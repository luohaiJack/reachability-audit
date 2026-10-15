#!/usr/bin/env python3
# bfcl_tax_report.py — 可达性税审计仪器（论文 C1/C2/C3/C5 的可复用封装）
# ============================================================================
# 目的：给**任意** BFCL 风格的结果目录产出一份标准化审计报告——
#   ① 三桶记账：①执行且正确 / ②执行但 harness 失败 / ③未执行（窗口截断）
#   ② 三个准确率：官方 / 条件（只在执行成功的样本上）/ 可达性税
#   ③ 边界签名检测：从失败报文反推 (W_c, W_s) 与阈值带位置（C3）
#   ④ 完整性门禁：行数、DONE 标记、报文恒等式、官方分与逐条账的一致性（C5）
#
# 用法：
#   python3 code/bfcl_tax_report.py <结果目录> [<结果目录> ...]
#   python3 code/bfcl_tax_report.py results/bfcl/law_mismatch32768_v1 --markdown
#   python3 code/bfcl_tax_report.py results/bfcl/law_*_v1 --out results/bfcl/tax_report.json
#
# 退出码：0 = 报告产出且门禁通过；2 = 报告产出但门禁不过（半成品臂，禁止下判词）
# 纪律：本仪器**只读数、不改数**；不写任何上游文件，输出默认落在 <dir>/tax_report.json
# ============================================================================
import argparse, collections, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
# 判定"未执行"的两种独立证据：结果文件里的错误串 / 官方 score 里的 error_type
BOUNDARY_RE = re.compile(r"requested (\d+) output tokens and your prompt contains at least (\d+) input tokens")
# 2026-10-15（故障注入 F4 发现）：G3 原本只查"取值是否唯一"，"所有报文一致地偏离恒等式"抓不到 ⇒ 再抓一次窗口值，能抓到就核 in+out==W+1。
WINDOW_RE = re.compile(r"maximum context length is (\d+) tokens", re.I)
INFERENCE_ERR = "multi_turn:inference_error"


def collect_dirs(args):
    out = []
    for a in args:
        p = pathlib.Path(a)
        if p.is_absolute() or (ROOT / a).exists():
            p = p if p.is_absolute() else ROOT / a
            if p.is_dir():
                out.append(p)
                continue
            # 支持 shell 未展开的 glob
            out += sorted(x for x in p.parent.glob(p.name) if x.is_dir())
    return sorted(set(out))


