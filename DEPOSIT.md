# 交付步骤（作者执行；本机无法上传）

本目录已经**可以直接打包上传**：自包含、零依赖、附复现脚本。

## 1. 选择托管

| 选项 | 适用 | 注意 |
|---|---|---|
| GitHub 仓库 + Zenodo 归档（推荐） | 要 DOI | GitHub release → Zenodo 集成，自动发 DOI |
| Zenodo 单独上传 | 只要 DOI、不要仓库 | 上传 `reachability-audit-v1.zip` |
| anonymous.4open.science | 双盲评审期 | 审稿期匿名，接收后换正式地址 |

## 2. 命令（在有网机器上）

```bash
cd /home/leli/Documents/新方向codex/agent实证研究
sha256sum -c artifact_reachability_audit_v1/MANIFEST.sha256   # 先自检
cd artifact_reachability_audit_v1 && zip -r ../reachability-audit-v1.zip . -x 'MANIFEST.sha256'
```

Zenodo：New upload → 选 `reachability-audit-v1.zip` → Resource type *Software* →
License（**需作者确认**：建议 MIT）→ Publish → 复制 DOI。

## 3. 回填两处（**不要忘**）

1. 论文 `Data availability`：把 `<REPO-OR-DOI>` 换成真实地址。
   **注意**：`verify_paper_numbers.py` 会对占位符给出 **WARN**（不判 FAIL，以免门禁长期发红），在
   看到 `<REPO-OR-DOI>` 时提醒一次；同时有一条硬守卫禁止 "upon reasonable request" 回流 —— 这是故意的，
   防止占位符被漏掉后投出去。
2. 本文件与 `README.md` 的许可行（把 `TBD` 改成确认后的许可）。

## 4. 打包内容清单

见 `MANIFEST.sha256`（每个文件的 sha256）。
