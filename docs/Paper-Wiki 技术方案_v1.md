# Paper-Wiki 技术方案 v1.3

> 作者：架构设计草稿 | 创建：2026-06-24 | 最后更新：2026-07-03 | 状态：持续维护

---

## 零、当前实现状态

本文档是长期维护文档，既记录已经落地的工程设计，也保留后续 Layer 2/Layer 3 的规划。每次功能实现、架构调整或范围变更后，都应同步更新本节与相关设计章节。

| 层次 | 当前状态 | 已落地内容 | 尚未落地内容 |
| ---- | -------- | ---------- | ------------ |
| Layer 0 | 已实现 | `LaTeXParser`、入口文件识别、`\input` / `\include` 内联、核心章节抽取、`paper-wiki parse` | 更复杂 LaTeX 语义解析、PDF OCR/正文回退 |
| Layer 1 | 已实现 | `IngestPipeline`、`SummaryGenerator`、`PriorWorksGenerator`、`PatternGenerator`、Pydantic 校验、prompt 切换、单篇/多篇 `paper-wiki ingest`、raw 扫描式 `paper-wiki ingest-all`，并将主论文元信息统一保存在 `summary.md` frontmatter | 单步骤重跑 `--only`、正式 review 命令 |
| Layer 2 | 部分实现 | `graph/` 包、reviewed artifacts 读取、Paper 节点与 typed prior-work 关系建模、`graph_state/` 快照、`graph_updates.jsonl` 事件日志、`paper-wiki graph plan/apply`、Neo4j 幂等入库；详见 [Neo4j 科学发现图谱需求与技术方案](./Neo4j%20科学发现图谱需求与技术方案.md) | `wiki/` 包、全局目录、概念页、日志、更多图谱查询 |
| Layer 3 | 未实现 | 无 | `retrieval/` 包、向量库、GraphRAG、FastAPI API |
| 测试 | 部分实现 | parser、models、mock LLM pipeline、CLI 多 slug ingest、raw 待处理发现、graph planner 增量事件 | graph/retrieval/api/e2e 测试 |

当前实现范围必须继续遵守 Layer 0/Layer 1 边界：ingest 只生成 `artifacts/{paper-slug}/` 三件套，不写入 `wiki/`、图谱、embedding 或检索索引。

## 一、技术选型


| 层次           | 选型                         | 理由                         |
| ------------ | -------------------------- | -------------------------- |
| 语言           | Python 3.11+               | 生态最丰富，LLM/向量库均有一流支持        |
| LLM API      | OpenAI-compatible API（已实现 OpenAI/DeepSeek 配置分支） | 通过统一 SDK 与 `.env` 支持模型切换 |
| LaTeX 解析     | 自实现预处理（正则 + 文件拼接）          | 轻量，无需引入重型 LaTeX 解析器        |
| 向量库          | ChromaDB（规划）              | 本地持久化、内置元数据过滤、无需部署         |
| Embedding 模型 | BGE / OpenAI embedding（规划） | 精度与成本平衡                    |
| 图计算          | NetworkX（规划）              | 纯 Python，图算法丰富，适合中小规模      |
| 图持久化         | JSON 文件（规划）               | Git 友好，无需数据库               |
| HTTP API     | FastAPI（规划）               | 异步、自动 OpenAPI 文档、类型安全      |
| 数据模型         | Pydantic v2                | 验证 + 序列化 + JSON schema 一体化 |
| CLI          | Typer                      | 基于 Pydantic，与 FastAPI 风格统一 |
| 配置管理         | pydantic-settings + `.env` | 统一管理 API Key 和路径配置         |
| 测试           | pytest + pytest-asyncio    | 标准，支持异步测试                  |
| 依赖管理         | conda                      | 速度快，现代 Python 标准           |


---

## 二、系统架构总览

