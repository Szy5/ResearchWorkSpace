# Paper-Wiki

<p align="center">
  <img src="img/pic_1.png" alt="Paper-Wiki：从论文 LaTeX 到结构化知识库" width="720"/>
</p>

<p align="center">
  <strong>把科研论文自动转化为结构化、可积累的个人论文知识库。</strong>
</p>

<p align="center">
  <a href="https://github.com/Szy5/ResearchWorkSpace"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python 3.11+"></a>
  <a href="https://github.com/Szy5/ResearchWorkSpace"><img src="https://img.shields.io/badge/status-Layer%200%2F1-green.svg" alt="Layer 0/1"></a>
  <a href="https://github.com/Szy5/ResearchWorkSpace"><img src="https://img.shields.io/badge/LLM-OpenAI--compatible-orange.svg" alt="OpenAI-compatible LLM"></a>
</p>

---

## 简介

Paper-Wiki 是一个**个人科研论文知识库**工具。它读取 `raw/` 下的 LaTeX 论文源码，调用 LLM 生成每篇论文的 **Layer 1 三件套**，为后续 Wiki、图谱与 RAG 检索打下基础。

当前已实现：

| 层级    | 能力                                                         | 状态        |
| ------- | ------------------------------------------------------------ | ----------- |
| Layer 0 | LaTeX 解析、章节抽取、图表路径保留                           | ✅          |
| Layer 1 | `summary.md` / `prior_works.json` / `sci_pattern.json` | ✅          |
| Layer 2 | Neo4j 科学发现图谱增量入库（`graph plan/apply`）           | ✅ 部分实现 |
| Layer 3 | 向量检索、图谱查询、HTTP API                                 | 🚧 规划中   |

