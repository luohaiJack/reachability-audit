# reachability-audit v1 — 可达性税审计仪器

[![instrument-ci](https://github.com/luohaiJack/reachability-audit/actions/workflows/ci.yml/badge.svg)](https://github.com/luohaiJack/reachability-audit/actions/workflows/ci.yml)
　**CI 在 GitHub 的干净机器上跑**：**23 臂复现** ＋ known-answer 控制 ＋ **8 例故障注入** ＋ 检测器自检 ＋ 探针离线复算 ＋ **插桩不变式控制** ＋ 决策边界（共 **7 步**）。**首跑 success**（2026-10-15T14:18:49Z）。

一个**零依赖**（只用 Python 标准库）的审计脚本：给它一个 BFCL 风格的
结果目录，它产出**一份标准化报告**，报告里把"官方分数"拆成
**① 执行且正确 / ② 执行但 harness 失败 / ③ 从未执行** 三桶，
并给出三个准确率与**七项**完整性门禁。

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
（被拒报文的算术位置，**注意：这是打印器构造值，见下**）、`gates`（七项）、
`gates_pass`。

**退出码**：`0` = 报告产出且门禁全过；`2` = 报告产出但门禁不过
（半成品臂 —— **禁止据此下判词**）；`2` 亦用于"未找到结果目录"。

## `reports/` 的覆盖范围

`reports/` 里共 **39 份** `*.tax_report.json`：其中 **23 份**对应随包 `slices/` 的臂
（可由 `reproduce.py` 零差异复现，均含 `G1b`），另 **16 份**属于**输入未随包**的臂或端口报告
（`expB_upstream`、`law_fresh160`、`law_llama31`、四份 `multiturn4_*`、四份 `pros_*`、
`smoke4`）以及 **4 份 τ² 端口报告**（port 8,192／llama 8,192／llama 32,768／llama 131,072／**qwen 131,072**）（由 `ports/tau2_tax_report.py` 生成，按设计只带两门）。
未随包的 16 份是历史留痕或端口报告，**不能**仅凭本包复现。

## τ² 同族窗口对（2026-10-16 补，L3'）

`tau2_retail_port_v1`（**Qwen3-4B** agent + Qwen3-4B user-sim @ **8,192**）与
`tau2_retail_qwen131072_v1`（**同族、同 user-sim** @ **131,072**）构成**只换窗口**的对：
前者 **3** 条 `ContextWindowExceededError`、后者 **0** 条（39/40 仿真完成，
最后一条超出预算未跑完，已在论文披露）；survivor reward 0.0714 → 0.0667。
注意 131,072 **超出 Qwen3-4B 声明的 40,960**，因此该臂必须改位置编码（论文已写明）。

## 未完成的一次尝试（τ² 2×2，2026-10-16 留痕）

为把 τ² 那一格从 "policy configuration" 收紧到 "agent policy"，我们试过**固定 8,192 窗口、
把 agent 与 user-sim 分别换族**的 2×2。**两次尝试均失败**：第一次 Llama 端口引擎 OOM；
第二次双端口都起来了（单独 chat/tools 探针 200），τ² 仍全量
`litellm.InternalServerError`（40/40、30/33）。原因未核实。
⇒ 该 2×2 **未产出可用数据**，本包**不含**这两条臂；论文相应措辞**维持**在
"the policy configuration we ran there"。

## 一条臂的降级与如实披露（2026-10-16）

`matrix_A2_ctx65536_b_v1`（65,536 档第二次）的 40 条结果里 **17 条是 `Connection error`**：
按"边界报文"数它拒了 **6** 条（税 0.15），按仪器的 **never-executed 桶**是 **23/40**（税 0.575）。
两者都在 `expected_reports.json`/`reports/` 里可查。论文据此**把该对排除在"同配置重跑"
比较之外**，并同时报出两个口径 —— 本包不掩盖它。

## 判分文件是**部分清单**（口径说明，2026-10-16 补）

BFCL 的 `official_score.jsonl` 记录的是**被判分的条目**，不是全部题目：
23 条臂里 **22 条**的判分条目数少于结果行数（例：`matrix_A2r_…` 40 行结果 / 36 条判分；
`env2_*` 80 行 / 23–26 条），只有 `matrix_A3_ctx24576aligned_v1` 是 40 行 / 40 条判分。

### ⚠️ 该臂的一个口径陷阱（第八轮第二刀 F7，2026-10-16 补）

`matrix_A3_ctx24576aligned_v1` 的 40 条结果里 **33 条是窗口边界报文、7 条是 `list`（真正执行过）**，
但它的**审计桶 b3 = 40/40**（税 1.0）。原因：仪器把 `official_score.jsonl` 记的
`inference_error` 一律算作"未执行"，而该臂的判分档把 7 条 `list` 行也计成了 error。
⇒ **不要把 `matrix_A3_…` 当作"全 40 条都咬窗"的例子**；论文未引用该臂，
此处仅作口径留痕（同类口径问题在 `matrix_A2_ctx65536_b_v1` 上已按双列处理）。
⇒ **不能**把"结果题号 ⊆ 判分题号"当门禁（它在多数臂上必然触发，
反映的是判分器只列被判分条目的口径，而不是缺陷）。
仪器采用的方向门禁是 **`G6_no_orphan_score_ids`**（判分有、结果没有才算缺陷）。
另外 4 个 `env*` 臂的切片目录**同时含两个子榜**的结果文件
（`miss_func` 与 `miss_param`），当前无害（`b3=0`、`G4` 过），但阅读时需注意类别。

## 七项完整性门禁（`gates`）

| 门禁 | 断言 | 为什么 |
|---|---|---|
| `G1_rows_present` / `G1_rows_count` | 有原始行，并报出条数 | 空目录不得产出"0% 税"的假报告 |
| `G1b_result_files_not_empty` | 结果文件**存在就不得为 0 行** | F6 用例抓出的缺口：被清空的产物原先被当"无原始结果"跳过 |
| `G2_done_marker` | 找到 chain 日志就必须有 `DONE` | 半成品臂的最大来源；无日志记"不适用"，**不算否证** |
| `G3_boundary_invariant_single` | 被拒报文的 `out+in` 取值唯一**且等于 `W_s+1`** | 混臂检测＋恒等式（F4 用例抓出的缺口）|
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
仪器把这些字段标为 **constructed**（构造值），并在报告里与"实测"分开呈现。

## 适用范围与不适用范围

- **适用**：任何"客户端把请求发给服务端、服务端可能因窗口硬拒、
  而官方判分只看最终状态"的 harness，只要它保留逐条结果文件与官方判分输出。
- **不适用**：没有逐条 rollout 记录的评测；分数由人工打分得到的评测；
  非 BFCL 风格的目录布局（需要改 `load_rows` / `load_score` 两个函数，
  见 `SCHEMA.md` §移植）。

## 复现论文数字（第三方最短路径）

```bash
python3 reproduce.py            # 只用随包切片 slices/，不需要任何外部数据
python3 reproduce.py --workspace <工作区根>     # 若你有原作者的完整 results/ 树
```

`slices/` 收录了 `expected_reports.json` 里 **23 条臂**的**输入切片**
（每臂的 `*_result.json` 与 `official_score.jsonl`，共约 **40 MB**），
所以拿到包就能跑，**不需要 8 GB 的原始数据树**。

预期输出（2026-10-16 本地实测）：

```
[OK  ] matrix_w49152_v1                               (bundle)

23 臂重跑（工作区 0 / 随包切片 16），差异 0 处
```

逐臂的位移（`tax_cost_pp`，23 条臂）：
`87.5, 70.0, 47.1, 46.7, 40.0, 31.2, 30.0, 18.6, 17.5, 15.0, 9.6, 0 ×5`
（**非零 11 条**，中位 18.05）。

运行时会先把被审计目录复制到临时目录，**不会改动本包**。

`reproduce.py` 对 `expected_reports.json` 里列出的 **23 条臂**重跑仪器，
并逐字段比对（三桶、三个准确率、税损失 pp）。预期：

```
23 臂：官方→条件 位移 pp = 87.5, 70.0, 47.1, 46.7, 40.0, 31.2, 30.0, 18.6,
                       17.5, 15.0, 9.6, 0, 0, 0, 0, 0
      非零 11 条，中位 18.05
```

## 仪器的有效性证据（不是"自洽"）

| 手段 | 命令 | 证明什么 |
|---|---|---|
| **known-answer 控制** | `python3 bfcl_tax_report.py --selftest` | 植入已知三桶（含"被叫停但达标"的第四格），断言逐字段一致 |
| **故障注入 8 例** | `python3 fault_inject.py` | **1 例空对照 ＋ 6 例已知破坏 ＋ 1 例有意降级**：每个破坏都被**指定的门禁**抓到（rc=2 且失败门禁名恰为预期集），缺 `official_score` 时**明示**为降级而非漏网 |
| **报文检测器自检** | `python3 tools/report_forensics.py selftest` | 三条真实报文 → constructed / non_tautological / absent |
| **探针离线复算** | `python3 tools/report_forensics.py probe --replay inputs/m1_probe_fixture.json` | `measured` **不需要活体服务**也能复现 |
| **决策边界** | `DSH_AUDIT_ROOT=/tmp/x python3 tools/audit_power.py` | 用随包 `inputs/` 离线复算 |
| **CI** | `.github/workflows/ci.yml`（**已启用，首跑 success**）| 以上全部在 GitHub 的干净机器上每次 push 自动跑 |

★ **报告与仪器同版**：`reports/` 下除 τ² 两条（由端口 `ports/tau2_tax_report.py` 生成，本就只带两门）
外，**全部报告由当前仪器重新生成**，因此每份都含最新的 `G1b` 门禁 —— 交付的报告就是交付的仪器产出的。

★ **决策规则一行判定**：`python3 tools/audit_power.py --check <τ_A> <τ_B> <观测差pp>` → 打印许可/不许可，退出码 **0=许可 / 3=不许可**。

★ 故障注入本身**发现并修好了两个真缺口**：其一 `G3` 原本只查"被拒报文的 `out+in` 取值是否唯一"
（能抓混臂，抓不到"所有报文一致地偏离恒等式"）；现改为**再用报文里的窗口值逐条核 `in+out==W+1`**。
—— 这就是"有效性证据"与"自洽复现"的区别。

## 许可

**MIT** —— 见 [`LICENSE`](LICENSE)。

你可以自由使用、修改、分发、商用，**唯一要求**：
在副本或衍生作品里**保留版权声明与这份许可全文**
（即"要署名"）。代码、报告与派生数据都按 MIT 提供。

被审计的**第三方**产物（BFCL / τ²-bench / ToolSandbox 的原始轨迹）
**不随本库分发**，其权利归各自发布方，引用时请遵循其原始许可。

引用本仓库请用 `CITATION.cff`（若有）或论文条目；`reports/` 里的每个数字都可追到论文的对应小节。

## 一个已完成的移植样例：τ²-bench

`ports/tau2_tax_report.py` 是把本仪器移植到 **τ²-bench 官方 harness** 的完整改动：
重写了 `load_rows()`（读 `results.json` 的 `simulations[]`）与 `load_score()`
（τ² 的"分"是 `reward_info.reward`，终止原因在 `termination_reason`），
**并改了两处内容**：③ 桶判据换成 `termination_reason == "infrastructure_error"`；
门禁只带 **2/7**（G1/G5，其余四门 τ² 产物里没有对应输入）。
三桶与三个率的**定义**未改。

映射：③ 从未执行 = `termination_reason == "infrastructure_error"`；
① 执行且对 = 跑到判分且 `reward == 1`；② 其余。

⇒ 结论要说得比初稿更窄：**读数口径（三桶＋三个率）是可移植的**，
但"只改两个取数函数"**不成立**——真值映射与可用门禁都要重写。

## 随包工具（`tools/`）

| 脚本 | 作用 | 论文位置 |
|---|---|---|
| `tools/report_forensics.py` | **报文字段取证**。两套词表：`classify`（单条报文）→ **constructed / non_tautological / absent**；`probe`（同提示 × 不同额度矩阵）→ **constructed / measured / unclear**；`selftest` 自带三条真实报文断言 | §5.5 |
| `tools/field_census.py` | 把田野普查做成**带分母**的形式（可审计比例、税分布、派别） | §sec:schools |
| `tools/audit_power.py` | **决策边界** $\Delta_{\max}=100(\tau_A+\tau_B)$ pp：多小的分差不能当能力证据 | §sec:power |

**判据速记**：
- `classify`（单条报文）：`constructed` = 输入长度满足 `in + out == W + 1`（额度的余数，
  **不含**请求信息）；`non_tautological` = 不是那个恒等式；`absent` = 报文里没有计数。
- `probe`（矩阵，需要活体栈）：`measured` = 同一提示下该数**不随**额度变、随提示长度变；
  `constructed` = 随额度联动；`unclear` = 两者都不是。
- **单条报文判不出 `measured`**——这一步必须跑矩阵。

## 离线可跑（第三方）

```bash
DSH_AUDIT_ROOT=/tmp/scratch python3 tools/audit_power.py   # 用随包 inputs/ 的冻结输入
python3 tools/report_forensics.py selftest                 # 三条真实报文断言
```

`inputs/` 随包带了 `tax_report_all.json` 与 `field_scan.json`（44 KB），
所以 `audit_power.py` **不需要作者的数据树**就能跑。
`field_census.py` 需要 τ² 官方榜的 `submissions/` 检出（该仓库 MIT，可公开克隆）；
本包只带它的**输出** `reports/field_census_v1.census.json`。
`DSH_AUDIT_ROOT` 可指向任何数据树根，用于覆盖脚本默认的工作区路径。
