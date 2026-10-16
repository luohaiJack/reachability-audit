#!/usr/bin/env python3
"""reproduce.py — 用交付的仪器重跑论文的 18 条臂，并逐字段比对 expected_reports.json。

**两种输入来源**（按序）：
  1. 工作区：`<workspace>/results/bfcl/<arm>/`（原作者的数据树，可选）
  2. **随包切片**：`<本目录>/slices/<arm>/`（约 40 MB，**第三方无需任何外部数据**）

运行时把被审计目录**复制到临时目录**再跑，因此**不会改动本包**。

用法： python3 reproduce.py --workspace /path/to/workspace
       python3 reproduce.py                 # 只用随包切片（第三方最短路径）
退出码：0 = 全部一致；1 = 有差异（逐条打印）
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
FIELDS = [("buckets", "b1_executed_correct"), ("buckets", "b2_executed_harness_failed"),
          ("buckets", "b3_never_executed_boundary"), ("rates", "official_accuracy"),
          ("rates", "conditional_accuracy"), ("rates", "tax_cost_pp")]


def locate(arm: str, ws: pathlib.Path | None):
    if ws is not None:
        d = ws / "results" / "bfcl" / arm
        if d.is_dir():
            return d, "workspace"
    d = HERE / "slices" / arm
    if d.is_dir():
        return d, "bundle"
    return None, "missing"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=None, help="原作者数据树根（可选）")
    a = ap.parse_args()
    ws = pathlib.Path(a.workspace).resolve() if a.workspace else None
    exp = json.loads((HERE / "expected_reports.json").read_text(encoding="utf-8"))
    bad, n, srcs = [], 0, {"workspace": 0, "bundle": 0}
    for arm, want in sorted(exp.items()):
        src, how = locate(arm, ws)
        if src is None:
            print(f"[SKIP] {arm}: 无数据（既不在工作区，也不在随包切片）")
            continue
        n += 1
        srcs[how] += 1
        with tempfile.TemporaryDirectory() as td:
            work = pathlib.Path(td) / arm
            shutil.copytree(src, work)
            r = subprocess.run([sys.executable, str(HERE / "bfcl_tax_report.py"), str(work),
                                "--out", str(pathlib.Path(td) / "merged.json")],
                               check=False, capture_output=True, text=True)
            got = json.loads((work / "tax_report.json").read_text(encoding="utf-8"))
        diffs = [(k, sub, got[k][sub], want[k][sub]) for k, sub in FIELDS
                 if got.get(k, {}).get(sub) != want[k][sub]]
        if not got.get("gates_pass"):
            diffs.append(("gates", "gates_pass", got.get("gates_pass"), True))
        if r.returncode not in (0, 2):
            diffs.append(("exit", "returncode", r.returncode, "0|2"))
        print(f"[{'OK  ' if not diffs else 'DIFF'}] {arm:46s} ({how})"
              + ("" if not diffs else f"  {diffs}"))
        bad += diffs
    print(f"\n{n} 臂重跑（工作区 {srcs['workspace']} / 随包切片 {srcs['bundle']}），差异 {len(bad)} 处")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