```mermaid
graph TB
    subgraph "用户操作"
        U1[放入论文文件<br/>raw/slug/]
        U2[人工审查<br/>modified artifacts]
        U3[发起查询]
    end

    subgraph "Layer 0: 原始资料"
        L0[LaTeX + PDF<br/>只读存储]
    end

    subgraph "Layer 1: 论文产物 (ingestion/)"
        LP[LaTeXParser<br/>预处理]
        LLM[LLMClient<br/>API 抽象层]
        G1[SummaryGenerator]
        G2[PriorWorksGenerator]
        G3[PatternGenerator]
        A1[summary.md]
        A2[prior_works.json]
        A3[sci_pattern.json]
    end

    subgraph "Layer 2: Wiki 知识层 (wiki/)"
        GR[GraphManager<br/>科学发现图谱]
        IDX[IndexManager<br/>全局目录]
        LOG[LogManager<br/>操作日志]
        CON[ConceptManager<br/>概念页]
    end

    subgraph "Layer 3: 检索接口 (retrieval/ + api/)"
        EMB[Embedder<br/>向量化]
        VS[VectorStore<br/>ChromaDB]
        GQ[GraphQuery<br/>图谱查询]
        API[FastAPI<br/>HTTP 接口]
    end

    U1 --> L0
    L0 --> LP
    LP --> LLM
    LLM --> G1 & G2 & G3
    G1 --> A1
    G2 --> A2
    G3 --> A3

    U2 -->|reviewed=true| A1 & A2 & A3

    A1 & A2 & A3 --> GR & IDX & LOG & CON
    A1 --> EMB
    EMB --> VS

    U3 --> API
    API --> VS & GQ
    GR --> GQ
```



---

## 三、包结构设计

本节同时展示已实现包与规划包。当前代码仓库已经落地 `core/`、`ingestion/`、`cli/`、`graph/`；`wiki/`、`retrieval/`、`api/` 仍属于后续阶段，不应在非相关任务中提前实现。

```
paper_wiki/                         # 主 Python 包
│
├── core/                           # 核心领域模型（无外部依赖）
│   ├── __init__.py
│   ├── models.py                   # 所有 Pydantic 数据模型
│   ├── enums.py                    # 枚举：角色、范式、贡献类型
│   └── config.py                   # 全局配置（路径、API Key）
│
├── ingestion/                      # Layer 0 → Layer 1
│   ├── __init__.py
│   ├── latex_parser.py             # LaTeX 预处理与拼接
│   ├── llm_client.py               # LLM API 抽象接口
│   ├── generators/
│   │   ├── summary_generator.py    # 生成 summary.md
│   │   ├── prior_works_generator.py # 生成 prior_works.json
│   │   └── pattern_generator.py    # 生成 sci_pattern.json
│   └── pipeline.py                 # Ingest 流程编排入口
│
├── graph/                          # Layer 1 → Layer 2（已部分实现）
│   ├── __init__.py
│   ├── artifact_reader.py          # 读取 reviewed artifacts
│   ├── models.py                   # 图谱节点、关系、事件与状态模型
│   ├── planner.py                  # artifact -> graph state / JSONL events
│   ├── neo4j_store.py              # Neo4j 幂等写入与查询
│   └── state_store.py              # graph_state / graph_updates 持久化
│
├── wiki/                           # Layer 1 → Layer 2（规划，未实现）
│   ├── __init__.py
│   ├── graph.py                    # 科学发现图谱
│   ├── index.py                    # wiki/index.md 维护
│   ├── concepts.py                 # wiki/concepts/ 维护
│   └── log.py                      # wiki/log.md 维护
│
├── retrieval/                      # Layer 2 → Layer 3（规划，未实现）
│   ├── __init__.py
│   ├── embedder.py                 # 向量化文档，写入 ChromaDB
│   ├── vector_store.py             # ChromaDB 封装
│   ├── graph_query.py              # 图谱遍历查询（溯源、路径、邻居）
│   └── search.py                   # 统一检索入口（向量 + 图谱混合）
│
├── api/                            # HTTP API（规划，未实现）
│   ├── __init__.py
│   ├── app.py                      # FastAPI 应用入口
│   └── routes/
│       ├── papers.py               # /papers 路由
│       ├── search.py               # /search 路由
│       └── graph.py                # /graph 路由
│
└── cli/                            # 命令行工具
    ├── __init__.py
    └── main.py                     # typer CLI 入口

tests/
├── unit/                           # 单元测试（无 LLM 调用）
│   ├── test_latex_parser.py
│   ├── test_models.py
│   └── test_cli.py
├── integration/                    # 集成测试（Mock LLM）
│   └── test_pipeline.py
└── fixtures/
    ├── sample_paper/               # 测试用论文片段
    │   ├── main.tex
    │   └── sections/
    └── expected/                   # 期望输出（快照测试）
        ├── summary.md
        ├── prior_works.json
        └── sci_pattern.json

prompts/                            # Prompt 模板（与代码解耦）
├── paper_summary.py
├── paper_summary_v2.py
├── prior_work_prompt.py
├── sci_pattern_classify_prompt.py
└── pattern_taxonomy.json

pyproject.toml
.env.example
AGENTS.md                           # LLM 操作规范
```

