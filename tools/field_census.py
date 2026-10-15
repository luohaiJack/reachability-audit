#!/usr/bin/env python3
"""field_census.py — M2：τ² 官方榜公开提交的**执行级**田野普查（零 GPU）。

与 `field_tax_scan.py`（191/196）的关系：那是 28 份、按"已下载的域文件"算；
本脚本把**分母**扩到全部声明轨迹的提交，并把"可审计比例"作为一等结论。

冻结规则（217 §M2，跑前落盘）：
  1. 提交集 = `submissions/*/submission.json` 且 `trajectories_available == true`，
     **排除 `A_EXAMPLE_*`**（模板，非真实提交）；
  2. 每份提交**只取一个域文件**，偏好序 **telecom → retail → airline → banking_knowledge**
     （便宜优先；此序在下载前冻结，不按结果挑）；
  3. 下载失败/空文件 ⇒ 记 `unavailable`，**不静默丢弃**，并计入分母；
  4. 下载预算：新增 ≤ 2.5 GB，超预算的记为 `skipped_budget`。

用法： python3 code/field_census.py [--no-fetch]
写：   results/field_census_v1/census.json
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
import os
ROOT = pathlib.Path(os.environ.get("DSH_AUDIT_ROOT") or ROOT).resolve()
SUBS = (ROOT / "code/baseline_selection/tau2-bench/web/leaderboard/public/submissions")
CACHE = ROOT / "results" / "bfcl" / "field_scan_v1" / "traj_cache"
OUT = ROOT / "results" / "field_census_v1"
BASE = "https://sierra-tau-bench-public.s3.us-west-2.amazonaws.com/submissions"
PREF = ["telecom", "retail", "airline", "banking_knowledge"]
BUDGET_BYTES = int(2.5e9)
SCORED = {"max_steps", "too_many_errors"}          # τ² 记分
EXCLUDED = {"infrastructure_error"}                # τ² 排除


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def declarations():
    out = []
    for p in sorted(SUBS.iterdir()):
        f = p / "submission.json"
        if not f.exists() or p.name.startswith("A_EXAMPLE"):
            continue
        d = json.loads(f.read_text(encoding="utf-8"))
        if not d.get("trajectories_available"):
            continue
        tf = d.get("trajectory_files") or {}
        if not isinstance(tf, dict):
            continue
        dom = next((x for x in PREF if tf.get(x)), None)
        if dom:
            out.append({"dir": p.name, "domain": dom, "file": tf[dom],
                        "type": d.get("submission_type"),
                        "model": d.get("model_name"), "org": d.get("model_organization")})
    return out


def fetch(decl, budget):
    CACHE.mkdir(parents=True, exist_ok=True)
    local = CACHE / f"{decl['dir']}__{decl['file']}"
    if local.exists() and local.stat().st_size > 0:
        return local, "cached", 0
    if budget[0] <= 0:
        return None, "skipped_budget", 0
    url = f"{BASE}/{decl['dir']}/trajectories/{decl['file']}"
    r = subprocess.run(["curl", "-sS", "-m", "240", "-o", str(local), "-w", "%{http_code} %{size_download}",
                        url], capture_output=True, text=True)
    code_size = (r.stdout or "").split()
    code = code_size[0] if code_size else "000"
    size = int(code_size[1]) if len(code_size) > 1 else 0
    # S3 对"缺 key"会返回 **200 + 一小段 NoSuchKey XML**（实测 393 B），
    # 只看状态码会把它当成下载成功，随后在解析阶段报 JSONDecodeError（2026-10-15 修正）。
    body_head = ""
    if local.exists():
        body_head = local.read_bytes()[:200].decode("utf-8", "replace")
    missing_key = "<Code>NoSuchKey</Code>" in body_head or body_head.lstrip().startswith("<?xml")
    if code != "200" or size == 0 or missing_key:
        if local.exists():
            local.unlink()
        return None, ("no_such_key" if missing_key else f"http_{code}"), 0
    budget[0] -= size
    return local, "fetched", size


def parse(path: pathlib.Path):
    d = json.loads(path.read_text(encoding="utf-8"))
    sims = d.get("simulations") or []
    reasons = collections.Counter(str(s.get("termination_reason")) for s in sims)
    rewards = [(s.get("reward_info") or {}).get("reward") for s in sims]
    n = len(sims)
    excl = sum(v for k, v in reasons.items() if k in EXCLUDED)
    scored_abn = sum(v for k, v in reasons.items() if k in SCORED)
    correct = sum(1 for r in rewards if r == 1)
    win = 0
    for s in sims:
        i = s.get("info") or {}
        e = (i.get("error") or "") + " " + str(i.get("error_type") or "")
        if "context length" in e.lower() or "ContextWindow" in e:
            win += 1
    return {"n_sims": n, "termination_reasons": dict(reasons), "n_excluded": excl,
            "n_scored_abnormal": scored_abn, "n_correct": correct,
            "n_reward_none": sum(1 for r in rewards if r is None),
            "n_window_class": win,
            "tax_excluded": round(excl / n, 4) if n else None,
            "tax_any_abnormal": round((excl + scored_abn) / n, 4) if n else None}


def main() -> int:
    no_fetch = "--no-fetch" in sys.argv
    if not SUBS.is_dir():
        print("⛔ 找不到 τ² 官方榜检出：" + str(SUBS), file=sys.stderr)
        print("   本脚本需要该仓库的 submissions/ 目录（MIT）。", file=sys.stderr)
        print("   获取：git clone https://github.com/sierra-research/tau2-bench", file=sys.stderr)
        print("   或用 DSH_AUDIT_ROOT 指向含该路径的数据树根。", file=sys.stderr)
        return 1
    decls = declarations()
    print(f"声明轨迹的提交（去模板）: {len(decls)}")
    budget = [0 if no_fetch else BUDGET_BYTES]
    rows, unavailable = [], []
    for d in decls:
        if no_fetch:
            local = CACHE / f"{d['dir']}__{d['file']}"
            if not (local.exists() and local.stat().st_size > 0):
                unavailable.append({**d, "why": "not_cached(no_fetch)"})
                continue
            src, how, size = local, "cached", 0
        else:
            src, how, size = fetch(d, budget)
        if src is None:
            unavailable.append({**d, "why": how})
            continue
        try:
            m = parse(src)
        except Exception as e:                                   # noqa: BLE001
            unavailable.append({**d, "why": f"parse_error:{type(e).__name__}"})
            continue
        rows.append({**d, "how": how, "bytes": size, **m})
        print(f"  [{how:7s}] {d['dir'][:44]:44s} {d['domain']:18s} n={m['n_sims']:4d} "
              f"excl={m['n_excluded']:3d} window={m['n_window_class']}")

    taxes = [r["tax_excluded"] for r in rows if r["tax_excluded"] is not None]
    taxes.sort()
    tot_excl = sum(r["n_excluded"] for r in rows)
    tot_sims = sum(r["n_sims"] for r in rows)
    tot_win = sum(r["n_window_class"] for r in rows)
    n_sub_all = len([p for p in SUBS.iterdir() if (p / "submission.json").exists()])
    cens = {
        "schema": "field_census_v1",
        "prereg": "217_预注册_M1M2M4_2026-10-15.md",
        "denominator": {"n_submissions_total": n_sub_all,
                        "n_declaring_trajectories": len(decls),
                        "n_audited": len(rows),
                        "n_unavailable": len(unavailable),
                        "audited_fraction_of_total": round(len(rows) / n_sub_all, 4),
                        "audited_fraction_of_declaring": round(len(rows) / len(decls), 4)},
        "aggregate": {"n_sims": tot_sims, "n_excluded_infra": tot_excl,
                      "excluded_share": round(tot_excl / tot_sims, 4) if tot_sims else None,
                      "n_window_class": tot_win},
        "tax_distribution": {"n": len(taxes), "median": taxes[len(taxes) // 2] if taxes else None,
                             "max": taxes[-1] if taxes else None,
                             "n_zero": sum(1 for t in taxes if t == 0),
                             "share_nonzero": round(sum(1 for t in taxes if t > 0) / len(taxes), 4) if taxes else None},
        "ci95_on_zero_share": list(wilson(sum(1 for t in taxes if t == 0), len(taxes))) if taxes else None,
        "schools": {"excluded": sum(1 for r in rows if r["n_excluded"] > 0),
                    "scored_abnormal": sum(1 for r in rows if r["n_scored_abnormal"] > 0),
                    "clean": sum(1 for r in rows if r["n_excluded"] == 0 and r["n_scored_abnormal"] == 0)},
        "unavailable": unavailable, "rows": rows,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "census.json").write_text(json.dumps(cens, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n== 分母 ==", json.dumps(cens["denominator"], ensure_ascii=False))
    print("== 汇总 ==", json.dumps(cens["aggregate"], ensure_ascii=False))
    print("== 税分布 ==", json.dumps(cens["tax_distribution"], ensure_ascii=False))
    print("== 派别 ==", json.dumps(cens["schools"], ensure_ascii=False))
    print(f"wrote {(OUT / 'census.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
