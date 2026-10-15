# 交付记录（已执行）

## 现状

- **仓库**：https://github.com/luohaiJack/reachability-audit （公开）
- **首次提交**：`reachability-audit v1: three-bucket accounting, tax, diagnostic-tautology classifier`
- 正文 `Data availability` 已填入该地址。
- 包内自检：`sha256sum -c MANIFEST.sha256`（11 项）通过；
  `python3 reproduce.py --workspace <WS>` 对 10 条臂重跑 **0 差异**。

## 内容

| 目录/文件 | 内容 |
|---|---|
| `bfcl_tax_report.py` | 主仪器（零依赖）：三桶 + 三个率 + 六门禁 + 退出码 |
| `tools/report_forensics.py` | **报文字段检测器**：`constructed / measured / absent` |
| `tools/field_census.py` | 田野普查（带分母：可审计比例、税分布、派别） |
| `tools/audit_power.py` | **决策边界** $\Delta_{\max}=100(\tau_A+\tau_B)$ pp |
| `ports/tau2_tax_report.py` | τ² 官方 harness 的移植样例 |
| `reports/` | 每条臂的 `tax_report.json`（+ τ² 与第三基准的判定 json） |
| `examples/`、`SCHEMA.md`、`reproduce.py` | 样例、字段语义、复现脚本 |

## 仍需人工完成的两件

1. ~~**许可**~~ **已完成（2026-10-15）**：`LICENSE`（MIT，Hai Luo and He Wang）＋ `LICENSE-DATA`（CC BY 4.0 全文）。
   确认后写入即可。
2. **DOI**：Zenodo → Settings → GitHub → 打开 `reachability-audit` 开关 →
   在 GitHub 建一个 **Release**（本仓库已有 token 可建）→ Zenodo 自动归档并发 DOI →
   把 DOI 补进论文 `Data availability`。

## 安全提示

写入本仓库所用的 **token 已暴露在对话记录里**，用完请到
`https://github.com/settings/tokens` **立即吊销**。
