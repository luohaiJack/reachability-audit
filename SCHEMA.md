# 报告 schema：`bfcl_tax_report_v1`

一份报告对应**一个结果目录**（= 一条臂 / 一个子榜 / 一次提交）。

```jsonc
{
 "schema": "bfcl_tax_report_v1",
 "dir": "results/bfcl/<arm>",          // 被审计目录
 "result_files": ["..."],              // 实际读到的逐行结果文件
 "score_file": "…/official_score.jsonl",
 "n_total": 40,                        // 去重后的任务数（三桶的分母）

 "buckets": {                          // ① 执行且正确 ② 执行但 harness 失败 ③ 从未执行
   "b1_executed_correct": 4,
   "b2_executed_harness_failed": 1,
   "b3_never_executed_boundary": 35,
   "b2_task_ids": [ … ],               // 最多 60 个，便于抽查
   "b3_task_ids_count": 35
 },

 "rates": {
   "official_accuracy": 0.1,           // 官方口径：③ 记在分母里算错
   "conditional_accuracy": 0.8,        // 条件口径：只在 ①+② 上算
   "reachability_tax": 0.875,          // ③ / n_total
   "tax_cost_pp": 70.0                 // 条件 − 官方，单位百分点
 },

 "signature": {                        // ⚠️ 打印器构造值，只用于"这条路死了"的事实判定
   "mode": "mismatch",                 // aligned / mismatch / unknown
   "W_s_estimate": 32768,
   "band_position": "28673…28673（…）",
   "distinct_input_tokens": [ … ],
   "n_boundary_msgs": 10,
   "invariant_out_plus_in": [32769]    // 若唯一 ⇒ 一批同配置的直死请求
 },

 "error_type_census": {"multi_turn:inference_error": 35},
 "b_unknown_executed_unscored": [],    // 无官方 score 时，执行了但判不了的题（**不假装 b1=0**）
 "gates": { "G1_rows_present": true, … },
 "gates_pass": true
}
```

## 字段语义

- **`b3_never_executed_boundary`** 的定义是"**有第一手证据表明这次执行没走到判分**"：
  优先用官方 `error_type = multi_turn:inference_error`；无官方 score 时退化为
  "结果串里出现服务端窗口拒绝报文"。**它是下界**，不是全部未执行样本。
- **`tax_cost_pp`** = 条件准确率 − 官方准确率。它是"改记账口径会让这个数字动多少"的直接读数。
- **`b_unknown_executed_unscored`**：没有官方判分时，仪器**不猜**这些题对错，单列出来。

## 移植到别的 harness（**三项，不是两项**）

1. `load_rows(d)`：把"逐条 rollout 记录"读成 `[(任务号, record)]`。
2. `load_score(d)`：把"官方判分输出"读成 `{任务号: error_type}`（`NO_ERROR` 表示判对）。
3. **③ 桶的判据**：怎么算"从未执行"。BFCL 用 `error_type == multi_turn:inference_error`；
   τ² 用 `termination_reason == "infrastructure_error"`。这是**真值映射**，各 harness 都不同。
4. 若该 harness 的窗口拒绝报文格式不同，改 `BOUNDARY_RE`（仅影响 `signature` 字段）。

**三桶与三个率的定义**与 harness 无关；**门禁则与可用输入绑定**——
τ² 移植只带得起 G1/G5，其余四门要的输入它没有。**不要声称未改的部分比你真改的多。**
