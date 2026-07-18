# Paper-Wiki

**把科研论文自动转化为结构化、可积累的个人论文知识库。**

---

## 简介

Paper-Wiki 是一个**个人科研论文知识库**工具。它读取 `raw/` 下的 LaTeX 论文源码，先构建 deterministic **paper assets**，再按需调用 LLM 生成每篇论文的 **Layer 1 语义产物**，审查通过后可选地把论文、作者、科学范式增量写入 **Layer 2 Neo4j 图谱**。

当前已实现：

| 层级    | 能力                                                                               | 状态         |
| ------- | ---------------------------------------------------------------------------------- | ------------ |
| Layer 0 | LaTeX 解析、章节抽取、图表路径保留                                                 | ✅           |
| Layer 1 | deterministic assets +`summary.md` / `prior_works.json` / `sci_pattern.json` | ✅           |
| 发现层  | Paper2Search / Paper2Recommend：arXiv 检索、按 ID 拉取、Zotero 口味推荐            | ✅ CLI + Web |
| Layer 2 | Neo4j 科学发现图谱增量入库（Paper / Author / Pattern 三种节点）                   | ✅           |
| 发布    | `artifacts/{slug}/` HTML 发布到微信公众号草稿                                    | ✅           |
| Web v1  | FastAPI 后端 + Vite React 工作站：今日推荐/检索添加/审查发布                       | ✅ 原型实现  |
| Layer 3 | 向量检索、图谱查询、HTTP API                                                       | 🚧 规划中    |

