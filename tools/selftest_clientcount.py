#!/usr/bin/env python3
"""selftest_clientcount.py — 客户端计数插桩的**已知答案/不变式控制**。

回答"你的插桩有没有被验证过"。对每条**已落盘**的请求记录逐条核 5 条不变式
（这些不变式全部来自 `base_oss_handler.py:277-296` 的源码语义）：

  I1  `W_client` 在每个臂内**唯一**，且等于该臂配置的窗口；
  I2  落 1000 回退支 ⇔ `n_client ≥ W−1`（源码：`W < n+2` ⇒ 回退）；
  I3  **不**落回退支 ⇒ `n_client < W−1` 且 `allowance == min(4096, W−n−2)`；
  I4  `status=error` 且报文含 "maximum context length" ⇒ 必落回退支；
  I5  报文里的 `requested` 与回退支的 1000 一致（构造值的另一面）。

用法： python3 code/selftest_clientcount.py
退出码：0 = 全部不变式成立；1 = 有不成立
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

def _find(root: pathlib.Path, arm: str) -> pathlib.Path | None:
    """先找工作区数据树，再找随包切片（两种布局都能跑）。"""
    for cand in (root / "results" / "bfcl" / arm, root / "slices" / arm):
        if (cand / "client_requests.jsonl").exists():
            return cand
    return None


ARMS = {
    "matrix_A2r_ctx40960_clientcount_v1": 40960,
    "matrix_A2_ctx65536_v1": 65536,
    "matrix_S4_qwen3_8b_ctx40960_v1": 40960,
}


def check_arm(d: pathlib.Path, W: int) -> tuple[int, list[str]]:
    rows = [json.loads(l) for l in (d / "client_requests.jsonl").read_text().splitlines() if l.strip()]
    bad: list[str] = []
    ws = {r.get("W_client") for r in rows}
    if ws != {W}:
        bad.append(f"I1 W_client 不唯一: {ws}")
    for i, r in enumerate(rows):
        n, fb, allow = r["n_client"], r["fallback_1000"], r.get("allowance")
        if fb != (n >= W - 1):
            bad.append(f"I2 行{i}: n={n} fb={fb}")
        if not fb:
            if not (n < W - 1) or allow != min(4096, W - n - 2):
                bad.append(f"I3 行{i}: n={n} allow={allow} 期望 {min(4096, W - n - 2)}")
        msg = r.get("server_message") or ""
        if r.get("status") == "error" and "maximum context length" in msg and not fb:
            bad.append(f"I4 行{i}: 窗口拒绝但未落回退支")
        m = re.search(r"requested (\d+) output tokens", msg)
        if m and fb and int(m.group(1)) != 1000:
            bad.append(f"I5 行{i}: 报文 requested={m.group(1)} 与回退支不符")
    return len(rows), bad


def main() -> int:
    total_bad = 0
    for arm, W in ARMS.items():
        d = _find(pathlib.Path(__file__).resolve().parents[1], arm)
        if d is None:
            print(f"[SKIP] {arm}（无产物）")
            continue
        n, bad = check_arm(d, W)
        total_bad += len(bad)
        print(f"[{'OK  ' if not bad else 'FAIL'}] {arm:42s} W={W} 请求={n} 违例={len(bad)}")
        for b in bad[:3]:
            print("       ", b)
    print("selftest_clientcount", "PASS" if not total_bad else f"FAIL ({total_bad})")
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
