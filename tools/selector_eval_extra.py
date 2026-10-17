#!/usr/bin/env python3
# selector_eval_extra.py — 复算 tab:zerotrain 背后的 selector_eval_extra.json（离线，零 GPU）
# ============================================================================
# 背景（第十一轮审稿 P1-1）：论文零训练表用的 selector_eval_extra.json 当时没有随包生成器，
# 门禁只做 json→正文 的比对。本文件把生成过程固定下来，并**自校验**：算出来的每个数必须
# 与已发布的 selector_eval_extra.json 逐项相等，否则非零退出。
#
# 口径（2026-10-17 用数据反推并验证，三个 selector 用同一套规则即可精确复现）：
#   first        = seed2001 那一条成功
#   oracle       = 三条里任意一条成功（pass@3）
#   length(滚动) = 该 rollout 的**工具调用步数** n_steps（rollout_features 的 n_steps，
#                  即 inference_log 里 (turn, step) 的个数）
#   tie          = 步数并列时取**较早**的 seed（min seed）。取较晚的 seed 会得到
#                  error_free_longest=28/70.0%/p=0.0625，与已发布 JSON 不符 ⇒ 已确认是前者。
#   capture      = (picked − first) / (oracle − first) × 100%
#   pass_both    = capture ≥ 30% 且 delta > 3 pp（现稿冻结判据）
#
# 用法：
#   python3 code/selector_eval_extra.py --run results/bfcl/probe_miss_param_K3_v2
#   python3 code/selector_eval_extra.py --run <随包切片> --check   # 只校验已发布 JSON
# ============================================================================
from __future__ import annotations
import argparse, json, pathlib, sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code/bfcl_budget_patch"))
try:                       # 随包运行时没有 code/bfcl_budget_patch（只有派生件）⇒ 允许缺失
    from rollout_selector_eval import rollout_features, mc_nemar_exact  # pinned, read-only
except ModuleNotFoundError:  # 仅 --check 的内核算术路径可用
    rollout_features = mc_nemar_exact = None

SEEDS = (2001, 2002, 2003)
SUBTRACK = "multi_turn_miss_param"
FIRST_SEED = 2001
CAPTURE_MIN, DELTA_MIN = 30.0, 3.0


def load(run: pathlib.Path):
    tasks: dict[str, list[dict]] = {}
    for td in sorted((run / "records").glob(f"{SUBTRACK}_*")):
        rows = []
        for s in SEEDS:
            rec = json.loads((td / f"BoK_seed{s}.json").read_text())
            lbl = json.loads((run / "labels" / f"{td.name}__BoK_seed{s}.json").read_text())
            rows.append({"seed": s, "ok": bool(lbl.get("success")),
                         "f": rollout_features(rec)})
        if len(rows) == 3:
            tasks[td.name] = rows
    return tasks


def _tie(rows):
    """步数并列 ⇒ 取较早 seed（已用数据确认，见文件头）。"""
    return min(rows, key=lambda r: r["seed"])


def sel_longest(rows):
    m = max(r["f"]["n_steps"] for r in rows)
    return _tie([r for r in rows if r["f"]["n_steps"] == m])


def sel_error_free_longest(rows):
    clean = [r for r in rows if r["f"]["n_errors"] == 0] or rows
    m = max(r["f"]["n_steps"] for r in clean)
    return _tie([r for r in clean if r["f"]["n_steps"] == m])


def sel_longest_first_call_majority(rows):
    cnt = Counter(json.dumps(r["f"]["first_calls"], ensure_ascii=False)
                  for r in rows if r["f"]["first_calls"])
    if not cnt:
        return sel_longest(rows)
    key, _ = cnt.most_common(1)[0]
    cand = [r for r in rows
            if json.dumps(r["f"]["first_calls"], ensure_ascii=False) == key]
    m = max(r["f"]["n_steps"] for r in cand)
    return _tie([r for r in cand if r["f"]["n_steps"] == m])


SELECTORS = {"longest": sel_longest,
             "error_free_longest": sel_error_free_longest,
             "longest_first_call_majority": sel_longest_first_call_majority}


