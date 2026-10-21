#!/usr/bin/env python3
"""v2：把 158 条 infrastructure_error 逐行留证（error_type / 时长 / 消息长度），
用于判断这些行是否可能是"累计载荷型窗口耗尽"（该机制要求在途 2–10 个请求，
故 0 时长、0 消息的崩溃在机制上不可能属于该机制）。只读缓存；零 GPU。"""
import json, glob, re, collections, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
CACHE = ROOT / "results/bfcl/field_scan_v1/traj_cache"
OUT = ROOT / "results/bfcl/field_infra_probe_v1"
DEC = json.JSONDecoder()
HARD = re.compile(r"context[_ ]length|maximum context|max_tokens|exceeds the maximum|"
                  r"context window|too many tokens|prompt is too long|400[^0-9]", re.I)


def iter_sims(path):
    txt = pathlib.Path(path).read_text(errors="replace")
    i = txt.find('"simulations"')
    i = txt.find('[', i) + 1
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


rows, et = [], collections.Counter()
durs, nmsg = [], []
for f in sorted(glob.glob(str(CACHE / "*.json"))):
    for s in iter_sims(f):
        if s.get("termination_reason") != "infrastructure_error":
            continue
        info = s.get("info") or {}
        if isinstance(info, str):
            info = {"raw": info}
        err = str(info.get("error", ""))
        et[str(info.get("error_type"))] += 1
        try:
            d = float(s.get("duration") or 0)
        except Exception:
            d = -1.0
        durs.append(d)
        nmsg.append(len(s.get("messages") or []))
        rows.append({"file": pathlib.Path(f).name, "task_id": s.get("task_id"),
                     "duration": d, "n_messages": len(s.get("messages") or []),
                     "error_type": str(info.get("error_type")), "error": err[:200],
                     "hard_hit": bool(HARD.search(err)),
                     "ticks_none": s.get("ticks") in (None, "None")})
res = {"schema": "field_infra_probe_v2", "n_infra": len(rows),
       "n_hard_hits": sum(r["hard_hit"] for r in rows),
       "error_type_counts": dict(et.most_common()),
       "duration_max": max(durs) if durs else None, "duration_min": min(durs) if durs else None,
       "n_duration_zero": sum(1 for d in durs if d == 0.0),
       "n_messages_zero": sum(1 for m in nmsg if m == 0),
       "n_messages_max": max(nmsg) if nmsg else None,
       "n_ticks_none": sum(r["ticks_none"] for r in rows),
       "rows": rows}
(OUT / "probe_v2.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps({k: v for k, v in res.items() if k != "rows"}, ensure_ascii=False, indent=1)[:2000])
