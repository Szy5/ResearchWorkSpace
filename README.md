# Paper-Wiki

<p align="center">
  <img src="img/pic_1.png" alt="Paper-Wiki Architecture Banner" width="100%" />
</p>

<p align="center">
  <strong>把科研论文自动转化为结构化、可积累、可发布的个人研究知识库。</strong>
</p>

<p align="center">
  <a href="#核心能力">核心能力</a> ·
  <a href="#快速开始">快速开始</a> ·
  <a href="#web-阅读与发布工作台">Web 工作台</a> ·
  <a href="#cli-命令速查">CLI 速查</a> ·
  <a href="#项目结构">项目结构</a> ·
  <a href="#相关文档">相关文档</a>
</p>

---

## 简介

**Paper-Wiki** 是一个面向研究者与工程师的个人科研论文知识库与内容工作台。它从 arXiv / LaTeX 源码出发，先构建确定性的 **Paper Assets**（正文、章节、配图、参考文献），再按需生成结构化的**精读笔记、前作谱系与科学发现范式**；经过人工核验后，既可增量入库至 **Neo4j 科学发现图谱**，也可通过 **「论文透镜 · PaperLens」** 排版流水线一键生成微信公众号草稿。

> 设计灵感：[Sci-Reasoning](https://github.com/AmberLJC/Sci-Reasoning)

---

## 核心能力

| 模块 | 能力说明 | 状态 |
| --- | --- | :---: |
| **发现与推荐** | arXiv 关键词检索、按 ID/链接拉取源码、基于 Zotero 口味的每日论文推荐 | ✅ |
| **Layer 0 / 1 Assets** | 确定性 LaTeX 解析与资产抽取（`paper.md`、`sections.json`、`figures/`、`references.json`） | ✅ |
| **Layer 1 语义精读** | 生成精读笔记（`summary.md`）、前作谱系（`prior_works.json`）与科学发现范式（`sci_pattern.json`） | ✅ |
| **Web 阅读工作台** | FastAPI + React 工作站：发现、专注阅读、编辑保护、独立核验、批量后台任务 | ✅ |
| **公众号一键发布** | 内置「论文透镜 · PaperLens」海军蓝学术主题，自动生成标题/摘要/封面/排版 HTML 并推送草稿箱 | ✅ |
| **Layer 2 知识图谱** | 经人工核验后幂等增量同步至 Neo4j（`Paper` / `Author` / `Pattern` 节点与关系） | ✅ |
| **Layer 3 检索接口** | 向量检索、图谱问答与对外 HTTP API | 🚧 规划中 |

---

## 架构概览

```text
  arXiv / Zotero 推荐  ──▶  KnowledgeBase/raw/{slug}/ (LaTeX 源码，只读)
                                      │
                                      ▼  Layer 0 / Layer 1 (deterministic，不调用 LLM)
                     manifest.json · paper.md · sections · figures · references
                                      │
                                      ▼  Layer 1 LLM Pipeline (prompts/)
                       summary.md · prior_works.json · sci_pattern.json
                                      │
                        ┌─────────────┴─────────────┐
                        ▼                           ▼
               Web 审查与独立核验             「论文透镜」公众号发布
           (meta & prior_works 核验)      标题/摘要 · 配图去重 · 海军蓝排版
                        │                           │
                        ▼                           ▼
           Neo4j 科学发现图谱 (Layer 2)       微信公众号草稿箱
```

---

## 快速开始

### 1. 环境安装

需要 **Python 3.11+** 及任意 **OpenAI 兼容** LLM API（可选：Node.js 18+ 用于构建前端、Neo4j 用于图谱入库）。

```bash
git clone https://github.com/Szy5/ResearchWorkSpace.git
cd ResearchWorkSpace

conda create -n paper-wiki -c conda-forge python=3.11 -y
conda activate paper-wiki
pip install -r requirements.txt
pip install -e .
```

> 若 pip 镜像缺包，可加 `-i https://pypi.org/simple` 使用官方 PyPI 源。

### 2. 配置 `.env`

```bash
cp .env.example .env
```

填入最基础的 LLM 配置即可运行 Layer 0 / Layer 1（也兼容 `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`）：

```bash
MODEL_NAME=your-model-name
BASE_URL=https://your-api-base-url/v1
API_KEY=your-api-key
```

### 3. 跑通第一篇论文（CLI）

```bash
# 1. 拉取 arXiv 论文源码到 KnowledgeBase/raw/{slug}/
paper-wiki fetch 2406.00552

# 2. 确定性构建 Layer 1 assets（不调用 LLM）
paper-wiki assets 2406.00552

# 3. 生成精读笔记、前作谱系与科学发现范式
paper-wiki ingest 2406.00552 --overwrite
```

产物输出在 `KnowledgeBase/artifacts/{slug}/`：

```text
KnowledgeBase/artifacts/{slug}/
├── manifest.json          # 论文元信息、来源哈希与人工核验状态
├── assets/                # 确定性资产：paper.md / sections.json / figures/ / references.json
├── summary.md             # 精读笔记（问题与动机 / 核心思路 / 方法架构 / 实验与分析 / 边界与思考 / 结语）
├── prior_works.json       # 直接前作与思想演进脉络
├── sci_pattern.json       # 科学发现范式分类
└── wechat/                # 公众号发布包：article.md / article.html / cover.jpg / images/ / package.json
```

### 4. 启动 Web 工作台

```bash
# 启动后端 API（如已构建前端 dist/，可直接访问 http://127.0.0.1:8000）
paper-wiki web --host 127.0.0.1 --port 8000 --reload

# 前端开发模式（另开终端）
cd web/frontend && npm install && npm run dev
```

生产环境部署说明见 [DEPLOY.md](DEPLOY.md)。

---

## Web 阅读与发布工作台

- **发现**：统一搜索框支持关键词检索与 arXiv ID / 链接识别；展示基于 Zotero 口味的每日推荐，支持原位多选与批量提交精读生成。
- **论文库与专注阅读**：支持按状态筛选与待核验快捷视图；正文独立滚动、目录/前作/核验按需展开；编辑带未保存离开提醒与乐观锁冲突保护。
- **独立人工核验**：区分普通保存与人工确认（元信息核验与前作核验相互独立），双项通过后才允许增量入库 Neo4j。
- **后台任务持久化**：推荐刷新、批量精读、公众号排版与发布均异步执行并落盘至 `artifacts/.jobs/`，刷新页面自动恢复进度，支持单篇失败重试。
- **写作与发布（论文透镜 · PaperLens）**：
  - 自动生成公众号标题/摘要、提取精简作者与机构、去重配图并优先选取方法框架图作为封面；
  - 默认调用 Cursor 无头模式 + `gzh-design` 的 **`论文透镜`**（深海军蓝学术内参主题）生成 100% 公众号合规 HTML 片段（期刊题头 + 30 秒核心速览 + `01–06` 主章节 + 低权重延伸档案 + 品牌尾卡）；
  - 支持在页面内预览、修改标题/摘要/封面，确认后再推送到微信公众号草稿箱；也支持上传独立 Markdown 文章直接排版发布。

---

## CLI 命令速查

未安装 console script 时，可用 `PYTHONPATH=src python -m paper_wiki.cli.main ...` 替代 `paper-wiki`。

### 发现与入库（Layer 0 / 1）

| 命令 | 用途 | 常用示例 |
| --- | --- | --- |
| `paper-wiki search <query>` | 检索 arXiv 候选论文 | `paper-wiki search "knowledge graph agent" --start-year 2024 -n 10` |
| `paper-wiki fetch <arxiv_id>` | 下载源码到 `raw/`（可加 `--and-ingest`） | `paper-wiki fetch 2406.00552 --and-ingest --overwrite` |
| `paper-wiki recommend run` | 基于 Zotero 口味生成每日推荐快照 | `paper-wiki recommend run --max-papers 15` |
| `paper-wiki parse <slug>` | 仅解析 LaTeX 检查章节与 token 规模 | `paper-wiki parse GraphWalker --verbose` |
| `paper-wiki assets <slug...>` | 确定性构建 `manifest.json` 与 `assets/` | `paper-wiki assets GraphWalker --overwrite` |
| `paper-wiki ingest <slug...>` | 生成语义产物（`--only summary\|prior_works\|sci_pattern`） | `paper-wiki ingest GraphWalker --overwrite` |
| `paper-wiki ingest-all` | 批量补齐 `raw/` 下缺失产物的论文 | `paper-wiki ingest-all --only summary` |

### 图谱与发布（Layer 2 / WeChat）

| 命令 | 用途 | 常用示例 |
| --- | --- | --- |
| `paper-wiki graph plan [slugs... \| --all]` | 针对已核验论文生成幂等图谱增量事件（不连 Neo4j） | `paper-wiki graph plan --all` |
| `paper-wiki graph apply` | 将未应用的增量事件 `MERGE` 进 Neo4j | `paper-wiki graph apply` |
| `paper-wiki publish render-html <slug>` | 调用 Cursor 无头模式排版为公众号 HTML | `paper-wiki publish render-html 2611.15268 --theme 论文透镜` |
| `paper-wiki publish wechat <slug> --html <file>` | 上传本地图片并创建微信公众号草稿 | `paper-wiki publish wechat 2611.15268 --html wechat/article.html` |
| `paper-wiki web` | 启动 FastAPI 后端服务 | `paper-wiki web --host 127.0.0.1 --port 8000` |

---

## 完整 `.env` 选配参考

```bash
# ── 1. 核心 LLM（必填） ──
MODEL_NAME=your-model-name
BASE_URL=https://your-api-base-url/v1
API_KEY=your-api-key
# SUMMARY_MAX_CONTEXT_CHARS=60000
# LLM_HTTP_PROXY=http://127.0.0.1:7890

# ── 2. 微信公众号与无头排版（可选） ──
WECHAT_APPID=your-appid
WECHAT_SECRET=your-secret
WECHAT_AUTHOR=论文透镜
# WECHAT_PROXY=http://user:pass@fixed-ip-host:3128   # 出口 IP 不固定时走白名单代理
CURSOR_API_KEY=your-cursor-api-key                   # Cursor 无头排版（agent -p）所需
CURSOR_RENDER_THEME=论文透镜                          # 默认海军蓝主题，也可切换其它 gzh-design 主题

# ── 3. 论文发现与 Zotero 推荐（可选） ──
ARXIV_QUERY=cs.AI+cs.LG+cs.CL+cs.IR
MAX_PAPER_NUM=15
ZOTERO_ID=your-zotero-id
ZOTERO_KEY=your-zotero-key

# ── 4. Layer 2 Neo4j 图谱（可选） ──
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

> ⚠️ 请勿提交 `.env` 或任何 API Key / AppSecret 到版本控制。

---

## 项目结构

```text
Paper-wiki/
├── KnowledgeBase/              # 运行时数据（默认被 git 忽略，与代码解耦）
│   ├── raw/{slug}/             # Layer 0：LaTeX 源码（只读）
│   ├── artifacts/{slug}/       # Layer 1：assets、精读、前作、范式与公众号发布包
│   ├── graph_state/            # Layer 2：本地图谱快照
│   └── graph_updates/          # Layer 2：增量 JSONL 事件与 checkpoint
├── prompts/                    # LLM Prompt 模板与科学发现范式 taxonomy
├── src/paper_wiki/             # Python 核心包
│   ├── assets/                 # 确定性 paper assets 构建与读取
│   ├── cli/                    # Typer CLI 入口
│   ├── core/                   # 配置、Pydantic 模型、任务进度
│   ├── discovery/              # arXiv 检索/拉取与 Zotero 推荐
│   ├── graph/                  # 图谱增量规划与 Neo4j 写入
│   ├── ingestion/              # LaTeX 解析、精读/前作/范式生成器与 Pipeline
│   ├── publishing/             # 论文透镜公众号组装、Cursor 排版、封面生成与微信 API
│   └── web/                    # FastAPI 路由、Schema 与后台任务服务
├── web/frontend/               # Vite + React + TypeScript 前端工作台
├── deploy/                     # 生产部署脚本与配置（见 DEPLOY.md）
├── tests/                      # 单元测试与集成测试
├── docs/                       # 核心需求与技术架构文档
└── img/                        # README 展示图
```

---

## 开发与测试

```bash
# 运行 Python 单元测试与集成测试
pytest

# 运行前端测试与构建
cd web/frontend && npm test && npm run build
```

---

## 相关文档

- 工程规范与边界：[AGENTS.md](AGENTS.md)
- 部署运维指南：[DEPLOY.md](DEPLOY.md)
- 项目总需求文档：[docs/项目-需求文档.md](docs/项目-需求文档.md)
- 总体技术方案：[docs/Paper-Wiki 技术方案_v1.md](<docs/Paper-Wiki%20技术方案_v1.md>)
- Assets 设计方案：[docs/Paper2Assets-设计方案.md](docs/Paper2Assets-设计方案.md)
- 公众号发布方案：[docs/Paper2Blogs-技术方案.md](docs/Paper2Blogs-技术方案.md)
- Layer 2 图谱方案：[docs/Neo4j 科学发现图谱需求与技术方案.md](<docs/Neo4j%20科学发现图谱需求与技术方案.md>)

---

## 路线图

- [x] Layer 0 LaTeX 解析 & Layer 1 确定性 Paper Assets
- [x] 结构化精读笔记、前作谱系与科学发现范式生成
- [x] arXiv 检索/拉取与 Zotero 口味每日推荐
- [x] Web 阅读工作台（发现、专注阅读、草稿保护、独立核验、持久化后台任务）
- [x] 「论文透镜 · PaperLens」海军蓝公众号一键排版与草稿推送
- [x] Layer 2 Neo4j 科学发现图谱增量入库
- [ ] 收藏 / 已读模型、原文双栏对照与专题合集
- [ ] Layer 3 向量检索与问答 API
