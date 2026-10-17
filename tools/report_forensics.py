#!/usr/bin/env python3
"""report_forensics.py — M1：报文字段取证（检测器 + 探针）

问题：服务端在"上下文超限"时回报的 **输入 token 数**，是**测量**还是**构造值**？

判据（217 §M1，跑前冻结）——**保持提示不变、只改 `max_tokens`**：
  · 若回报的输入数与 `max_tokens` 联动（且满足 `in + out == W + 1`）⇒ **constructed**
    （它是"窗口减去输出额度"的余数，不是对提示的测量）
  · 若回报的输入数**不随** `max_tokens` 变、而随**提示长度**变 ⇒ **measured**
  · 报文里根本没有计数 ⇒ **absent**

用法：
  # 检测器：读一段文本/文件里的 400 报文
  python3 code/report_forensics.py classify --text '...error json...'
  # 探针：对若干栈跑矩阵（同提示 × 不同 max_tokens）
  python3 code/report_forensics.py probe --out results/m1_probe_v1/probe.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]

# 已知的报文模式 → 抓 (W, out, in)
PATTERNS = [
    # 修复后（vLLM PR #57035 / commit 1a3a7a8）：窗口界 + "even without any output tokens"
    # 报文里没有 requested output 数，报数恒为 W+1 ⇒ 与"输出额度"解耦（window_bound）
    (re.compile(r"maximum context length is (\d+) tokens.*?contains at least (\d+) input tokens"
                r".*?even without any output tokens", re.S | re.I), "vllm_postfix"),
    # vLLM：窗口 + requested output + "at least ... input"
    (re.compile(r"maximum context length is (\d+) tokens.*?requested (\d+) output tokens"
                r".*?contains at least (\d+) input tokens", re.S | re.I), "vllm_ctx"),
    # Ollama / llama.cpp 系：request (N tokens) exceeds the available context size (W tokens)
    (re.compile(r"request \((\d+) tokens\) exceeds the available context size \((\d+) tokens\)", re.I),
     "ollama_req"),
    # 通用：某种 "max_tokens"/"context length" 组合
    (re.compile(r"max(?:imum)?[ _]?(?:context|seq)[ _]?len(?:gth)?[^0-9]{0,20}(\d+)", re.I), "generic_ctx"),
]


def classify(text: str) -> dict:
    """输入报文（任意格式的字符串），输出判定。"""
    out = {"verdict": "absent", "W": None, "out": None, "in": None, "pattern": None,
           "evidence": []}
    DOCUMENTED = {"constructed", "non_tautological", "absent", "window_bound"}
    for rx, name in PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        if name == "vllm_ctx":
            W, o, i = int(m.group(1)), int(m.group(2)), int(m.group(3))
            out.update(W=W, out=o, in_=i, pattern=name)
            out["in"] = i
            out["evidence"].append(f"W={W} out={o} in={i} out+in={o+i} (W+1={W+1})")
            out["verdict"] = "constructed" if o + i == W + 1 else "non_tautological"
            return out
        if name == "vllm_postfix":
            W, i = int(m.group(1)), int(m.group(2))
            out.update(W=W, out=None, pattern=name)
            out["in"] = i
            out["evidence"].append(f"W={W} in={i} (W+1={W+1}) 无 requested-output 项")
            # 修复后：报数恒 W+1，与请求的 allowance 解耦；记为 window_bound（不是 measurement）
            out["verdict"] = "window_bound" if i == W + 1 else "non_tautological"
            return out
        if name == "ollama_req":
            n, W = int(m.group(1)), int(m.group(2))
            out.update(W=W, out=None, pattern=name)
            out["in"] = n
            out["evidence"].append(f"request={n} ctx={W}")
            # 单条报文**不能**判"measured"：那需要 probe 矩阵（同提示 × 不同额度）。
            # 这里只能给出"不是那个恒等式"，命名与 docstring 的三种 verdict 分开。
            out["verdict"] = "non_tautological"
            return out
        if name == "generic_ctx":
            out.update(W=int(m.group(1)), pattern=name)
            out["evidence"].append(f"ctx={m.group(1)}")
            return out
    return out


DOCUMENTED_VERDICTS = {"constructed", "non_tautological", "absent", "window_bound"}


def _assert_documented(v: dict) -> dict:
    if v["verdict"] not in DOCUMENTED_VERDICTS:      # 词表守卫（2026-10-15）
        raise AssertionError(f"未文档化的 verdict {v['verdict']!r}")
    return v


def _post(base: str, model: str, prompt: str, max_tokens: int, timeout: int = 180):
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "max_tokens": max_tokens}).encode()
    req = urllib.request.Request(base.rstrip("/") + "/v1/chat/completions", data=body,
                                 headers={"Content-Type": "application/json",
                                          "Authorization": "Bearer EMPTY"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(4000).decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(4000).decode(errors="replace")
    except Exception as e:                                        # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def probe(stacks: list[dict], out_path: pathlib.Path) -> dict:
    prompts = {"p3000": "hello " * 3000, "p9000": "hello " * 9000}
    maxes = [1, 128, 4096]
    res = {"schema": "m1_probe_v1", "stacks": []}
    for st in stacks:
        rec = {"name": st["name"], "base": st["base"], "model": st["model"], "cells": []}
        for pname, p in prompts.items():
            for mt in maxes:
                code, body = _post(st["base"], st["model"], p, mt)
                c = classify(body)
                rec["cells"].append({"prompt": pname, "max_tokens": mt, "http": code,
                                     "body": body[:400], **c})
        _finish(rec, prompts)
        res["stacks"].append(rec)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def _finish(rec: dict, prompts: dict) -> dict:
        # 判定：同一提示下 in 是否随 max_tokens 变
        for pname in prompts:
            cells = [c for c in rec["cells"] if c["prompt"] == pname and c["in"] is not None]
            ins = {c["in"] for c in cells}
            outs = {c["out"] for c in cells}
            if cells:
                rec[f"in_varies_with_max_tokens_{pname}"] = len(ins) > 1
                rec[f"io_sum_constant_{pname}"] = (
                    len({(c["out"] or 0) + c["in"] for c in cells}) == 1)
                rec[f"n_reported_{pname}"] = len(cells)
        # 判定（217 §M1）：
        #  window_bound = 同一提示下 in **不随** out 变，且恒等于 W+1（修复后 vLLM 系）
        #  constructed = 同一提示下 in 随 out 联动，且 out+in 恒定（vLLM 系，pre-fix）
        #  measured    = 同一提示下 in 不随 out 变，却随提示长度变（ollama/llama.cpp 系）
        cons = rec.get("io_sum_constant_p9000") and rec.get("in_varies_with_max_tokens_p9000")
        by_out = {}
        for c in rec["cells"]:
            if c["in"] is not None:
                by_out.setdefault(c["max_tokens"], {})[c["prompt"]] = c["in"]
        varied_with_prompt = any(len(set(v.values())) > 1 for v in by_out.values())
        invariant_in_out = rec.get("n_reported_p9000") and not rec.get("in_varies_with_max_tokens_p9000")
        # window_bound：同一提示下 in 不随 out 变，且恒等于 W+1（修复后 vLLM 系）
        _ins9 = {c["in"] for c in rec["cells"]
                 if c["prompt"] == "p9000" and c["in"] is not None}
        _W9 = {c["W"] for c in rec["cells"] if c["prompt"] == "p9000" and c.get("W")}
        is_window_bound = (len(_ins9) == 1 and bool(_W9)
                           and next(iter(_ins9)) == next(iter(_W9)) + 1
                           and not rec.get("in_varies_with_max_tokens_p9000", False))
        if is_window_bound:
            rec["verdict"] = "window_bound"
        elif cons:
            rec["verdict"] = "constructed"
        elif invariant_in_out and varied_with_prompt:
            rec["verdict"] = "measured"
        else:
            rec["verdict"] = "unclear"
        rec["in_varies_with_prompt"] = varied_with_prompt
        return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify")
    c.add_argument("--text", default=None)
    c.add_argument("--file", default=None)
    st = sub.add_parser("selftest")
    p = sub.add_parser("probe")
    p.add_argument("--out", default=str(ROOT / "results" / "m1_probe_v1" / "probe.json"))
    p.add_argument("--replay", default=None,
                   help="离线复算：读已冻结的 probe fixture，重算各栈 verdict（无需活体栈）")
    p.add_argument("--stack", action="append", default=[],
                   help="name=base|model，可重复")
    a = ap.parse_args()
    if a.cmd == "selftest":
        cases = [
            ('{"error":{"message":"This model\'s maximum context length is 8192 tokens. However, '
             'you requested 0 output tokens and your prompt contains at least 8193 input tokens, '
             'for a total of at least 8193 tokens."}}', "constructed"),
            ('{"error":{"message":"request (3030 tokens) exceeds the available context size '
             '(512 tokens), try increasing it"}}', "non_tautological"),
            ('{"error":{"message":"bad request"}}', "absent"),
        ]
        bad = 0
        for text, want in cases:
            got = classify(text)["verdict"]
            ok = got == want
            bad += 0 if ok else 1
            print(f"[{'OK  ' if ok else 'FAIL'}] classify → {got:16s} want {want}")
        print("selftest", "PASS" if not bad else f"FAIL ({bad})")
        return 1 if bad else 0
    if a.cmd == "classify":
        txt = a.text or pathlib.Path(a.file).read_text(errors="replace")
        print(json.dumps(_assert_documented(classify(txt)), ensure_ascii=False, indent=1))
        return 0
    if a.replay:
        fx = json.loads(pathlib.Path(a.replay).read_text(encoding="utf-8"))
        prompts = {"p3000": "hello " * 3000, "p9000": "hello " * 9000}
        bad = 0
        for st in fx["stacks"]:
            rec = {"name": st["name"], "base": st.get("base"), "model": st.get("model"),
                   "cells": [dict(c, **classify(c.get("body") or "")) for c in st["cells"]]}
            _finish(rec, prompts)
            ok = rec["verdict"] == st.get("verdict")
            bad += 0 if ok else 1
            print(f"[{'OK  ' if ok else 'FAIL'}] {st['name']:10s} live={st.get('verdict')} "
                  f"replay={rec['verdict']}")
        print("replay", "PASS" if not bad else f"FAIL ({bad})")
        return 1 if bad else 0
    stacks = []
    for s in a.stack:
        nm, rest = s.split("=", 1)
        base, model = rest.split("|", 1)
        stacks.append({"name": nm, "base": base, "model": model})
    r = probe(stacks, pathlib.Path(a.out))
    for st in r["stacks"]:
        print(f"{st['name']:12s} verdict={st['verdict']:20s} "
              f"in_varies={st.get('in_varies_with_max_tokens_long')} "
              f"sum_const={st.get('io_sum_constant_long')}")
    print("wrote", a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