**设计灵感：** [LLM Wiki](docs/llm_wiki.md) · [Sci-Reasoning](https://github.com/AmberLJC/Sci-Reasoning)

---

## 特性

- **LaTeX 原生输入** — 递归内联 `\input` / `\include`，自动识别主文件与 introduction / method / experiments 等章节
- **三件套生成** — 精读摘要、前作谱系、科学创新范式分类，输出经 Pydantic 校验
- **主论文元信息单点维护** — 主论文 metadata 统一保存在 `summary.md` frontmatter，`prior_works.json` / `sci_pattern.json` 不再重复保存
- **自动发现待处理论文** — 一条命令扫描 `raw/`，只为未生成完整三件套的论文执行 ingest
- **Neo4j 增量入库** — `graph plan` 生成 JSONL 事件，`graph apply` 幂等写入 Paper 节点和前作关系
- **Prompt 可切换** — CLI 透传三个 prompt 文件，方便调试与迭代
- **增量写入** — 每步生成后立即落盘，单步失败不丢已完成产物
- **Markdown 增强** — 摘要支持公式、图片引用与格式规范；图片路径自动指向 `raw/{slug}/figures/`

---

## 快速开始

```bash
# 1. 克隆并安装
git clone https://github.com/Szy5/ResearchWorkSpace.git
cd ResearchWorkSpace
conda create -n paper-wiki -c conda-forge python=3.11 -y && conda activate paper-wiki
pip install -r requirements.txt && pip install -e .

# 2. 配置 LLM（复制模板后填入密钥）
cp .env.example .env

# 3. 放入论文 LaTeX 到 raw/{paper-slug}/，先解析再生成
paper-wiki parse GraphWalker
paper-wiki ingest GraphWalker --overwrite
```

产物输出到 `artifacts/GraphWalker/`：

```
artifacts/GraphWalker/
├── summary.md          # 精读摘要（含 YAML frontmatter）
├── prior_works.json    # 直接前作与思想谱系
└── sci_pattern.json    # 科学创新范式分类
```

---

## 安装

### 环境要求

- Python **3.11+**
- 任意 **OpenAI 兼容** API（OpenAI / Azure / 自建网关等）

### 依赖安装

```bash
conda create -n paper-wiki -c conda-forge --override-channels python=3.11 -y
conda activate paper-wiki
pip install -r requirements.txt
pip install --no-build-isolation -e .
```

若 pip 镜像缺包，可改用官方 PyPI：

```bash
pip install -i https://pypi.org/simple -r requirements.txt
pip install -i https://pypi.org/simple --no-build-isolation -e .
```

### 配置

在项目根目录创建 `.env`（可参考 `.env.example`）：

```bash
MODEL_NAME=your-model-name
BASE_URL=https://your-api-base-url/v1
API_KEY=your-api-key
```

也兼容 OpenAI 官方变量名：`OPENAI_MODEL` / `OPENAI_BASE_URL` / `OPENAI_API_KEY`。

> ⚠️ 请勿将 `.env` 或 API Key 提交到版本控制。

---

## 使用

### 1. 添加论文

将 LaTeX 源码放入 `raw/{paper-slug}/`。`paper-slug` 即目录名，例如 `GraphWalker`。

解析器会按以下优先级寻找主文件：

1. `main.tex` → `paper.tex` → `article.tex`
2. 包含 `\begin{document}` 的 `.tex`
3. 体积最大的 `.tex`

### 2. 解析检查（Layer 0，不调用 LLM）

```bash
paper-wiki parse GraphWalker
paper-wiki parse GraphWalker --verbose   # DEBUG 日志
```

关注输出中的 `entry_file`、`matched_sections`、`estimated_tokens`，确认解析无误后再 ingest。

### 3. 生成三件套（Layer 1）

```bash
paper-wiki ingest GraphWalker
paper-wiki ingest GraphWalker --overwrite --verbose
paper-wiki ingest GraphWalker 2508.00719 --overwrite
paper-wiki ingest-all --overwrite
```

默认不覆盖已有产物；需重生成时加 `--overwrite`。
传入多个 slug 时会按顺序逐篇生成；若某篇失败，CLI 会继续处理后续论文，并在结束时返回非零退出码。
`--ingest-all` 会扫描 `raw/` 下所有包含 `.tex` 的论文目录，默认跳过已经拥有完整 `summary.md`、`prior_works.json`、`sci_pattern.json` 的论文；加 `--overwrite` 时会重跑所有 raw 论文。

### 4. 自定义 Prompt

```bash
paper-wiki ingest GraphWalker --overwrite \
  --summary-prompt paper_summary_v2.py \
  --prior-works-prompt prior_work_prompt.py \
  --sci-pattern-prompt sci_pattern_classify_prompt.py
```

路径可为 `prompts/` 下的相对路径，或绝对路径。

### 5. 人工审查

生成结果默认 `reviewed: false`。入库前建议核对：

- `summary.md` 标题、作者、贡献类型与正文是否有幻觉
- `prior_works.json` 前作标题、年份、角色是否准确
- `sci_pattern.json` 范式分类是否符合你的判断

### 6. 图谱入库（Layer 2）

```bash
paper-wiki graph plan 2307.07697
paper-wiki graph apply
```

`graph plan` 只读取 reviewed `artifacts/{slug}/`，更新本地 `graph_state/` 和 `graph_updates/graph_updates.jsonl`。`graph apply` 会读取未应用事件并幂等写入 Neo4j。

---

## CLI 参考

| 命令                                        | 说明                                                             |
| ------------------------------------------- | ---------------------------------------------------------------- |
| `paper-wiki parse <slug>`                 | 解析 LaTeX，打印 Layer 0 摘要                                    |
| `paper-wiki ingest <slug> [slug ...]`     | 生成一篇或多篇 Layer 1 三件套                                    |
| `paper-wiki ingest-all`                   | 扫描`raw/`，为未生成完整三件套的论文批量生成 Layer 1 artifacts |
| `paper-wiki graph plan <slug> [slug ...]` | 从 reviewed artifacts 生成 Layer 2 图谱快照和增量 JSONL 事件     |
| `paper-wiki graph apply`                  | 把图谱 JSONL 增量事件幂等写入 Neo4j                              |

**`ingest` 常用选项**

| 选项                     | 说明                                                  |
| ------------------------ | ----------------------------------------------------- |
| `--overwrite`, `-f`  | 覆盖已有产物                                          |
| `--verbose`, `-v`    | DEBUG 日志与异常堆栈                                  |
| `--summary-prompt`     | 摘要 prompt（默认`paper_summary_v2.py`）            |
| `--prior-works-prompt` | 前作 prompt（默认`prior_work_prompt.py`）           |
| `--sci-pattern-prompt` | 范式 prompt（默认`sci_pattern_classify_prompt.py`） |

`ingest-all` 支持同一组选项；默认只处理未生成完整三件套的 raw 论文，`--overwrite` 会重跑全部 raw 论文。

---

## 项目结构

```
Paper-wiki/
├── raw/{paper-slug}/       # Layer 0：LaTeX 源码（只读）
├── artifacts/{paper-slug}/ # Layer 1：三件套输出
├── prompts/                # LLM prompt 模板与范式 taxonomy
├── src/paper_wiki/         # 核心代码
│   ├── cli/                # Typer CLI
│   ├── core/               # 配置、模型、枚举
│   └── ingestion/          # 解析器、生成器、Pipeline
├── tests/                  # 单元测试与集成测试
└── docs/                   # 需求与技术方案文档
```

---

## 架构概览

```
  raw/{slug}/          prompts/
  LaTeX + figures  +   模板 / taxonomy
        │                    │
        └────────┬───────────┘
                 ▼
          ┌──────────────┐
          │  LaTeX Parser │  Layer 0
          └──────┬───────┘
                 ▼
          ┌──────────────┐
          │  LLM Pipeline │  Layer 1
          └──────┬───────┘
                 ▼
     summary.md · prior_works.json · sci_pattern.json
                 │
                 ▼  （规划中）
          wiki/ · 图谱 · RAG API   Layer 2 / 3
```

---

## 开发与测试

```bash
pytest
```

测试覆盖：LaTeX 解析与章节匹配、Pydantic schema 校验、mock LLM 端到端 ingest。

更多约定见 [AGENTS.md](AGENTS.md)；设计文档见 [docs/](docs/)。

---

## 常见问题

<details>
<summary><b>parse 没有命中章节？</b></summary>

检查主文件是否正确，或章节标题是否过于特殊。关键词维护于 `src/paper_wiki/ingestion/latex_parser.py` 的 `TARGET_SECTIONS`。

</details>

<details>
<summary><b>ingest JSON 校验失败？</b></summary>

模型输出不符合 schema 时会自动重试。仍失败时可换更强模型，或调整对应 prompt。

</details>

<details>
<summary><b>summary 里图片预览空白？</b></summary>

LaTeX 图多为 `.pdf`，多数 Markdown 预览不支持内嵌 PDF。路径已指向 `raw/{slug}/figures/`；可 Ctrl+点击链接，或安装 VS Code 的 <code>vscode-pdf</code> 插件查看。

</details>

<details>
<summary><b>conda / pip 装包失败？</b></summary>

conda 使用 <code>conda-forge</code> 渠道；pip 可加 <code>-i https://pypi.org/simple</code> 使用官方源。

</details>

---

## 路线图

- [X] Layer 0 LaTeX 解析
- [X] Layer 1 三件套生成与 prompt 透传
- [X] raw 待处理论文自动发现与批量 ingest
- [X] 摘要 Markdown 图片引用与格式规范
- [ ] Layer 2 Wiki 与科学发现图谱
- [ ] Layer 3 向量检索与 API

---

## 相关链接

- 仓库：[github.com/Szy5/ResearchWorkSpace](https://github.com/Szy5/ResearchWorkSpace)
- 需求文档：[docs/Paper-Wiki 需求文档.md](docs/Paper-Wiki%20需求文档.md)
- 技术方案：[docs/Paper-Wiki 技术方案_v1.md](docs/Paper-Wiki%20技术方案_v1.md)

---

<p align="center">
  如果这个项目对你有帮助，欢迎 Star ⭐
</p>
