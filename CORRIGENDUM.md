# Corrigendum · A3 臂（2026-10-19）

**改了什么**：`slices/matrix_A3_ctx24576aligned_v1/official_score.jsonl` 从旧件（40 行全 `valid:false`，
`accuracy 0.0`）换成按该臂 `result` 文件重评的 score（**accuracy 0.10，4/40**；33 条 `inference_error`
＋2 条 `instance_state_mismatch`＋1 条 `empty_turn_model_response`）。

**为什么**：旧 score 写于 2026-10-14 01:44，`result` 写于 01:51（rerun 之后）；两者不一致，
导致本包的 A3 报告记 `b3=40、tax=1.0、official=0.0`，与同包 slice 的 result（33 条超窗＋7 条真执行）
自相矛盾。重评后三桶为 **①4 / ②3 / ③33**、税 **0.825**、官方 **0.10**、条件 **0.5714**、税损失 **47.1 pp**。

**影响的文件**：
- `slices/matrix_A3_ctx24576aligned_v1/official_score.jsonl`（换新）
- `reports/matrix_A3_ctx24576aligned_v1.tax_report.json`（重生成）
- `expected_reports.json`（A3 条目改为 4/3/33、0.1、0.5714、47.1）
- `MANIFEST.sha256`（按 README §MANIFEST 生成口径重算）

**不变**：其余臂、工具、协议、README/SCHEMA 均未改；本目录是 `v1` 的旁支版本，
`artifact_reachability_audit_v1/` 原样保留（冻结件不就地改）。

**复现**：`python3 reproduce.py` ⇒ 全部臂与 `expected_reports.json` 一致（A3 现为 4/3/33）。