### 包依赖关系

```mermaid
graph LR
    core["core<br/>(models, enums, config)"]
    ingestion["ingestion<br/>(latex, llm, generators)"]
    wiki["wiki<br/>(graph, index, concepts)"]
    retrieval["retrieval<br/>(embed, search, graph_query)"]
    api["api<br/>(FastAPI routes)"]
    cli["cli<br/>(typer commands)"]

    core --> ingestion
    core --> wiki
    core --> retrieval
    ingestion --> wiki
    wiki --> retrieval
    retrieval --> api
    retrieval --> cli
    wiki --> api
    wiki --> cli
```



`core` 是零依赖的纯领域模型层，所有其他模块单向依赖它，不允许循环依赖。

---

## 四、数据模型设计

### 4.1 核心枚举

```python
# core/enums.py

class PriorWorkRole(str, Enum):
    BASELINE = "Baseline"
    INSPIRATION = "Inspiration"
    GAP_IDENTIFICATION = "Gap Identification"
    FOUNDATION = "Foundation"
    EXTENSION = "Extension"
    RELATED_PROBLEM = "Related Problem"

class ContributionType(str, Enum):
    PROBLEM_DEFINITION = "问题定义型"
    MECHANISM_EXPLANATION = "机制解释型"
    METHOD_IMPROVEMENT = "方法改进型"
    BENCHMARK = "评测基准型"

class PatternID(str, Enum):
    P01 = "P01"  # Gap-Driven Reframing
    P02 = "P02"  # Cross-Domain Synthesis
    # ... P03-P15
```

### 4.2 论文元数据（YAML Frontmatter）

```mermaid
erDiagram
    PaperMeta {
        str slug PK "唯一标识符，如 controlnet-2023"
        str title
        list authors
        int year
        str venue
        str arxiv_id
        list tags
        PatternID primary_pattern FK
        list secondary_patterns
        ContributionType contribution_type
        bool reviewed "人工审查状态"
        date added_date
    }
```



### 4.3 先前工作文档

```mermaid
erDiagram
    PriorWorksDoc {
        str target_slug FK
        str target_title
        str target_venue
        int target_year
        list prior_works
        str synthesis_narrative
    }
    PriorWorkEntry {
        str title
        str authors
        int year
        str arxiv_id "可空"
        PriorWorkRole role
        str relationship_sentence
    }
    PriorWorksDoc ||--o{ PriorWorkEntry : "contains"
```



### 4.4 科学范式分类文档

```mermaid
erDiagram
    SciPatternDoc {
        str target_slug FK
        str target_title
        PatternID primary_pattern
        str primary_pattern_name
        list secondary_patterns
        list secondary_pattern_names
        str confidence "high | medium | low"
        str reasoning
    }
```



