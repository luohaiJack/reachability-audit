#!/usr/bin/env python3
"""paired_from_results.py — 从**臂的结果文件**（带题号）做逐题配对与精确 McNemar。

为什么不用插桩日志：日志里 `n_messages==2` 的行按**回合波次**出现（先 40 条首轮，
再后续回合），且**未记题号** ⇒ 只能做聚合比较；而 `*_result.json` 每行都带 `id`，
拒绝状态可直接读出 ⇒ **逐题配对只能从结果文件做**。
"""
from __future__ import annotations

import json
import math
import pathlib

ARMS = {
    "A2_4B_40960_run1": "matrix_A2_ctx40960_v1",
    "A2r_4B_40960_run2": "matrix_A2r_ctx40960_clientcount_v1",
    "A2_4B_65536": "matrix_A2_ctx65536_v1",
    "S4_8B_40960": "matrix_S4_qwen3_8b_ctx40960_v1",
}


def _arm_dir(arm: str) -> pathlib.Path | None:
    base = pathlib.Path(__file__).resolve().parents[1]
    for cand in (base / "results" / "bfcl" / arm, base / "slices" / arm):
        if cand.is_dir():
            return cand
    return None


def rejected(arm: str) -> set[str]:
    out = set()
    root = _arm_dir(arm)
    if root is None:
        return out
    for f in root.rglob("*_result.json"):
        for ln in f.read_text(errors="replace").splitlines():
            if ln.strip() and "maximum context length" in (json.loads(ln).get("result") or ""):
                out.add(json.loads(ln)["id"])
    return out


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n))


def main() -> int:
    rej = {k: rejected(v) for k, v in ARMS.items()}
    for k, v in rej.items():
        print(f"{k:20s} 被拒 {len(v):3d}")
    res = {}
    pairs = [("A2_4B_40960_run1", "A2r_4B_40960_run2", "同配置两跑"),
             ("A2r_4B_40960_run2", "S4_8B_40960", "同窗口 4B vs 8B"),
             ("A2r_4B_40960_run2", "A2_4B_65536", "同模型 40,960 vs 65,536")]
    for x, y, lab in pairs:
        universe = 40                      # 每臂题集固定 40 题（冻结件 100–139）
        b = len(rej[x] - rej[y])
        c = len(rej[y] - rej[x])
        both = len(rej[x] & rej[y])
        neither = universe - b - c - both
        p = mcnemar_exact(b, c)
        res[lab] = {"arms": [x, y], "n_tasks_universe": universe, "both": both, "neither": neither,
                    "only_first": b, "only_second": c, "mcnemar_exact_p": p}
        print(f"{lab:26s} 全 40 题 | 都拒 {both:2d} | 都不拒 {neither:2d} | "
              f"仅前者 {b} | 仅后者 {c} | McNemar p={p:.4f}")
    ws = pathlib.Path(__file__).resolve().parents[1] / "results" / "bfcl"
    payload = {"rejected_counts": {k: len(v) for k, v in rej.items()}, "pairs": res}
    if ws.is_dir():                                   # 工作区布局才落盘；随包跑只打印
        (ws / "paired_from_results.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        print("→ results/bfcl/paired_from_results.json")
    else:
        print("（随包运行：仅打印，不落盘）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
