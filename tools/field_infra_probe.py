#!/usr/bin/env python3
"""扫 τ² 田野语料里 infrastructure_error 行的 error 文本，看能否识别"上下文耗尽"。
只读缓存；输出 results/bfcl/field_infra_probe_v1/probe.json。零 GPU。
目的：核实 §4.4/摘要的 "window/context exhaustion = 0 rows" 是否只是"终止原因标签里没有窗口"，
还是"保留的 error 文本里也没有上下文耗尽签名"。"""
import json, glob, re, collections, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "results/bfcl/field_scan_v1/traj_cache"
OUT = ROOT / "results/bfcl/field_infra_probe_v1"
DEC = json.JSONDecoder()

PAT = re.compile(r"context|token|window|too long|maximum|400|length", re.I)
HARD = re.compile(r"context[_ ]length|maximum context|max_tokens|exceeds the maximum|"
                  r"context window|too many tokens|prompt is too long|400[^0-9]", re.I)


def iter_sims(path):
    txt = pathlib.Path(path).read_text(errors="replace")
    i = txt.find('"simulations"')
    if i < 0:
        return
    i = txt.find('[', i)
    i += 1
    n = len(txt)
    while i < n:
        while i < n and txt[i] in ' \t\r\n,':
            i += 1
        if i >= n or txt[i] == ']':
            return
        try:
            obj, i = DEC.raw_decode(txt, i)
        except json.JSONDecodeError:
            return
        yield obj


def main():
    files = sorted(glob.glob(str(CACHE / "*.json")))
    rows = []
    reason_counter = collections.Counter()
    infra = 0
    infra_with_info = 0
    hits = []
    for f in files:
        try:
            sims = list(iter_sims(f))
        except Exception as e:
            print("ERR", f, e, file=sys.stderr)
            continue
        n_inf = 0
        for s in sims:
            t = s.get("termination_reason")
            reason_counter[str(t)] += 1
            if t != "infrastructure_error":
                continue
            infra += 1; n_inf += 1
            info = s.get("info") or {}
            if isinstance(info, str):
                info = {"raw": info}
            err = str(info.get("error", "")) + " " + str(info.get("error_type", ""))
            if err.strip():
                infra_with_info += 1
            if HARD.search(err):
                hits.append({"file": pathlib.Path(f).name[:40], "errt": str(info.get("error_type"))[:60],
                             "err": err[:180]})
        rows.append({"file": pathlib.Path(f).name, "n_sims": len(sims), "n_infra": n_inf})
        print(f"{pathlib.Path(f).name[:52]:54s} sims={len(sims):4d} infra={n_inf:4d} hits={len(hits)}", flush=True)
    res = {"schema": "field_infra_probe_v1", "n_files": len(files),
           "n_sims": sum(r["n_sims"] for r in rows), "n_infra": infra,
           "n_infra_with_error_text": infra_with_info,
           "n_hard_context_hits": len(hits), "hard_hits": hits[:60],
           "termination_reasons": dict(reason_counter.most_common(12)), "per_file": rows,
           "note": "HARD 只匹配上下文/长度类硬签名；'error' 字段在 messages 被清空时仍保留。"}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "probe.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k not in ("per_file", "hard_hits")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