### 4.5 图谱节点与边

```mermaid
erDiagram
    GraphNode {
        str id PK "slug（已收录）或 title-hash（外部节点）"
        str title
        int year
        str venue
        str arxiv_id
        PatternID primary_pattern
        list tags
        bool is_external "true 表示尚未完整收录"
    }
    GraphEdge {
        str source FK "源论文 id（当前论文）"
        str target FK "目标论文 id（前作）"
        PriorWorkRole role
        str relationship_sentence
    }
    GraphNode ||--o{ GraphEdge : "source"
    GraphNode ||--o{ GraphEdge : "target"
```



### 4.6 完整数据流 ER 图

```mermaid
erDiagram
    PaperMeta ||--|| PriorWorksDoc : "slug"
    PaperMeta ||--|| SciPatternDoc : "slug"
    PaperMeta ||--o{ GraphNode : "becomes"
    PriorWorksDoc ||--o{ GraphEdge : "generates"
    GraphNode ||--o{ GraphEdge : "source/target"
```



---

## 五、核心模块详细设计

### 5.1 `ingestion/latex_parser.py`

**职责**：将 `raw/{slug}/` 目录下的 LaTeX 文件预处理为适合 LLM 消费的纯文本。

#### 核心问题

LaTeX 论文有两种常见组织形式，Parser 需要同时支持：

```latex
% 方式 A：内容全写在 main.tex
\section{Introduction}
正文内容直接写在这里...

% 方式 B：main.tex 通过 \input / \include 引用子文件
\input{sections/introduction}
\include{method}
\input{experiments.tex}
```

因此处理分为两个阶段：**先把所有文件合并**，再**按 `\section` 定位目标章节**。

#### 完整处理流程

```mermaid
flowchart TD
    A["raw/{slug}/ 目录"] --> B[读取 main.tex]
    B --> C["递归内联 \\input / \\include\n遇到引用则读取目标文件内容替换"]
    C --> D{目标文件中\n还有 \\input?}
    D -->|是| C
    D -->|否| E[完整合并文本]

    E --> F["提取 \\begin{abstract}...\\end{abstract}"]
    E --> G["正则切分所有 \\section 块\n得到 章节名->内容 映射"]

    G --> H["关键词模糊匹配\n将章节名归类为\nIntro / RelatedWork / Method / Experiments"]
    H --> I{命中目标章节?}
    I -->|是| J[加入目标内容]
    I -->|否| K[丢弃]

    F --> L["去噪处理\n- 去除 figure/algorithm 环境（保留 caption）\n- 去除注释行（% 开头）\n- 去除纯格式命令（vspace/hspace 等）\n- 保留 equation / table / 正文"]
    J --> L

    L --> M["按优先级拼接\nAbstract → Intro → Method\n→ RelatedWork → Experiments"]
    M --> N{超出 32k 字符?}
    N -->|是| O["按优先级裁剪\n保留 Method 和 Intro\n截断 Experiments"]
    N -->|否| P[直接输出]
    O --> P
    P --> Q[ParsedPaper]
```

#### 章节名模糊匹配规则

论文章节名没有统一规范，使用关键词列表匹配：

```python
TARGET_SECTIONS: dict[str, list[str]] = {
    "introduction": ["introduction", "motivation", "overview"],
    "related_work": ["related work", "background", "prior work",
                     "literature review", "related"],
    "method":       ["method", "approach", "model", "framework",
                     "proposed", "our method", "methodology",
                     "technique", "algorithm"],
    "experiments":  ["experiment", "evaluation", "result",
                     "empirical", "analysis", "benchmark"],
}
# abstract 单独处理：走 \begin{abstract}...\end{abstract} 环境
```

匹配逻辑：章节名小写后，检查是否包含任意关键词。`\subsection` 也参与匹配，但优先级低于 `\section`（用于 Related Work 作为 Introduction 子节的情况）。

