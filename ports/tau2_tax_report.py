#!/usr/bin/env python3
"""tau2_tax_report.py — 把 `artifact_reachability_audit_v1/bfcl_tax_report.py` 的**同一套口径**
移植到 τ²-bench 官方 harness。

按 README 的移植说明，改的是：
  · load_rows()  —— τ² 的 rollout 记录在 results.json 的 simulations[] 里
  · load_score() —— τ² 的"分"是 reward_info.reward，终止原因在 termination_reason
  · **③ 桶的判据**（BFCL: error_type == multi_turn:inference_error；τ²: termination_reason
    == "infrastructure_error"）—— 这是**内容改动**，不是换文件布局
  · **门禁只带 2/6**（G1 行数、G5 桶互斥完备）：其余四门要的输入（chain 日志、官方 score
    表头、逐条计分一致性、题号集合关系）τ² 的产物里没有，**不许假装带上了**
三桶与三个率的**定义**沿用；实现按上面四点改。

映射（写进报告，便于复核）：
  ③ 从未执行 = termination_reason == "infrastructure_error"（官方自己把它排除在指标外）
  ① 执行且正确 = 跑到判分且 reward == 1
  ② 执行但失败 = 其余（正常停止但 reward < 1 / max_steps / too_many_errors …）

用法： python3 code/tau2_tax_report.py <results.json 或所在目录> [--json]
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

NEVER = {"infrastructure_error"}


def load_rows(p: pathlib.Path):
    d = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else json.loads(
        (p / "results.json").read_text(encoding="utf-8"))
    sims = d.get("simulations") or []
    rows = []
    for s in sims:
        tid = s.get("task_id", s.get("id"))
        try:
            tid = int(tid)
        except (TypeError, ValueError):
            pass
        rows.append((tid, s))
    return rows, d


def load_score(rows):
    """τ² 没有独立判分文件；分与终止原因都在 simulation 记录里。"""
    score = {}
    for tid, s in rows:
        ri = s.get("reward_info") or {}
        r = ri.get("reward")
        reason = s.get("termination_reason") or "unknown"
        info = s.get("info") or {}
        score[tid] = {
            "reward": r,
            "termination_reason": str(reason),
            "error_type": info.get("error_type"),
            "error": (info.get("error") or "")[:400],
        }
    return score


def report(p: pathlib.Path) -> dict:
    rows, raw = load_rows(p)
    score = load_score(rows)
    n = len(rows) or 1
    never = {t for t, v in score.items() if v["termination_reason"] in NEVER}
    correct = {t for t, v in score.items()
               if t not in never and v["reward"] is not None and abs(v["reward"] - 1.0) < 1e-9}
    harness = set(score) - never - correct
    acc = len(correct) / n
    cond = len(correct) / max(len(correct) + len(harness), 1)
    reasons = collections.Counter(v["termination_reason"] for v in score.values())
    errs = collections.Counter(v["error_type"] for v in score.values() if v["error_type"])
    window = [t for t, v in score.items()
              if v["termination_reason"] in NEVER
              and ("context length" in v["error"].lower() or "maximum context" in v["error"].lower()
                   or "400" in v["error"])]
    return {
        "schema": "tau2_tax_report_v1",
        "dir": str(p),
        "n_total": n,
        "buckets": {"b1_executed_correct": len(correct),
                    "b2_executed_harness_failed": len(harness),
                    "b3_never_executed_boundary": len(never),
                    "b3_task_ids_count": len(never)},
        "rates": {"official_accuracy": round(acc, 4),
                  "conditional_accuracy": round(cond, 4),
                  "reachability_tax": round(len(never) / n, 4),
                  "tax_cost_pp": round((cond - acc) * 100, 1)},
        "termination_reasons": dict(reasons),
        "error_types": dict(errs),
        "window_rejection_task_ids": sorted(window),
        "gates": {"G1_rows_present": len(rows) > 0,
                  "G1_rows_count": len(rows),
                  "G5_bucket_partition": len(never & harness) == 0
                  and len(correct) + len(never) + len(harness) == len(score)},
        "gates_pass": len(never & harness) == 0
        and len(correct) + len(never) + len(harness) == len(score) and len(rows) > 0,
    }


def main() -> int:
    p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    r = report(p)
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(f"══ τ² {r['dir']} ══")
        print(f"仿真 {r['n_total']} | ①执行且对 {r['buckets']['b1_executed_correct']} | "
              f"②执行但失败 {r['buckets']['b2_executed_harness_failed']} | "
              f"③从未执行 {r['buckets']['b3_never_executed_boundary']}")
        print(f"官方 reward 均值 {r['rates']['official_accuracy']} | 条件 {r['rates']['conditional_accuracy']}"
              f" | 税 {r['rates']['reachability_tax']} | 税代价 {r['rates']['tax_cost_pp']} pp")
        print(f"终止原因 {r['termination_reasons']}")
        print(f"错误类型 {r['error_types']}")
        print(f"窗口类拒绝题号 {r['window_rejection_task_ids']}")
    return 0 if r["gates_pass"] else 2


if __name__ == "__main__":
    sys.exit(main())