**设计灵感：** [LLM Wiki](docs/llm_wiki.md) · [Sci-Reasoning](https://github.com/AmberLJC/Sci-Reasoning)

本文档下半部分是一份**操作手册**：每个命令都单独列出用途、全部参数和示例，跟着第「操作手册」章节从上到下执行即可完成一篇论文从入库到图谱的全流程，不需要再去翻代码。

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

# 3. 放入论文 LaTeX 到 raw/{paper-slug}/，先解析/构建 assets，再生成语义产物
paper-wiki parse GraphWalker
paper-wiki assets GraphWalker
paper-wiki ingest GraphWalker --overwrite
```

产物输出到 `artifacts/GraphWalker/`：

```
artifacts/GraphWalker/
├── manifest.json
├── assets/
│   ├── paper.md
│   ├── sections.json
│   ├── figures/
│   │   ├── manifest.json
│   │   └── ...
│   └── references.json
├── summary.md          # assets 下游：精读摘要正文，可附加科学发现范式和先前工作分析
├── prior_works.json    # assets 下游：直接前作与思想谱系
└── sci_pattern.json    # assets 下游：科学创新范式分类
```

---

## 安装与配置

### 环境要求

- Python **3.11+**
- 任意 **OpenAI 兼容** API（OpenAI / Azure / 自建网关等）
- （可选）Neo4j 实例（本地或 Aura），仅 Layer 2 图谱入库需要

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

### `.env` 配置

在项目根目录创建 `.env`（可参考 `.env.example`）：

```bash
MODEL_NAME=your-model-name
BASE_URL=https://your-api-base-url/v1
API_KEY=your-api-key

# 可选：微信公众号草稿发布
WECHAT_APPID=your-wechat-official-account-appid
WECHAT_SECRET=your-wechat-official-account-secret
WECHAT_AUTHOR=Paper-Wiki
# WECHAT_COVER_PATH=artifacts/GraphWalker/cover.jpg
# WECHAT_THUMB_MEDIA_ID=already-uploaded-cover-media-id

# 可选：Neo4j 图谱增量入库
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j

# 可选：Paper2Search / Paper2Recommend
ARXIV_MIN_INTERVAL=4.0
SEARCH_MAX_RESULTS=10
FETCH_DOWNLOAD_TIMEOUT_SECONDS=60
ZOTERO_ID=your-zotero-user-or-group-id
ZOTERO_KEY=your-zotero-api-key
ZOTERO_LIBRARY_TYPE=user
ZOTERO_IGNORE=
ARXIV_QUERY=cs.AI+cs.LG+cs.CL+cs.IR
MAX_PAPER_NUM=15
RECOMMEND_CANDIDATE_POOL_SIZE=200
RECOMMEND_EMBEDDING_MODEL=avsolatorio/GIST-small-Embedding-v0
```

也兼容 OpenAI 官方变量名：`OPENAI_MODEL` / `OPENAI_BASE_URL` / `OPENAI_API_KEY`。

未安装 console script 的开发环境，可以用 `PYTHONPATH=src python -m paper_wiki.cli.main ...` 调用同一套 CLI，下文所有命令都可以这样替换。

> ⚠️ 请勿将 `.env`、API Key 或微信公众号 AppSecret 提交到版本控制。

---

## 操作手册

按论文从加入到入图谱的自然顺序排列：**发现/添加论文 → 解析 → 构建 assets → 生成语义产物 → 人工审查 → 图谱入库 → 发布 → Web 界面**。每个命令都列出了它接受的**全部**参数；只写"必填"的参数是可以直接运行的最小命令，其余都有默认值。

### 1. `paper-wiki search` — 检索 arXiv 候选论文

不落盘，只打印候选列表，用于决定要不要 `fetch`。

| 参数                     | 类型 | 必填 | 默认值                    | 说明                        |
| ------------------------ | ---- | ---- | ------------------------- | --------------------------- |
| `query`（位置参数）    | str  | 是   | -                          | arXiv 关键词检索查询        |
| `--start-year`         | int  | 否   | `2020`                   | 起始年份                    |
| `--end-year`           | int  | 否   | `2026`                   | 结束年份                    |
| `--max-results`, `-n` | int  | 否   | 读取 `SEARCH_MAX_RESULTS` | 最大返回条数                |
| `--verbose`, `-v`     | flag | 否   | `False`                  | 输出 DEBUG 日志和异常堆栈 |

```bash
paper-wiki search "graph neural network" --start-year 2024 --end-year 2026 -n 10
```

### 2. `paper-wiki fetch` — 下载 arXiv 源码到 raw/

按 arXiv ID 下载 LaTeX 源码和 PDF 到 `raw/{slug}/`，`slug` 由 arXiv ID 自动推出。

| 参数                    | 类型 | 必填 | 默认值    | 说明                                    |
| ----------------------- | ---- | ---- | ---------- | ---------------------------------------- |
| `arxiv_id`（位置参数） | str  | 是   | -          | 例如`2401.12345`                       |
| `--and-ingest`        | flag | 否   | `False`   | 下载完成后立即运行 Layer 1 ingest        |
| `--overwrite`, `-f`  | flag | 否   | `False`   | 允许覆盖已有`raw/{slug}/`              |
| `--verbose`, `-v`    | flag | 否   | `False`   | 输出 DEBUG 日志和异常堆栈              |

```bash
paper-wiki fetch 2406.00552
paper-wiki fetch 2406.00552 --and-ingest --overwrite
```

### 3. `paper-wiki recommend run` — 生成每日推荐快照

基于 Zotero 语料的阅读口味，从当日 arXiv 候选池里挑出 Top K，写入 `artifacts/.recommendations/{date}.json` 和 `latest.json`。

| 参数              | 类型 | 必填 | 默认值               | 说明                              |
| ----------------- | ---- | ---- | --------------------- | ---------------------------------- |
| `--max-papers`, `-n` | int  | 否   | 读取 `MAX_PAPER_NUM` | 推荐 Top K 数量                    |
| `--arxiv-query`  | str  | 否   | 读取 `ARXIV_QUERY`   | 覆盖候选池查询                    |
| `--verbose`, `-v` | flag | 否   | `False`              | 输出 DEBUG 日志和异常堆栈        |

```bash
paper-wiki recommend run --max-papers 15
```

### 4. `paper-wiki parse` — 解析检查（Layer 0，不调用 LLM）

只解析 `raw/{slug}` 的 LaTeX 并打印摘要，方便在生成产物前确认主文件识别、章节命中和 token 规模是否正常。

| 参数                  | 类型 | 必填 | 默认值  | 说明                       |
| --------------------- | ---- | ---- | -------- | --------------------------- |
| `slug`（位置参数）  | str  | 是   | -        | `raw/{slug}` 目录名       |
| `--verbose`, `-v`   | flag | 否   | `False` | 输出 DEBUG 级别日志       |

```bash
paper-wiki parse GraphWalker
paper-wiki parse GraphWalker --verbose
```

解析器按以下优先级寻找主文件：`main.tex` → `paper.tex` → `article.tex` → 含 `\begin{document}` 的 `.tex` → 体积最大的 `.tex`。关注输出中的 `entry_file`、`matched_sections`、`estimated_tokens`，确认无误后再继续。

### 5. `paper-wiki assets` — 构建论文 Assets（Layer 1 deterministic，不调用 LLM）

只构建 `artifacts/{slug}/manifest.json` 和 `assets/` 下的通用论文资产（`paper.md`/`sections.json`/`figures/`/`references.json`），不调用 LLM。

| 参数                    | 类型      | 必填 | 默认值  | 说明                        |
| ----------------------- | --------- | ---- | -------- | ---------------------------- |
| `slugs`（位置参数）   | list[str] | 是   | -        | 一个或多个`raw/{slug}` 目录名 |
| `--overwrite`, `-f`  | flag      | 否   | `False` | 允许覆盖已有 assets        |
| `--verbose`, `-v`    | flag      | 否   | `False` | 输出 DEBUG 日志和异常堆栈 |

```bash
paper-wiki assets GraphWalker
paper-wiki assets GraphWalker 2508.00719 --overwrite
```

### 6. `paper-wiki ingest` — 生成 Layer 1 语义产物

在 assets 基础上调用 LLM，生成 `summary.md`、`prior_works.json`、`sci_pattern.json` 三个独立产物。会先构建或复用 assets，三者共享同一份 assets 输入但可以独立生成或重跑。

| 参数                        | 类型      | 必填 | 默认值                                  | 说明                                                                                       |
| --------------------------- | --------- | ---- | ---------------------------------------- | -------------------------------------------------------------------------------------------- |
| `slugs`（位置参数）       | list[str] | 是   | -                                        | 一个或多个`raw/{slug}` 目录名                                                              |
| `--overwrite`, `-f`      | flag      | 否   | `False`                                 | 允许覆盖所选 Layer 1 语义产物                                                              |
| `--verbose`, `-v`        | flag      | 否   | `False`                                 | 输出 DEBUG 日志和异常堆栈                                                                 |
| `--only`                 | list[str] | 否   | 不传=全部三个                           | 只生成指定产物，可重复传入：`summary`/`prior_works`/`sci_pattern`（也接受 `prior-works`/`pattern`） |
| `--summary-prompt`       | str       | 否   | `paper_summary_v3.py`                  | 摘要 prompt 文件；可传`prompts/` 下相对路径或绝对路径                                     |
| `--prior-works-prompt`   | str       | 否   | `prior_work_prompt.py`                 | 前作谱系 prompt 文件                                                                      |
| `--sci-pattern-prompt`   | str       | 否   | `sci_pattern_classify_prompt.py`       | 科学范式 prompt 文件                                                                      |

```bash
paper-wiki ingest GraphWalker --overwrite
paper-wiki ingest GraphWalker 2508.00719 --overwrite --verbose
paper-wiki ingest GraphWalker --only summary --overwrite
paper-wiki ingest GraphWalker --overwrite \
  --summary-prompt paper_summary_v3.py \
  --prior-works-prompt prior_work_prompt.py \
  --sci-pattern-prompt sci_pattern_classify_prompt.py
```

传入多个 slug 时按顺序逐篇生成；若某篇失败，CLI 会继续处理后续论文，并在结束时返回非零退出码。每次新生成 `summary.md` 后，pipeline 会把已生成或已有的 `sci_pattern.json` 追加为 `## 科学发现范式` 小节，把 `prior_works.json` 的 `synthesis_narrative` 追加为 `## 先前工作分析` 小节；对应 JSON 不存在时跳过该小节。

### 7. `paper-wiki ingest-all` — 批量生成 Layer 1 语义产物

扫描 `raw/` 下所有论文目录，只为缺少所选产物的论文生成（不重复调用 LLM），加 `--overwrite` 才会重跑全部。

| 参数                      | 类型      | 必填 | 默认值                            | 说明                                                                        |
| -------------------------- | --------- | ---- | ---------------------------------- | ----------------------------------------------------------------------------- |
| `--overwrite`, `-f`      | flag      | 否   | `False`                          | 重跑`raw/` 下所有论文；默认只处理缺产物的论文                              |
| `--verbose`, `-v`        | flag      | 否   | `False`                          | 输出 DEBUG 日志和异常堆栈                                                 |
| `--only`                 | list[str] | 否   | 不传=全部三个                     | 同`ingest` 的 `--only`                                                     |
| `--summary-prompt`       | str       | 否   | `paper_summary_v3.py`            | 同`ingest`                                                                 |
| `--prior-works-prompt`   | str       | 否   | `prior_work_prompt.py`           | 同`ingest`                                                                 |
| `--sci-pattern-prompt`   | str       | 否   | `sci_pattern_classify_prompt.py` | 同`ingest`                                                                 |

```bash
paper-wiki ingest-all
paper-wiki ingest-all --overwrite --only summary
```

### 8. 人工审查（无 CLI 命令，直接编辑或走 Web 审查页）

`manifest.json` 的 `paper.meta_reviewed` 和 `paper.prior_works_reviewed` 默认都是 `false`，两者都为 `true` 才允许该论文进入 Layer 2 图谱（见下一节）。可以直接编辑 `artifacts/{slug}/manifest.json`，也可以通过 [`paper-wiki web`](#12-paper-wiki-web--启动本地-web-原型) 的审查页勾选。

入库前建议核对：

- `manifest.json` 中的标题、作者、年份、venue、arXiv ID 是否准确（对应 `meta_reviewed`）
- `summary.md` 正文是否有幻觉
- `prior_works.json` 前作标题、年份、角色是否准确，`sci_pattern.json` 范式分类是否符合判断（对应 `prior_works_reviewed`）

### 9. `paper-wiki graph plan` — 生成 Layer 2 图谱增量事件

只读取 `meta_reviewed && prior_works_reviewed` 均为 `true` 的 `artifacts/{slug}/`，把 Paper / Author / Pattern 节点和三类关系（前作关系、`AUTHORED`、`CLASSIFIED_AS`）与本地快照 `graph_state/` 做 diff，追加幂等事件到 `graph_updates/graph_updates.jsonl`。**不连接 Neo4j**，可以反复跑做 dry-run。

| 参数                      | 类型            | 必填              | 默认值    | 说明                                                                 |
| -------------------------- | --------------- | ------------------ | ---------- | ---------------------------------------------------------------------- |
| `slugs`（位置参数）      | list[str] \| 空 | 与`--all` 二选一 | -          | 一个或多个`artifacts/{slug}` 目录名                                  |
| `--all`                  | flag            | 否                | `False`   | 扫描`artifacts/` 下所有已审查完成的论文并全部 plan，不需要手动列 slug |
| `--include-unreviewed`   | flag            | 否                | `False`   | 允许为未审查完成的 artifact 也生成图谱事件（调试用）                |
| `--verbose`, `-v`      | flag            | 否                | `False`   | 输出 DEBUG 日志和异常堆栈                                          |

```bash
paper-wiki graph plan 2307.07697
paper-wiki graph plan 2307.07697 GraphWalker
paper-wiki graph plan --all
```

### 10. `paper-wiki graph apply` — 把增量事件写入 Neo4j

读取 `graph_updates/graph_updates.jsonl` 中未应用的事件（按 `checkpoint.json` 记录的位置），幂等 `MERGE` 进 Neo4j，写完更新 checkpoint。

| 参数                                        | 类型 | 必填 | 默认值   | 说明                                                                |
| -------------------------------------------- | ---- | ---- | --------- | --------------------------------------------------------------------- |
| `--since-checkpoint` / `--from-start`   | flag | 否   | `since-checkpoint` | 默认只应用 checkpoint 之后的新事件；`--from-start` 从第一行重新应用全部事件 |
| `--verbose`, `-v`                        | flag | 否   | `False`  | 输出 DEBUG 日志和异常堆栈                                          |

```bash
paper-wiki graph apply
paper-wiki graph apply --from-start   # 全量重放，配合 clear_graph() 做全库重建时使用
```

典型日常用法：随时在审查页把新论文标记为已审查，然后定期跑一次 `paper-wiki graph plan --all && paper-wiki graph apply`。

### 11. `paper-wiki publish` — 发布 Layer 1 产物

#### 11.1 `publish render-html` — 排版为公众号 HTML

调用本机 Cursor 无头模式，把 `artifacts/{slug}/summary.md` 排版成公众号 HTML。

| 参数                  | 类型 | 必填 | 默认值                     | 说明                        |
| --------------------- | ---- | ---- | --------------------------- | ---------------------------- |
| `slug`（位置参数）  | str  | 是   | -                           | `artifacts/{slug}` 目录名 |
| `--theme`           | str  | 否   | 读取 `CURSOR_RENDER_THEME` | 排版主题                    |
| `--verbose`, `-v` | flag | 否   | `False`                    | 输出 DEBUG 日志和异常堆栈 |

```bash
paper-wiki publish render-html GraphWalker
```

#### 11.2 `publish wechat` — 创建微信公众号草稿

读取 `artifacts/{slug}/` 下已有的 HTML 文件，上传正文中的本地图片并替换为微信图片 URL，创建公众号图文草稿。**不会**触发 ingest、graph plan 或覆盖原始 HTML。

| 参数                   | 类型 | 必填 | 默认值                  | 说明                                                                |
| ---------------------- | ---- | ---- | ------------------------ | ---------------------------------------------------------------------- |
| `slug`（位置参数）   | str  | 是   | -                        | `artifacts/{slug}` 目录名                                          |
| `--html`             | str  | 是   | -                        | `artifacts/{slug}/` 下要发布的 HTML 文件名或相对路径              |
| `--title`            | str  | 否   | 使用 HTML 文件名        | 微信草稿标题                                                       |
| `--author`           | str  | 否   | 读取 `WECHAT_AUTHOR`     | 作者                                                               |
| `--digest`           | str  | 否   | 无                       | 图文摘要                                                           |
| `--cover`            | Path | 否   | 读取 `WECHAT_COVER_PATH` | 封面图路径；可传 artifact 内相对路径或项目根相对路径              |
| `--thumb-media-id`   | str  | 否   | 读取 `WECHAT_THUMB_MEDIA_ID` | 已上传封面永久素材 ID，传了就跳过封面上传                       |
| `--save-rendered`    | flag | 否   | `False`                 | 把图片 URL 替换后的 HTML 另存为 `{原文件名}_wechat_rendered.html` |
| `--verbose`, `-v`  | flag | 否   | `False`                 | 输出 DEBUG 日志和异常堆栈                                         |

```bash
paper-wiki publish wechat GraphWalker \
  --html article.html \
  --title "GraphWalker 论文精读" \
  --author "Paper-Wiki" \
  --digest "GraphWalker 方法与实验速览" \
  --cover figures/cover.jpg \
  --save-rendered
```

封面二选一：传 `--cover`/`WECHAT_COVER_PATH` 会上传封面并使用返回的永久素材 `media_id`；传 `--thumb-media-id`/`WECHAT_THUMB_MEDIA_ID` 复用已上传过的封面素材。HTML 必须位于 `artifacts/{slug}/` 内，扩展名为 `.html`/`.htm`；本地图片支持 `jpg/jpeg/png/gif`，远程 `http/https` 图片保留原 URL；命令会拒绝空 HTML、`<script>` 和外部 stylesheet 以避免公众号草稿接口报错。

### 12. `paper-wiki web` — 启动本地 Web 原型

后端读取同一份 `artifacts/` 状态，不引入额外数据库。

| 参数                | 类型 | 必填 | 默认值        | 说明                    |
| ------------------- | ---- | ---- | -------------- | ------------------------- |
| `--host`          | str  | 否   | `127.0.0.1`   | 监听地址                |
| `--port`          | int  | 否   | `8000`        | 监听端口                |
| `--reload`        | flag | 否   | `False`       | 开发模式自动重载        |
| `--verbose`, `-v` | flag | 否   | `False`       | 输出 DEBUG 级别日志    |

```bash
paper-wiki web --host 127.0.0.1 --port 8000 --reload
```

前端是独立 Vite 工程：

```bash
cd web/frontend
npm install
npm run dev
```

浏览器打开 Vite 输出的本地地址，默认把 `/api` 代理到 `http://127.0.0.1:8000`。首页是 `TodayFeed`（今日推荐，读 `.recommendations/latest.json`，支持勾选批量生成），顶部导航另有"检索 / 添加"（`SearchAndAdd`，关键词检索或按 arXiv ID 拉取）、"全部论文"与"待审查 (N)"。批量生成、检索、按 ID 拉取分别对应 `POST /api/papers/batch-ingest`、`GET /api/search`、`POST /api/papers/fetch`，均为异步 job，前端轮询 `GET /api/jobs/{job_id}` 直到 `succeeded`/`failed`。

---

## 典型工作流速查

只想知道"按什么顺序敲命令"，不需要参数细节时看这里：

```bash
# 发现并添加一篇论文
paper-wiki search "graph neural network" -n 10
paper-wiki fetch 2406.00552

# 生成产物
paper-wiki parse 2406.00552          # 可选，先检查解析是否正常
paper-wiki assets 2406.00552
paper-wiki ingest 2406.00552 --overwrite

# 人工审查：编辑 artifacts/2406.00552/manifest.json，
# 或用 `paper-wiki web` 打开审查页把 meta_reviewed / prior_works_reviewed 都勾上

# 增量入图谱
paper-wiki graph plan --all
paper-wiki graph apply

# 可选：发布到公众号
paper-wiki publish render-html 2406.00552
paper-wiki publish wechat 2406.00552 --html article.html
```

新增一批论文后，只需要重复"生成产物 → 人工审查 → `graph plan --all && graph apply`"这三步。

---

## 项目结构

```
Paper-wiki/
├── raw/{paper-slug}/       # Layer 0：LaTeX 源码（只读）
├── artifacts/{paper-slug}/ # Layer 1：assets + 语义产物输出
├── graph_state/            # Layer 2：本地图谱快照（papers/authors/patterns/relations...)
├── graph_updates/          # Layer 2：增量 JSONL 事件 + apply checkpoint
├── prompts/                # LLM prompt 模板与范式 taxonomy
├── src/paper_wiki/         # 核心代码
│   ├── cli/                # Typer CLI
│   ├── core/                # 配置、模型、枚举
│   ├── assets/              # deterministic paper assets builder
│   ├── ingestion/           # 解析器、生成器、Pipeline
│   ├── discovery/           # arXiv search/fetch + Zotero/arXiv recommend
│   ├── graph/               # reviewed artifacts -> graph state / Neo4j events
│   ├── publishing/          # HTML artifact 发布到微信公众号草稿
│   └── web/                 # FastAPI Web 原型入口层
├── web/frontend/           # Vite + React + TypeScript 前端原型
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
          │ Assets Builder│  Layer 1
          └──────┬───────┘
                 ▼
 manifest.json · assets/paper.md · sections · figures · references
                 │
                 ▼
          ┌──────────────┐
          │  LLM Pipeline │  Layer 1 downstream
          └──────┬───────┘
                 ▼
     summary.md · prior_works.json · sci_pattern.json
                 │
        ┌────────┴────────┐
        ▼                 ▼
 graph plan/apply      publish wechat
  (meta_reviewed &&        │
   prior_works_reviewed)   ▼
        │            微信公众号草稿
        ▼
  Neo4j：Paper / Author / Pattern
        │
        ▼  （规划中）
      Wiki · RAG API      Layer 2 / 3
```

---

## 开发与测试

```bash
pytest
cd web/frontend && npm test && npm run build
```

测试覆盖：LaTeX 解析与章节匹配、assets builder、Pydantic schema 校验、mock LLM 端到端 ingest、discovery search/fetch/recommend 单元与集成流程、Layer 2 图谱 planner/neo4j_store（Paper/Author/Pattern 节点、三类关系、增量 diff 与幂等性）、Web API 路由与异步任务、前端 TodayFeed/SearchAndAdd 批量生成与检索交互、微信公众号 HTML 定位/校验/图片替换/草稿请求。

更多约定见 [AGENTS.md](AGENTS.md)；设计文档见 [docs/](docs/)，其中 [Neo4j 科学发现图谱需求与技术方案.md](<docs/Neo4j%20科学发现图谱需求与技术方案.md>) 是 Layer 2 图谱的完整建模文档（节点/关系定义、去重规则、增量事件设计）。

---

## 常见问题

**parse 没有命中章节？**

检查主文件是否正确，或章节标题是否过于特殊。关键词维护于 `src/paper_wiki/ingestion/latex_parser.py` 的 `TARGET_SECTIONS`。

**ingest JSON 校验失败？**

模型输出不符合 schema 时会自动重试。仍失败时可换更强模型，或调整对应 prompt。

**summary 里图片预览空白？**

LaTeX 图多为 `.pdf`，多数 Markdown 预览不支持内嵌 PDF。优先检查 `artifacts/{slug}/assets/figures/manifest.json` 中的 `asset_path` 和 `source_path`；也可 Ctrl+点击原始路径，或安装 VS Code 的 `vscode-pdf` 插件查看。

**`graph plan` 报错说论文没有 review？**

确认 `artifacts/{slug}/manifest.json` 里 `paper.meta_reviewed` 和 `paper.prior_works_reviewed` 是否都是 `true`——两者必须同时为真才允许入库；调试时可以加 `--include-unreviewed` 绕过检查。

**conda / pip 装包失败？**

conda 使用 `conda-forge` 渠道；pip 可加 `-i https://pypi.org/simple` 使用官方源。

---

## 路线图

- [X] Layer 0 LaTeX 解析
- [X] Layer 1 deterministic paper assets contract
- [X] Layer 1 独立语义产物生成、单步重跑与 prompt 透传
- [X] raw 待处理论文自动发现与批量 ingest
- [X] 摘要 Markdown 图片引用与格式规范
- [X] 微信公众号 HTML 草稿发布
- [X] Web 原型 v1：论文列表、审查编辑、异步 ingest、微信发布入口
- [X] Paper2Search / Paper2Recommend：arXiv 检索、按 ID 拉取、Zotero 口味每日推荐（CLI）
- [X] Web 接入发现层：今日推荐 `TodayFeed`、检索/添加 `SearchAndAdd`、批量生成汇入待审查队列
- [X] Layer 2 Neo4j 科学发现图谱增量入库：Paper / Author / Pattern 三种节点，`graph plan --all` 批量入库
- [ ] Layer 2 Wiki 页面生成
- [ ] Layer 3 向量检索与 API

---

## 相关链接

- 仓库：[github.com/Szy5/ResearchWorkSpace](https://github.com/Szy5/ResearchWorkSpace)
- 需求文档：[docs/项目-需求文档.md](<docs/项目-需求文档.md>)
- 技术方案：[docs/Paper-Wiki 技术方案_v1.md](<docs/Paper-Wiki%20技术方案_v1.md>)
- Layer 2 图谱方案：[docs/Neo4j 科学发现图谱需求与技术方案.md](<docs/Neo4j%20科学发现图谱需求与技术方案.md>)

---

如果这个项目对你有帮助，欢迎 Star ⭐
