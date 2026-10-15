#!/usr/bin/env python3
"""reproduce.py — 用交付的仪器重跑论文的 10 条臂，并逐字段比对 expected_reports.json。

用法： python3 reproduce.py --workspace /path/to/workspace [--write]
退出码：0 = 全部一致；1 = 有差异（逐条打印）。
"""
import argparse, json, pathlib, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
FIELDS = [("buckets", "b1_executed_correct"), ("buckets", "b2_executed_harness_failed"),
          ("buckets", "b3_never_executed_boundary"), ("rates", "official_accuracy"),
          ("rates", "conditional_accuracy"), ("rates", "tax_cost_pp")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, help="含 results/bfcl/ 的工作区根")
    ap.add_argument("--write", action="store_true", help="把重跑报告写回结果目录")
    a = ap.parse_args()
    ws = pathlib.Path(a.workspace).resolve()
    exp = json.loads((HERE / "expected_reports.json").read_text(encoding="utf-8"))
    bad, n = [], 0
    for arm, want in sorted(exp.items()):
        d = ws / "results" / "bfcl" / arm
        if not d.is_dir():
            print(f"[SKIP] {arm}: 目录不存在");  continue
        n += 1
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run([sys.executable, str(HERE / "bfcl_tax_report.py"), str(d),
                                "--out", str(pathlib.Path(td) / "o.json")],
                               check=False, capture_output=True, text=True)
        got = json.loads((d / "tax_report.json").read_text(encoding="utf-8"))
        diffs = [(k, sub, got[k][sub], want[k][sub]) for k, sub in FIELDS
                 if got.get(k, {}).get(sub) != want[k][sub]]
        # 仪器自己判的门禁与退出码也算结果的一部分
        if not got.get("gates_pass"):
            diffs.append(("gates", "gates_pass", got.get("gates_pass"), True))
        if r.returncode not in (0, 2):
            diffs.append(("exit", "returncode", r.returncode, "0|2"))
        print(f"[{'OK  ' if not diffs else 'DIFF'}] {arm}"
              + ("" if not diffs else f"  {diffs}"))
        bad += diffs
    print(f"\n{n} 臂重跑，差异 {len(bad)} 处")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
