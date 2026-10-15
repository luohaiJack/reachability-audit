# reachability-audit v1 — 可达性税审计仪器

一个**零依赖**（只用 Python 标准库）的审计脚本：给它一个 BFCL 风格的
结果目录，它产出**一份标准化报告**，报告里把"官方分数"拆成
**① 执行且正确 / ② 执行但 harness 失败 / ③ 从未执行** 三桶，
并给出三个准确率与六项完整性门禁。

本目录是论文 *Execution-window hazard and reachability* 所描述仪器的可交付副本。

## 为什么需要它

官方判分器（BFCL v4 及同类）的分数只由**结果标签**算出，标签里
**不含执行状态**：一条"被守卫叫停"的轨迹和一条"跑完但答错"的轨迹，
在分数上完全一样。于是"分数低"既可能是模型差，也可能是**执行根本没跑完**。
本仪器用 harness 已经记录的**逐请求记录**把两者分开。

## 用法

```bash
# 单臂：在结果目录里写 tax_report.json，并打印人类可读报告
python3 bfcl_tax_report.py results/bfcl/law_mismatch32768_v1

# 多臂：合并报告 + markdown 表
python3 bfcl_tax_report.py results/bfcl/law_*_v1 --markdown --out audit_all.json
```

**输入**（必需两种；另可选读一个 chain 日志，仅用于 G2"DONE 标记"门禁）：

| 输入 | 从哪来 | 用途 |
|---|---|---|
| `*_result.json`（逐行 JSON） | BFCL 生成端每条 rollout 的原始记录 | 任务号、结果串（含被拒报文）；**未执行**的第一手证据 |
| `official_score.jsonl` | BFCL 官方判分器输出 | 官方记错的条目与 `error_type`；`accuracy` 表头 |

**输出**：`<结果目录>/tax_report.json`（schema 见 `SCHEMA.md`），字段包括
`buckets`（三桶）、`rates`（官方／条件／税／税损失 pp）、`signature`
（被拒报文的算术位置，**注意：这是打印器构造值，见下**）、`gates`（六项）、
`gates_pass`。

**退出码**：`0` = 报告产出且门禁全过；`2` = 报告产出但门禁不过
（半成品臂 —— **禁止据此下判词**）；`2` 亦用于"未找到结果目录"。

## 六项完整性门禁（`gates`）

| 门禁 | 断言 | 为什么 |
|---|---|---|
| `G1_rows_present` / `G1_rows_count` | 有原始行，并报出条数 | 空目录不得产出"0% 税"的假报告 |
| `G2_done_marker` | 找到 chain 日志就必须有 `DONE` | 半成品臂的最大来源；无日志记"不适用"，**不算否证** |
| `G3_boundary_invariant_single` | 被拒报文的 `out+in` 取值唯一 | 混臂检测 |
| `G4_score_matches_rows` | 官方 `accuracy` 与逐条重算**逐位**一致 | 防止"评错文件"（我们踩过） |
| `G5_bucket_partition` | 三桶互斥且覆盖全部题 | 桶不互斥 ⇒ 报告无意义 |
| `G6_no_orphan_score_ids` | 判分器里的题号 ⊆ 结果文件题号 | 归档/copy 事故检测 |

## ⚠️ `signature` 字段的正确读法（重要）

`signature` 从**服务端报错文本**里提取 `(out, in)`，用于识别
"注定被拒的请求"。但实测（论文 §2.2）表明：

> 报错文本里的 `input_token_count` **是构造值** `in ≡ W_s + 1 − out`，
> 由 `out` 反算，**不是对提示长度的测量**。

因此 `signature` **只能**用来识别"这批请求死在了窗口契约上"这一**事实**，
**不能**用来推断真实提示长度、阈值带位置或"边界几何"。
真实的死亡阈值只能从**客户端逐请求计数与输出额度**读出。
本目录的报告保留该字段仅为与旧产物兼容；论文已把该组件从
"签名检测"改名为 **dead-request detection**。

## 适用范围与不适用范围

- **适用**：任何"客户端把请求发给服务端、服务端可能因窗口硬拒、
  而官方判分只看最终状态"的 harness，只要它保留逐条结果文件与官方判分输出。
- **不适用**：没有逐条 rollout 记录的评测；分数由人工打分得到的评测；
  非 BFCL 风格的目录布局（需要改 `load_rows` / `load_score` 两个函数，
  见 `SCHEMA.md` §移植）。

## 复现论文数字

```bash
python3 reproduce.py --workspace <工作区根>     # 需要论文的 results/ 目录在场
```

`reproduce.py` 对 `expected_reports.json` 里列出的 **10 条臂**重跑仪器，
并逐字段比对（三桶、三个准确率、税损失 pp）。预期：

```
10 臂：官方→条件 位移 pp = 87.5, 70.0, 40.0, 30.0, 17.5, 0, 0, 0, 0, 0
      中位 8.75，非零 5 条
```

## 许可

| 内容 | 许可 | 文件 |
|---|---|---|
| 代码（`*.py`、`reproduce.py`、`tools/`、`ports/`） | **MIT** | [`LICENSE`](LICENSE) |
| 报告与派生数据（`reports/`、`expected_reports.json`、`examples/`） | **CC BY 4.0** | [`LICENSE-DATA`](LICENSE-DATA) |

被审计的**第三方**产物（BFCL / τ²-bench / ToolSandbox 的原始轨迹）**不随本库分发**，
其权利归各自发布方，引用时请遵循其原始许可。

引用本仓库请用 `CITATION.cff`（若有）或论文条目；`reports/` 里的每个数字都可追到论文的对应小节。

## 一个已完成的移植样例：τ²-bench

`ports/tau2_tax_report.py` 是把本仪器移植到 **τ²-bench 官方 harness** 的完整改动：
重写了 `load_rows()`（读 `results.json` 的 `simulations[]`）与 `load_score()`
（τ² 的"分"是 `reward_info.reward`，终止原因在 `termination_reason`），
**并改了两处内容**：③ 桶判据换成 `termination_reason == "infrastructure_error"`；
门禁只带 **2/6**（G1/G5，其余四门 τ² 产物里没有对应输入）。
三桶与三个率的**定义**未改。

映射：③ 从未执行 = `termination_reason == "infrastructure_error"`；
① 执行且对 = 跑到判分且 `reward == 1`；② 其余。

⇒ 结论要说得比初稿更窄：**读数口径（三桶＋三个率）是可移植的**，
但"只改两个取数函数"**不成立**——真值映射与可用门禁都要重写。

## 随包工具（`tools/`）

| 脚本 | 作用 | 论文位置 |
|---|---|---|
| `tools/report_forensics.py` | **报文字段取证**：喂一条 400 报文，判它的"输入长度"是 **constructed / measured / absent**；`probe` 子命令跑"同提示 × 不同额度"的矩阵 | §5.5 |
| `tools/field_census.py` | 把田野普查做成**带分母**的形式（可审计比例、税分布、派别） | §sec:schools |
| `tools/audit_power.py` | **决策边界** $\Delta_{\max}=100(\tau_A+\tau_B)$ pp：多小的分差不能当能力证据 | §sec:power |

**判据速记**（`report_forensics.py classify`）：
- `constructed`：报文里的输入长度满足 `in + out == W + 1` ⇒ 它是额度的余数，**不含**请求信息；
- `measured`：同一提示下该数**不随**额度变、随提示长度变；
- `absent`：报文里没有计数。
