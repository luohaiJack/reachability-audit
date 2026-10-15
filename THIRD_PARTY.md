# 第三方组件与许可（合规声明）

**结论一句话**：本仓库**不分发**任何第三方项目的代码、权重或原始数据；
`reproduce.py` 只对**我们自己跑出来的结果文件**做重算。

## 我们**运行**过（未再分发）

| 项目 | 版本/来源 | 许可 | 我们怎么用 |
|---|---|---|---|
| **BFCL / Gorilla** | v4，`github.com/ShishirPatil/gorilla` | **Apache-2.0** | 用官方评测器跑多轮子榜，产出**我们自己的**结果文件 |
| **τ²-bench** | Sierra Research，`github.com/sierra-research/tau2-bench` | **MIT** | 用官方 CLI 跑 retail 40 题；`ports/tau2_tax_report.py` 是**我们写的**读法适配器 |
| **Apple ToolSandbox** | `github.com/apple/ToolSandbox` | **Apple Sample Code License** | 用未修改的 CLI 跑 37 场景（运行期重定向端点，未改源码） |
| **vLLM** | 0.31.0 | **Apache-2.0** | 本地推理服务端 |
| **Ollama / llama.cpp** | Ollama 0.40.4（内含 llama.cpp） | **MIT** | 报文取证对照实验（本地 CPU） |
| **模型权重** | Qwen3-4B/8B、Llama-3.1-8B | 各自模型许可 | 仅推理，**权重不在本仓库** |

## 我们**复制**过什么

**没有。** 本仓库的 6 个脚本（`bfcl_tax_report.py`、`reproduce.py`、
`tools/*.py`、`ports/tau2_tax_report.py`）全部为本工作原创；
没有任何文件是从上述项目拷贝或改写的。

判定方法（可自行复核）：

```bash
grep -rn "Copyright\|SPDX" --include=*.py .        # 第三方版权头：0 命中
```

## 我们**分发**了什么

| 目录 | 内容 | 性质 |
|---|---|---|
| `slices/` | 10 条臂的 `*_result.json` 与 `official_score.jsonl` | **我们自己跑出来的产物**（输入切片，40 MB） |
| `reports/` | 逐臂 `tax_report.json`、τ² 与田野的判定 json | **我们算出来的统计量** |
| `examples/` | 一份样例报告 | 同上 |

`reports/` 里含**对 τ² 官方榜公开提交的聚合统计**（28 份 / 11,476 条仿真）。
这些统计量由公开提交的轨迹文件算出，本仓库**不含**其原始轨迹；
引用该数据时请遵循发布方的条款。

## 引用（非代码使用）

论文 Related work 引用了 **Interface-Induced Trajectory Censoring**
（arXiv:2609.03966）用于现象划界：**仅引用文献，未使用其代码**。

## 我们的许可

本仓库全部内容（上述原创脚本 + `slices/` + `reports/` + 文档）按
**MIT** 提供，见 [`LICENSE`](LICENSE)。
