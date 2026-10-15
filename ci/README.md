# 启用 CI（需要 `workflow` 权限）

本目录里的 `ci.yml` 就是 `.github/workflows/ci.yml`。
它**没有**放在 `.github/workflows/`，原因很具体：写该路径需要 GitHub token 具备
**`workflow` scope**，而当前交付用的 classic token 只有 `public_repo`
（推送被 GitHub 拒绝：`refusing to allow a Personal Access Token to create or update workflow ... without workflow scope`）。

两种启用方式（任选）：

1. **网页**：在仓库里 New file → 路径填 `.github/workflows/ci.yml` → 粘贴本文件内容 → Commit。
2. **命令行**：给 token 加上 `workflow` scope（或新开一个带它的 token），然后
   ```bash
   mkdir -p .github/workflows && cp ci/ci.yml .github/workflows/ci.yml
   git add .github/workflows/ci.yml && git commit -m "enable CI" && git push
   ```

`ci.yml` 跑的六件：`reproduce.py`、`bfcl_tax_report.py --selftest`、`fault_inject.py`、
`tools/report_forensics.py selftest`、`probe --replay`、`audit_power.py`。