#### 边界情况处理

| 情况 | 处理方式 |
|------|---------|
| `\section[短标题]{完整标题}` | 提取 `{...}` 中的完整标题，忽略 `[...]` |
| `\input{method}` 无扩展名 | 自动补 `.tex` 后缀后在 `paper_dir` 下搜索 |
| `\input{sections/method}` 带路径 | 相对于 `paper_dir` 解析路径 |
| 循环 `\input` 引用 | 维护 `visited: set[Path]`，已访问文件跳过 |
| Related Work 是 Intro 的 `\subsection` | `\subsection` 也做关键词匹配，优先级低于 `\section` |
| 论文无 `main.tex` | 按文件大小降序取最大的 `.tex` 文件作为入口 |

#### 接口定义

```python
@dataclass
class ParsedPaper:
    raw_text: str                      # 预处理后正文（Abstract + 目标章节）
    estimated_tokens: int              # 估算 token 数（字符数 / 3.5）
    source_files: list[str]            # 实际内联的 .tex 文件列表
    matched_sections: dict[str, bool]  # 各目标章节是否命中

class LaTeXParser:
    def parse(self, paper_dir: Path) -> ParsedPaper: ...

    def _inline_inputs(self, tex_path: Path, base_dir: Path,
                       visited: set[Path] | None = None) -> str:
        """递归内联 \\input / \\include，防止循环引用"""

    def _split_by_section(self, text: str) -> dict[str, str]:
        """用正则 r'\\section\\*?\\{([^}]+)\\}' 切分，返回 {章节名: 内容}"""

    def _match_target_sections(self, sections: dict[str, str]
                                ) -> dict[str, str]:
        """关键词模糊匹配，返回 {intro/method/... : content}"""

    def _strip_latex_noise(self, text: str) -> str:
        """去除 figure/algorithm 环境、注释行、格式命令"""

    def _assemble_and_truncate(self, abstract: str,
                                sections: dict[str, str],
                                max_chars: int = 32000) -> str:
        """按优先级拼接并按需截断"""
```

---

### 5.2 `ingestion/llm_client.py`

**职责**：抽象 LLM API 调用，屏蔽具体模型差异，支持 OpenAI-compatible 模型切换。

```mermaid
classDiagram
    class LLMClient {
        <<abstract>>
        +complete(system: str, user: str) str
        +complete_json(system: str, user: str, schema: type) BaseModel
    }
    class OpenAIClient {
        -api_key: str
        -model: str
        +complete()
        +complete_json()
    }
    LLMClient <|-- OpenAIClient
```



**关键设计**：

- `complete_json()` 内置 JSON 解析重试，处理 LLM 输出非法 JSON 的情况
- 通过 `API_KEY` / `BASE_URL` / `MODEL_NAME` 以及 OpenAI-style aliases 配置模型
- 当前已实现 OpenAI-compatible 客户端；token 用量与成本追踪仍未实现

---

### 5.3 `ingestion/pipeline.py`

**职责**：Ingest 流程的编排入口，当前只协调 Parser + 三个 Generator，并写入 Layer 1 artifacts。Wiki 更新属于后续 `review` 阶段，尚未实现。

```mermaid
sequenceDiagram
    actor User
    participant CLI
    participant Pipeline
    participant LaTeXParser
    participant SummaryGen
    participant PriorWorksGen
    participant PatternGen
    participant WikiManager

    User->>CLI: paper-wiki ingest {slug} [slug ...] / ingest-all
    CLI->>Pipeline: run(slug)
    Pipeline->>LaTeXParser: parse(raw/slug/)
    LaTeXParser-->>Pipeline: ParsedPaper

    Pipeline->>SummaryGen: generate(parsed_paper)
    SummaryGen-->>Pipeline: summary.md

    Pipeline->>PriorWorksGen: generate(parsed_paper)
    PriorWorksGen-->>Pipeline: prior_works.json

    Pipeline->>PatternGen: generate(parsed_paper)
    PatternGen-->>Pipeline: sci_pattern.json

    Pipeline->>Pipeline: 写入 artifacts/{slug}/
    Pipeline-->>User: 三件套生成完毕，请人工审查

    Note over User,WikiManager: 以下为规划中的 review 入库阶段
    User->>CLI: paper-wiki review {slug}
    CLI->>WikiManager: update_all(slug)
    WikiManager->>WikiManager: 更新图谱、index.md、log.md
```



