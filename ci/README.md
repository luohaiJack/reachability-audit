# CI 已启用 ✅（2026-10-15）

`.github/workflows/ci.yml` 已由作者在网页端提交（commit `070b0084`），workflow `instrument-ci` 状态 **active**，**首跑 success**：
https://github.com/luohaiJack/reachability-audit/actions/runs/38750264156

本目录的 `ci.yml` 保留为**同内容的副本**（历史留痕），启用时不再需要。

> 背景：用命令行推 `.github/workflows/*` 需要 token 具备 `workflow` scope；当前交付 token 只有 `public_repo`，故当初改走网页端（浏览器会话不受 token scope 限制）。

## 追加步骤（2026-10-16）

`ci/ci.yml` 比仓库里那份多一步「插桩不变式控制」`python3 tools/selftest_clientcount.py`
（对三条复制臂 903 条请求核 5 条源码语义不变式）。
命令行推 `.github/workflows/*` 需要 token 具 `workflow` scope；当前交付 token 只有 `public_repo`
⇒ 请在网页端把这一步并入，或给一个带 `workflow` 的 token 由我推。
