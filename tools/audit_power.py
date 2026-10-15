#!/usr/bin/env python3
r"""audit_power.py — M4：审计收益的**决策边界**（零 GPU）。

问题：观察到两臂分差 Δ（pp）时，**多大的 Δ 可以完全由"未执行样本"解释掉**？

推导（写死在这里，与 217 §M4 一致）
------------------------------------------------
臂 i：$n_i$ 条样本，$u_i$ 条从未执行（税 $\tau_i=u_i/n_i$），$c_i$ 条执行且正确。
未执行样本的**真实结果未知**，每条 ∈ {0,1} ⇒ 臂 $i$ 的"若都跑完"分数
$$\in\Big[\frac{c_i}{n_i},\ \frac{c_i+u_i}{n_i}\Big]$$
两臂相减 ⇒ 分差的可解释区间
$$\Delta\in\Big[\frac{c_A}{n_A}-\frac{c_B+u_B}{n_B},\ \frac{c_A+u_A}{n_A}-\frac{c_B}{n_B}\Big]$$
其**宽度恰好是** $\tau_A+\tau_B$（分数），即
$$\boxed{\ \Delta_{\max}=100\,(\tau_A+\tau_B)\ \text{pp}\ }$$
⇒ **决策规则**：$|\Delta|\le 100(\tau_A+\tau_B)$ 时，**这个分差不能作为能力证据**；
要读能力，先报可达性。

用法： python3 code/audit_power.py
写：   results/audit_power_v1/boundary.json
"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
import os
ROOT = pathlib.Path(os.environ.get("DSH_AUDIT_ROOT") or ROOT).resolve()
OUT = ROOT / "results" / "audit_power_v1"
HERE = pathlib.Path(__file__).resolve().parent


def _p(rel: str) -> pathlib.Path:
    """先在工作区找，找不到就用随包切片 inputs/（第三方离线可跑）。"""
    a = ROOT / rel
    if a.exists():
        return a
    b = HERE / "inputs" / pathlib.Path(rel).name
    if b.exists():
        return b
    for c in (HERE.parent / "inputs" / pathlib.Path(rel).name,):
        if c.exists():
            return c
    return a


def dmax_pp(tau_a: float, tau_b: float) -> float:
    return round(100.0 * (tau_a + tau_b), 2)


def check(tau_a: float, tau_b: float, gap_pp: float) -> int:
    """一行决策：给定两臂税与观测分差，判"能否当作能力证据"。"""
    bound = dmax_pp(tau_a, tau_b)
    licensed = abs(gap_pp) > bound
    print(f"τ_A={tau_a}  τ_B={tau_b}  |Δ|={abs(gap_pp)}pp  界 Δ_max={bound}pp")
    print(("✅ 许可：分差超出界 ⇒ 不能由未执行样本解释" if licensed else
           "⛔ 不许可：分差落在界内 ⇒ 可以被未执行样本完全解释，先报可达性"))
    return 0 if licensed else 3


def main() -> int:
    import argparse as _ap
    import sys as _sys
    _apx = _ap.ArgumentParser(add_help=False)
    _apx.add_argument("--check", nargs=3, type=float, metavar=("TAU_A", "TAU_B", "GAP_PP"))
    _a, _ = _apx.parse_known_args()
    if _a.check:
        return check(*_a.check)
    # 1) 边界表
    taus = [0.0, 0.02, 0.05, 0.10, 0.20, 0.50, 0.875]
    table = [{"tau_a": a, "tau_b": 0.0, "dmax_pp": dmax_pp(a, 0.0)} for a in taus]

    # 2) 用我们自己的臂校准：上界必须覆盖实测位移
    rows = json.loads(_p("results/bfcl/tax_report_all.json").read_text(encoding="utf-8"))
    cal = []
    for r in rows:
        rt, b = r.get("rates", {}), r.get("buckets", {})
        if rt.get("tax_cost_pp") is None:
            continue
        n = r["n_total"] or 1
        tau = b["b3_never_executed_boundary"] / n
        obs = rt["tax_cost_pp"]
        cal.append({"arm": r["dir"].split("/")[-1], "n": n, "tau_a": round(tau, 4),
                    "observed_pp": obs, "dmax_pp": dmax_pp(tau, 0.0),
                    "within_bound": abs(obs) <= dmax_pp(tau, 0.0) + 1e-9})

    # 3) 田野校准
    fs = json.loads(_p("results/bfcl/field_scan_v1/field_scan.json")
                    .read_text(encoding="utf-8"))
    fd = []
    for r in fs["rows"]:
        if r.get("official_pass") is None or r.get("conditional_pass") is None:
            continue
        tau = r["n_abnormal"] / (r["n_sims"] or 1)
        obs = (r["conditional_pass"] - r["official_pass"]) * 100
        fd.append({"dir": r["dir"], "n": r["n_sims"], "tau_a": round(tau, 4),
                   "observed_pp": round(obs, 2), "dmax_pp": dmax_pp(tau, 0.0),
                   "within_bound": abs(obs) <= dmax_pp(tau, 0.0) + 1e-9})

    out = {
        "schema": "audit_power_v1",
        "prereg": "217_预注册_M1M2M4_2026-10-15.md",
        "rule": "|Δ| ≤ 100·(τ_A + τ_B) pp ⇒ 分差可由未执行样本完全解释，不得当作能力证据",
        "boundary_table": table,
        "calibration_own_arms": cal,
        "calibration_field": fd,
        "checks": {
            "own_arms_all_within": all(c["within_bound"] for c in cal),
            "field_all_within": all(c["within_bound"] for c in fd),
            "own_arm_max_observed": max((c["observed_pp"] for c in cal), default=None),
            "own_arm_bound_at_that_tau": max(
                (c["dmax_pp"] for c in cal if c["observed_pp"] == max(
                    (x["observed_pp"] for x in cal), default=0)), default=None),
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "boundary.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    _src = "set" if os.environ.get("DSH_AUDIT_ROOT") else "unset"
    print(f"[审计根] {ROOT}  (DSH_AUDIT_ROOT={_src})")
    print("τ_A → Δ_max(pp)（τ_B=0）:")
    for t in table:
        print(f"  {t['tau_a']:.3f} → {t['dmax_pp']:6.2f}")
    print("\n注：单臂位移 ≤ 自身税是恒等式（由 tax_cost_pp 的定义直接得出），"
          "故『自臂全部落在界内』不构成校准；有信息量的是田野那一列与比值。")
    print(f"自臂 {len(cal)} 条：最大实测位移 = {out['checks']['own_arm_max_observed']}pp "
          f"（该臂上界 {out['checks']['own_arm_bound_at_that_tau']}pp）")
    print(f"田野 {len(fd)} 条：全部落在界内 = {out['checks']['field_all_within']}")
    print("wrote", (OUT / "boundary.json").relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