**已实现关键设计**：

- Pipeline 保持单篇论文职责，CLI 负责把单个或多个 slug 逐个送入 Pipeline
- CLI 的 `ingest-all` 会扫描 `raw/` 下包含 `.tex` 的论文目录，默认只选择未生成完整三件套的 slug；`--overwrite` 会选择全部 raw 论文
- 默认不覆盖已有 artifact，只有传入 `--overwrite` 时才允许重写三件套
- 支持切换 summary、prior works、sci pattern 三类 prompt
- ingest 不写入 `wiki/`、图谱、embedding 或检索索引

**规划设计**：

- `ingest` 和 `review` 是两个独立命令，强制分离"生成"与"入库"
- Pipeline 支持 `--only summary|prior_works|pattern` flag，可单独重跑某一步
- review 阶段只接收 `reviewed=true` 的 artifact，并触发 Wiki / Graph / Index 更新

---

### 5.4 `wiki/graph.py`（规划，未实现）

**职责**：维护科学发现图谱，提供增删查操作，持久化为 JSON 文件。

```mermaid
classDiagram
    class GraphManager {
        -graph: nx.DiGraph
        -nodes_path: Path
        -edges_path: Path
        +load() void
        +save() void
        +add_paper(meta: PaperMeta) void
        +add_prior_works(doc: PriorWorksDoc) void
        +get_ancestors(slug, depth) list~GraphNode~
        +get_descendants(slug, depth) list~GraphNode~
        +find_path(from_slug, to_slug) list~GraphNode~
        +get_by_pattern(pattern_id) list~GraphNode~
        +get_pattern_distribution() dict
    }
```



**关键设计**：

- 启动时从 JSON 重建 NetworkX 图（内存操作），每次写操作后同步持久化
- 外部节点（`is_external=True`）由 `add_prior_works()` 自动创建，当后续 Ingest 同名论文时自动升级为完整节点
- 外部节点的 ID 生成规则：`{title_normalized}-{year}`，归一化处理大小写和标点

---

### 5.5 `retrieval/` 模块（规划，未实现）

**两种检索模式**：

```mermaid
graph TB
    Q[用户查询] --> R{查询类型}
    R -->|自然语言| VS[向量检索<br/>ChromaDB]
    R -->|结构化| GQ[图谱查询<br/>NetworkX]

    VS --> C1[summaries collection<br/>按 H2 章节切块]
    VS --> C2[prior_works collection<br/>relationship_sentence 粒度]
    VS --> C3[concepts collection<br/>整篇概念页]

    GQ --> GQ1[溯源/影响力查询]
    GQ --> GQ2[范式聚类查询]
    GQ --> GQ3[路径查询]

    C1 & C2 & C3 --> MR[元数据过滤<br/>venue/year/pattern/tags]
    MR --> SR[SearchResult 列表]
    GQ1 & GQ2 & GQ3 --> SR
```



**ChromaDB Collections 设计**：


| Collection    | 文档单元                     | Metadata 字段                                            |
| ------------- | ------------------------ | ------------------------------------------------------ |
| `summaries`   | summary.md 按 H2 章节切分     | slug, year, venue, primary_pattern, tags, section_name |
| `prior_works` | 每条 relationship_sentence | slug, role, target_title                               |
| `concepts`    | 整篇概念 Markdown            | concept_name, related_slugs                            |