def load_rows(d):
    """逐条结果文件（可多份，例如 arm 内多个子榜）；返回 [(任务号, {record})]"""
    rows, files = [], []
    for f in sorted(d.rglob("*_result.json")):
        files.append(f)
        for ln in f.read_text(errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:
                continue
            tid = str(r.get("id", "")).rsplit("_", 1)[-1]
            try:
                tid = int(tid)
            except ValueError:
                pass
            rows.append((tid, r))
    return rows, files


def load_score(d):
    """官方判分记录：{任务号: error_type}（收录 = 官方记错）；返回 (dict, 表头, 路径)"""
    for f in sorted(d.rglob("official_score.jsonl")):
        recs, head = {}, None
        for ln in f.read_text(errors="replace").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            r = json.loads(ln)
            if "id" not in r:
                head = head or r
                continue
            recs[int(str(r["id"]).rsplit("_", 1)[-1])] = (r.get("error") or {}).get("error_type") or "NO_ERROR"
        return recs, head, f
    return {}, None, None


def done_marker(d):
    """DONE 标记：找不到 chain 日志 ⇒ 返回 None（不适用，**不算门禁失败**）。
    只有"找到了日志但没有 DONE"才是有信息量的否定证据。"""
    keys = {d.name, d.name[:-3] if d.name.endswith("_v1") else d.name}
    cands = sorted(set(list(d.parent.glob("*_chain.log")) + list(d.rglob("*_chain.log"))))
    found_log = False
    for f in cands:
        txt = f.read_text(errors="replace")
        if any(f"{k}_DONE" in txt for k in keys):
            return f
        if any(k in f.name for k in keys) or any(k in txt[:2000] for k in keys):
            found_log = True
    return False if found_log else None


def _empty_result_files(d) -> list:
    """结果文件**存在但 0 行**（0 字节或被清空）⇒ 破损件，不是"没跑"。

    与"根本没有结果文件"不同：后者是"这个目录不是一条臂"（判词/图/台账），可以跳过；
    前者是**被清空/截断的产物**，必须判失败（夜间值守事故 F6 的直接教训）。
    """
    out = []
    for f in pathlib.Path(d).rglob("*_result.json"):
        try:
            if not [ln for ln in f.read_text(errors="replace").splitlines() if ln.strip()]:
                out.append(str(f.relative_to(pathlib.Path(d))))
        except OSError:
            out.append(str(f))
    return out


def report_dir(d):
    rows, files = load_rows(d)
    score, head, score_f = load_score(d)
    ids = [t for t, _ in rows]
    all_ids = set(ids)
    # 边界报文（未执行的第一手证据）
    bt, ws_seen = [], set()
    for _, r in rows:
        res = r.get("result")
        if isinstance(res, str):
            bt += [(int(a), int(b)) for a, b in BOUNDARY_RE.findall(res)]
            ws_seen |= {int(x) for x in WINDOW_RE.findall(res)}
    ins = sorted({b for _, b in bt})
    outs_inv = sorted({a + b for a, b in bt})
    # 三桶
    never = {t for t in all_ids if score.get(t) == INFERENCE_ERR}
    if not score:  # 无官方 score ⇒ 退化：只认结果文件错误串
        never = {t for t, r in rows if isinstance(r.get("result"), str) and BOUNDARY_RE.search(r["result"])}
    wrong = set(score) if score else set()
    harness = wrong - never
    correct = all_ids - wrong if score else set()
    # 无官方 score ⇒ 执行题的结果无法判定，单列"不可判"桶，**不假装 b1=0**
    executed_unscored = (all_ids - never) - correct if not score else set()
    n = len(all_ids) or 1
    # 配置签名反推
    mode, w_s_est, band = "unknown", None, None
    if ins:
        if len(ins) == 1:
            mode, w_s_est, band = "aligned", ins[0] + 999, f"恒 {ins[0]}（= W_s−999）"
        else:
            mode, band = "mismatch", f"{min(ins)}…{max(ins)}（需 ≥ W_s−4096 且分散）"
        if outs_inv and len(outs_inv) == 1:
            w_s_est = (w_s_est or 0) or (outs_inv[0] - 1)
    acc = head.get("accuracy") if head else None
    acc_from_rows = (len(correct) / n) if score else None   # ★不四舍五入（G4 与官方分逐位比对；本夜修）
    # 完整性门禁（C5）
    dm = done_marker(d)
    gates = {
        "G1_rows_present": len(rows) > 0,
        "G1_rows_count": len(rows),
        "G2_done_marker": dm is True or dm is None or bool(dm),  # None=不适用（无日志），不算否证
        # 唯一性（同配置）＋ 若报文可解析出 W：逐条核 in+out == W+1
        "G1b_result_files_not_empty": not _empty_result_files(d),
        "G3_boundary_invariant_single": len(outs_inv) <= 1 and (
            not ws_seen or all((o + i) == (w + 1) for o, i in bt for w in ws_seen)),
        "G4_score_matches_rows": (acc is None or acc_from_rows is None or abs(acc - acc_from_rows) < 1e-9),
        "G5_bucket_partition": len(never & harness) == 0 and (not score or len(correct) + len(never) + len(harness) == len(all_ids)),
        "G6_no_orphan_score_ids": (not score or set(score) <= all_ids),
    }
    gates_pass = all(v for k, v in gates.items() if k.startswith("G") and isinstance(v, bool))
    return {
        "schema": "bfcl_tax_report_v1",
        "dir": str(d.relative_to(ROOT)) if str(d).startswith(str(ROOT)) else str(d),
        # 2026-10-15：被审计目录在工作区之外时（第三方拿包直接跑）不得抛 ValueError
        "result_files": [str(f.relative_to(ROOT)) if str(f).startswith(str(ROOT)) else str(f)
                         for f in files],
        "score_file": (str(score_f.relative_to(ROOT))
                       if score_f and str(score_f).startswith(str(ROOT)) else
                       (str(score_f) if score_f else None)),
        "n_total": len(all_ids),
        "buckets": {
            "b1_executed_correct": len(correct),
            "b2_executed_harness_failed": len(harness),
            "b3_never_executed_boundary": len(never),
            "b2_task_ids": sorted(harness)[:60],
            "b3_task_ids_count": len(never),
        },
        "rates": {
            "official_accuracy": acc if acc is not None else acc_from_rows,
            "conditional_accuracy": round(len(correct) / max(len(correct) + len(harness), 1), 4) if score else None,
            "reachability_tax": round(len(never) / n, 4),
            # 税造成的分数损失（百分点）= 条件准确率 − 官方准确率
            "tax_cost_pp": round((len(correct) / max(len(correct) + len(harness), 1) - len(correct) / n) * 100, 1) if score else None,
        },
        "signature": {
            "mode": mode, "W_s_estimate": w_s_est, "band_position": band,
            "distinct_input_tokens": ins[:20], "n_boundary_msgs": len(bt),
            "invariant_out_plus_in": outs_inv,
        },
        "error_type_census": dict(sorted(collections.Counter(score.values()).items())) if score else {},
        "b_unknown_executed_unscored": sorted(executed_unscored),
        "gates": gates, "gates_pass": gates_pass,
    }


def render(r):
    b, rt, sg = r["buckets"], r["rates"], r["signature"]
    L = [f"══ {r['dir']} ══",
         f"样本 {r['n_total']} | ①执行且对 {b['b1_executed_correct']} | "
         f"②执行但 harness 失败 {b['b2_executed_harness_failed']}{b['b2_task_ids'][:8]} | "
         f"③未执行(截断) {b['b3_never_executed_boundary']}",
         f"官方准确率 {rt['official_accuracy']} | 条件准确率(仅执行成功) {rt['conditional_accuracy']} | "
         f"可达性税 {rt['reachability_tax']} | 税造成的损失 {rt['tax_cost_pp']} pp"
         + (f" | ⚠️ 不可判(无 score) {len(r['b_unknown_executed_unscored'])}" if r['b_unknown_executed_unscored'] else ""),
         f"签名: {sg['mode']} | W_s≈{sg['W_s_estimate']} | 带位置 {sg['band_position']} | "
         f"报文恒等式 out+in ∈ {sg['invariant_out_plus_in']}",
         f"error_type: {r['error_type_census']}",
         f"门禁: {'✅ 通过' if r['gates_pass'] else '⛔ 不过'} {[k for k, v in r['gates'].items() if isinstance(v, bool) and not v]}"]
    return "\n".join(L)


BOUNDARY_MSG = ("This model's maximum context length is 8192 tokens. However, you requested 0 "
                "output tokens and your prompt contains at least 8193 input tokens.")


def selftest() -> int:
    """known-answer 控制：植入已知的三桶，断言仪器算出来的与植入值**逐字段**一致。

    这是对"复现脚本只能证明自洽"的回应——本控制有**已知正确答案**，
    而且刻意包含那个反例：**被窗口叫停但最终状态达标的 rollout**（第四格），
    它必须落进 b1（执行且正确），不能落进 b3。
    """
    import tempfile
    cases = [
        # (名称, 正确答案数, 执行但失败数, 从未执行数, 第四格：停机但达标)
        ("planted_basic", 6, 2, 2, 0),
        ("planted_fourth_cell", 5, 2, 2, 1),
    ]
    bad = 0
    for name, n_ok, n_wrong, n_never, n_stop_ok in cases:
        with tempfile.TemporaryDirectory() as td:
            d = pathlib.Path(td) / name
            d.mkdir(parents=True)
            rows, score = [], []
            tid = 0
            def mkrec(i, payload):
                return json.dumps({"id": f"multi_turn_long_context_{i}", "result": payload})
            for _ in range(n_ok + n_stop_ok):
                rows.append(mkrec(tid, ["ok"])); tid += 1
            for _ in range(n_wrong):
                rows.append(mkrec(tid, ["wrong"])); score.append(
                    {"id": f"multi_turn_long_context_{tid}",
                     "error": {"error_type": "multi_turn:instance_state_mismatch"}}); tid += 1
            for _ in range(n_never):
                rows.append(mkrec(tid, BOUNDARY_MSG)); score.append(
                    {"id": f"multi_turn_long_context_{tid}",
                     "error": {"error_type": "multi_turn:inference_error"}}); tid += 1
            (d / "arm_result.json").write_text("\n".join(rows) + "\n", encoding="utf-8")
            n = len(rows)
            acc = (n_ok + n_stop_ok) / n
            head = {"accuracy": acc}
            (d / "official_score.jsonl").write_text(
                json.dumps(head) + "\n" + "\n".join(json.dumps(x) for x in score) + "\n",
                encoding="utf-8")
            r = report_dir(d)
            got = (r["buckets"]["b1_executed_correct"], r["buckets"]["b2_executed_harness_failed"],
                   r["buckets"]["b3_never_executed_boundary"])
            want = (n_ok + n_stop_ok, n_wrong, n_never)
            ok = got == want and r["gates_pass"]
            bad += 0 if ok else 1
            print(f"[{'OK  ' if ok else 'FAIL'}] {name}: buckets={got} want={want} "
                  f"tax={r['rates']['reachability_tax']} official={r['rates']['official_accuracy']} "
                  f"gates={'pass' if r['gates_pass'] else 'FAIL'}")
    print("selftest", "PASS" if not bad else f"FAIL ({bad})")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="*")
    ap.add_argument("--out", default=None, help="合并报告的输出路径（默认各目录内 tax_report.json）")
    ap.add_argument("--markdown", action="store_true", help="额外打印 markdown 表")
    ap.add_argument("--selftest", action="store_true",
                    help="known-answer 控制：人工构造两个臂，断言三桶/三个率与植入值一致")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.dirs:
        ap.error("需要至少一个结果目录（或 --selftest）")
    dirs = collect_dirs(a.dirs)
    if not dirs:
        print("⛔ 未找到结果目录", file=sys.stderr)
        return 2
    reports, skipped = [], []
    for d in dirs:
        r = report_dir(d)
        if r["n_total"] == 0 and not _empty_result_files(r["dir"]):
            # **没有**原始结果的目录（判词/图/台账）⇒ 跳过，不算门禁失败；
            # 但"结果文件存在却被清空"**不跳过** ⇒ 由 G1b 判失败（F6 用例）
            skipped.append(r["dir"])
            continue
        reports.append(r)
        print(render(r))
        (d / "tax_report.json").write_text(json.dumps(r, indent=1, ensure_ascii=False))
    if skipped:
        print(f"（跳过 {len(skipped)} 个无原始结果的目录）")
    if a.out:
        p = pathlib.Path(a.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(reports, indent=1, ensure_ascii=False))
        print("合并报告:", p)
    if a.markdown:
        print("\n| 臂 | n | ①对 | ②harness错 | ③未执行 | 官方 | 条件 | 税 | 签名 |")
        print("|---|---|---|---|---|---|---|---|---|")
        for r in reports:
            b, rt, sg = r["buckets"], r["rates"], r["signature"]
            print(f"| {pathlib.Path(r['dir']).name} | {r['n_total']} | {b['b1_executed_correct']} | "
                  f"{b['b2_executed_harness_failed']} | {b['b3_never_executed_boundary']} | "
                  f"{rt['official_accuracy']} | {rt['conditional_accuracy']} | {rt['reachability_tax']} | {sg['mode']} |")
    return 0 if all(r["gates_pass"] for r in reports) else 2


if __name__ == "__main__":
    sys.exit(main())
