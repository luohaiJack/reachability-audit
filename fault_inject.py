#!/usr/bin/env python3
"""fault_inject.py — 仪器的**已知答案故障注入**（known-answer controls）。

回答的是"`reproduce.py` 只能证明自洽"这一条：这里每个用例都**植入一个已知破坏**，
并断言 (1) 退出码为 2，(2) **失败的门禁名恰为预期集合**（多一个少一个都算 FAIL）。

用法： python3 code/fault_inject.py
退出码：0 = 全部用例符合预期；1 = 有不符合
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
CLI = HERE / "bfcl_tax_report.py"
BOUNDARY = ("This model's maximum context length is 8192 tokens. However, you requested 0 "
            "output tokens and your prompt contains at least 8193 input tokens.")
BAD_BOUNDARY = ("This model's maximum context length is 8192 tokens. However, you requested 0 "
                "output tokens and your prompt contains at least 7000 input tokens.")


def build_fixture(root: pathlib.Path) -> pathlib.Path:
    """已知-good 臂：6 对 / 2 执行错 / 2 从未执行；带 DONE 标记的 chain 日志。"""
    d = root / "arm_good"
    d.mkdir(parents=True, exist_ok=True)
    rows, score = [], []
    tid = 0
    for _ in range(6):
        rows.append(json.dumps({"id": f"multi_turn_long_context_{tid}", "result": ["ok"]})); tid += 1
    for _ in range(2):
        rows.append(json.dumps({"id": f"multi_turn_long_context_{tid}", "result": ["wrong"]}))
        score.append({"id": f"multi_turn_long_context_{tid}",
                      "error": {"error_type": "multi_turn:instance_state_mismatch"}}); tid += 1
    for _ in range(2):
        rows.append(json.dumps({"id": f"multi_turn_long_context_{tid}", "result": BOUNDARY}))
        score.append({"id": f"multi_turn_long_context_{tid}",
                      "error": {"error_type": "multi_turn:inference_error"}}); tid += 1
    (d / "arm_result.json").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (d / "official_score.jsonl").write_text(
        json.dumps({"accuracy": 0.6}) + "\n" + "\n".join(json.dumps(x) for x in score) + "\n",
        encoding="utf-8")
    (root / "arm_good_chain.log").write_text("arm_good_DONE\n", encoding="utf-8")
    return d


# ── 破坏算子 ────────────────────────────────────────────────────────────────
def f_delete_row(d: pathlib.Path):
    p = d / "arm_result.json"
    lines = p.read_text(encoding="utf-8").splitlines()
    p.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")     # 删最后一行


def f_orphan_score(d: pathlib.Path):
    p = d / "official_score.jsonl"
    p.write_text(p.read_text(encoding="utf-8") +
                 json.dumps({"id": "multi_turn_long_context_999",
                             "error": {"error_type": "multi_turn:instance_state_mismatch"}}) + "\n",
                 encoding="utf-8")


def f_tamper_accuracy(d: pathlib.Path):
    p = d / "official_score.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[0] = json.dumps({"accuracy": 0.9})
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def f_bad_boundary(d: pathlib.Path):
    p = d / "arm_result.json"
    p.write_text(p.read_text(encoding="utf-8").replace(BOUNDARY, BAD_BOUNDARY), encoding="utf-8")


def f_log_without_done(d: pathlib.Path):
    (d.parent / "arm_good_chain.log").write_text("arm_good started\n", encoding="utf-8")


CASES = [
    ("F0_no_break", None, set(), 0),
    ("F1_delete_row", f_delete_row, {"G4", "G5", "G6"}, 2),
    ("F2_orphan_score_id", f_orphan_score, {"G5", "G6"}, 2),
    ("F3_tamper_accuracy", f_tamper_accuracy, {"G4"}, 2),
    ("F4_boundary_invariant_broken", f_bad_boundary, {"G3"}, 2),
    ("F5_log_without_DONE", f_log_without_done, {"G2"}, 2),
]


def main() -> int:
    bad = 0
    for name, fn, want_fails, want_rc in CASES:
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            d = build_fixture(root)
            if fn:
                fn(d)
            r = subprocess.run([sys.executable, str(CLI), str(d)], capture_output=True, text=True)
            rep = d / "tax_report.json"
            if not rep.exists():
                print(f"[FAIL] {name}: 未产出报告（rc={r.returncode}）")
                bad += 1
                continue
            got = json.loads(rep.read_text(encoding="utf-8"))
            fails = {k for k, v in got["gates"].items() if isinstance(v, bool) and not v}
            fails_pref = {k.split("_")[0] for k in fails}          # 比前缀，容忍门禁名后缀
            ok = (r.returncode == want_rc) and (fails_pref == want_fails)
            bad += 0 if ok else 1
            print(f"[{'OK  ' if ok else 'FAIL'}] {name:30s} rc={r.returncode}(want {want_rc}) "
                  f"失败门禁={sorted(fails_pref)}(want {sorted(want_fails)})")
    print("fault_inject", "PASS" if not bad else f"FAIL ({bad})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