**关键设计**：只有 `reviewed=true` 的 artifact 才会被 Embedder 索引，通过读取 frontmatter 中的 `reviewed` 字段控制。

---

## 六、API 设计（规划，未实现）

### 6.1 路由总览

```
POST   /ingest/{slug}                   触发 Ingest（仅生成三件套）
PATCH  /papers/{slug}/review            标记为已审查，触发 Wiki 更新
GET    /papers/{slug}                   获取论文详情（三件套）
GET    /papers/{slug}/summary           获取 summary.md 内容
GET    /papers/{slug}/prior-works       获取 prior_works.json
GET    /papers/{slug}/pattern           获取 sci_pattern.json

GET    /search?q=&pattern=&year_min=&venue=   语义搜索 + 元数据过滤
GET    /graph/{slug}/ancestors?depth=2        溯源查询
GET    /graph/{slug}/descendants?depth=2      影响力查询
GET    /graph/path?from={slug}&to={slug}      路径查询
GET    /graph/pattern/{pattern_id}            范式聚类

GET    /wiki/index                      获取全局目录
GET    /wiki/concepts/{name}            获取概念页
GET    /wiki/log?limit=20              获取操作日志
```

### 6.2 统一响应格式

```python
class APIResponse(BaseModel, Generic[T]):
    data: T
    total: int | None = None
    message: str = "ok"

class SearchResult(BaseModel):
    slug: str
    title: str
    score: float
    source_type: str       # "summary" | "prior_works" | "concept"
    section: str | None    # 命中的章节名
    snippet: str           # 上下文片段
    metadata: PaperMeta
```

---

## 七、CLI 命令设计

```bash
# 已实现：Layer 0 / Layer 1
paper-wiki parse {slug}                       # 解析 LaTeX，打印 Layer 0 摘要
paper-wiki ingest {slug}                      # 生成单篇三件套（不入库）
paper-wiki ingest {slug1} {slug2} --overwrite # 批量生成多篇三件套
paper-wiki ingest-all                         # 扫描 raw/，生成未完成三件套的论文
paper-wiki graph plan {slug} [slug ...]      # 从 reviewed artifacts 生成图谱快照和 JSONL 事件
paper-wiki graph apply                        # 把未应用事件写入 Neo4j

# 规划：人工审查与入库
paper-wiki review {slug}              # 审查后入库（更新图谱+索引）

# 规划：查询
paper-wiki search "RAG with graph"
paper-wiki graph ancestors lora-2022 --depth 3
paper-wiki graph path gpt3-2020 rlhf-2022

# 规划：维护
paper-wiki lint                        # Wiki 健康检查
paper-wiki rebuild-index               # 重建向量索引
paper-wiki status                      # 显示库统计（论文数、图谱节点/边数等）

# 规划：服务
paper-wiki serve --port 8000           # 启动 HTTP API
```

---

## 八、测试策略

### 8.1 测试分层

```
tests/
├── unit/           纯逻辑测试，无 IO、无 LLM
├── integration/    含 IO，LLM 调用 Mock
└── e2e/            真实调用（仅 CI 偶尔运行，需要 API Key）
```

### 8.2 各层测试重点

**单元测试**（快速，始终运行）：


| 模块             | 测试内容                    |
| -------------- | ----------------------- |
| `latex_parser` | 噪声去除、章节提取、截断逻辑、多文件拼接    |
| `models`       | Pydantic 验证规则、序列化/反序列化  |
| `graph`        | 节点增删、路径查找、外部节点升级、模式分布统计 |
| `enums`        | 枚举值合法性                  |


**集成测试**（较慢，PR 时运行）：

```mermaid
sequenceDiagram
    participant Test
    participant Pipeline
    participant MockLLM
    participant FS as 文件系统

    Test->>MockLLM: 注册固定返回值（fixtures/expected/）
    Test->>Pipeline: run("test-paper")
    Pipeline->>MockLLM: complete_json(...)
    MockLLM-->>Pipeline: 返回预设 fixture
    Pipeline->>FS: 写入 artifacts/test-paper/
    Test->>FS: 读取产物
    Test->>Test: 断言与 expected/ 快照匹配
```