def compute(tasks: dict[str, list[dict]]) -> dict:
    names = sorted(tasks)
    n = len(names)
    first = sum(1 for t in names
                if next(r["ok"] for r in tasks[t] if r["seed"] == FIRST_SEED))
    oracle = sum(1 for t in names if any(r["ok"] for r in tasks[t]))
    gap = oracle - first
    out = {"n": n, "first": first, "oracle": oracle, "gap": gap, "selectors": {}}
    for name, fn in SELECTORS.items():
        picked = sum(fn(tasks[t])["ok"] for t in names)
        # 与 first 配对的 McNemar：仅"first 失败、选择成功"与"first 成功、选择失败"两类
        b = sum(1 for t in names
                if (not next(r["ok"] for r in tasks[t] if r["seed"] == FIRST_SEED))
                and fn(tasks[t])["ok"])
        c = sum(1 for t in names
                if (next(r["ok"] for r in tasks[t] if r["seed"] == FIRST_SEED))
                and not fn(tasks[t])["ok"])
        p = mc_nemar_exact(b, c)
        delta = 100.0 * (picked - first) / n
        cap = (100.0 * (picked - first) / (oracle - first)) if oracle > first else 0.0
        out["selectors"][name] = {
            "picked": picked, "pct": round(100.0 * picked / n, 2),
            "delta_pp": round(delta, 2), "capture_pct": round(cap, 2),
            "mcnemar_p": p,
            "pass_both": bool(cap >= CAPTURE_MIN and delta > DELTA_MIN),
        }
    return out


def check_against(got: dict, ref_path: pathlib.Path) -> list[str]:
    ref = json.loads(ref_path.read_text())
    bad = []
    for k in ("n", "first", "oracle", "gap"):
        if got[k] != ref[k]:
            bad.append(f"{k}: got {got[k]} want {ref[k]}")
    for name, want in ref["selectors"].items():
        g = got["selectors"].get(name)
        if g is None:
            bad.append(f"{name}: 生成器没有该 selector")
            continue
        for k in ("picked", "pct", "delta_pp", "capture_pct", "mcnemar_p", "pass_both"):
            if abs(float(g[k]) - float(want[k])) > 1e-9 if isinstance(want[k], (int, float)) else g[k] != want[k]:
                bad.append(f"{name}.{k}: got {g[k]} want {want[k]}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=pathlib.Path,
                    default=ROOT / "results/bfcl/probe_miss_param_K3_v2")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--check", action="store_true", help="只校验不写盘")
    a = ap.parse_args(argv)
    run = a.run
    ref = run / "selector_eval_extra.json"
    if not (run / "records").is_dir() or not (run / "labels").is_dir():
        if ref.exists():
            print(f"[INFO] {run} 只有派生件，无 records/labels ⇒ 无法重算；"
                  f"改用随包的内核算术校验（picked/n、delta、capture、判据）")
            d = json.loads(ref.read_text())
            bad = []
            n, first, oracle = d["n"], d["first"], d["oracle"]
            for name, s in d["selectors"].items():
                if abs(s["pct"] - 100.0 * s["picked"] / n) > 0.02:
                    bad.append(f"{name}.pct")
                if abs(s["delta_pp"] - 100.0 * (s["picked"] - first) / n) > 0.02:
                    bad.append(f"{name}.delta_pp")
                cap = 100.0 * (s["picked"] - first) / (oracle - first)
                if abs(s["capture_pct"] - cap) > 0.02:
                    bad.append(f"{name}.capture_pct")
                if s["pass_both"] != (cap >= CAPTURE_MIN and s["delta_pp"] > DELTA_MIN):
                    bad.append(f"{name}.pass_both")
            print("内核算术:", "PASS" if not bad else f"FAIL {bad}")
            return 1 if bad else 0
        print(f"⛔ 既无 records/labels 也无 {ref}", file=sys.stderr)
        return 2

    tasks = load(run)
    got = compute(tasks)
    print(json.dumps(got, ensure_ascii=False, indent=1))
    bad = check_against(got, ref) if ref.exists() else []
    if bad:
        print("⛔ 与已发布 selector_eval_extra.json 不一致：", file=sys.stderr)
        for x in bad:
            print("   -", x, file=sys.stderr)
        return 1
    if ref.exists():
        print(f"✓ 与已发布 {ref.name} 逐项一致")
    if not a.check:
        out = a.out or (run / "selector_eval_extra.json")
        out.write_text(json.dumps(got, indent=1, ensure_ascii=False), encoding="utf-8")
        print("→", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