**快照测试**：`expected/` 目录保存期望的 artifact 内容，用于检测 Prompt 修改导致的输出变化是否符合预期（类似前端的 snapshot test）。

**E2E 测试**：使用真实小论文（~5 页），调用真实 LLM API，验证端到端流程不报错、产物结构合法。仅在 `CI_E2E=true` 时运行。

---

## 九、可维护性设计

### 9.1 Prompt 与代码完全解耦

所有 Prompt 存放在 `prompts/` 目录的独立文件中，生成器代码只负责加载 Prompt、填充变量、调用 API。**修改 Prompt 不需要改代码**，也不会触发代码层的测试失败。

```mermaid
graph LR
    P[prompts/paper_summary_v2.py] -->|读取| SG[SummaryGenerator]
    SG -->|调用| LLM[LLMClient]
```



### 9.2 LLM 可替换

通过 `LLMClient` 抽象层隔离模型调用。当前已实现 OpenAI-compatible 客户端，可通过 `.env` 中的 `API_KEY`、`BASE_URL`、`MODEL_NAME` 切换 OpenAI、DeepSeek 或兼容网关；Claude 等非 OpenAI-compatible 客户端仍属于规划。

### 9.3 幂等设计

当前 Layer 1 写操作采用显式覆盖策略：默认拒绝覆盖已有三件套，只有传入 `--overwrite` 时才重写 artifacts。`ingest-all` 默认通过完整三件套是否存在来跳过已处理论文，传入 `--overwrite` 时会把所有 raw 论文送入同一条 pipeline 重跑。后续重建索引应先清空目标 ChromaDB collection 再重新索引，保证失败后可以安全重试。

### 9.4 渐进式引入

系统各层相互独立，可以分阶段上线：

```mermaid
gantt
    title 渐进式交付计划
    dateFormat  YYYY-MM-DD
    section Phase 1 核心
    LaTeXParser + LLMClient         :p1a, 2026-06-25, 3d
    三个 Generator                   :p1b, after p1a, 3d
    CLI parse/ingest 命令            :done, p1c, after p1b, 2d
    CLI review 命令                  :p1d, after p1c, 2d

    section Phase 2 Wiki
    GraphManager                    :p2a, after p1c, 3d
    IndexManager + LogManager       :p2b, after p2a, 2d
    CLI graph/lint 命令              :p2c, after p2b, 2d

    section Phase 3 检索
    Embedder + VectorStore          :p3a, after p2c, 3d
    SearchAPI + GraphQuery API      :p3b, after p3a, 3d
    FastAPI 服务                    :p3c, after p3b, 2d
```



### 9.5 日志与可观测性

- 所有 LLM 调用记录：模型名、token 用量、耗时、成本估算（写入 `wiki/log.md`）
- 所有失败的 JSON 解析记录原始 LLM 响应（写入 `logs/llm_errors/`），便于 Prompt 调试
- `paper-wiki status` 命令可实时查看库的健康状态

---

## 十、待决策事项（留 Review 时讨论）


| 问题           | 选项 A                              | 选项 B                    | 建议                        |
| ------------ | --------------------------------- | ----------------------- | ------------------------- |
| LaTeX 截取策略   | 章节感知（取 Intro+Method+Related Work） |                         | 选 A，信息密度更高                |
| RAG 检索粒度     | H2 章节级（~300 tokens）               | 整篇 summary（~800 tokens） | 先做 H2 章节级，实测再调            |
| 概念页触发阈值      | ≥2 篇论文涉及时自动创建                     | 手动触发                    | 先手动触发，避免低质量自动创建           |
| Embedding 方案 | OpenAI `text-embedding-3-small`   | 本地 `bge-m3`             | 先用 OpenAI，有隐私需求再换本地       |


---
