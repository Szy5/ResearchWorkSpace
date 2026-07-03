# Paper-Wiki 需求文档

> 版本：v1.3 | 创建：2026-06-23 | 最后更新：2026-07-03 | 状态：持续维护

---

## 一、背景与动机

### 核心问题

传统的论文阅读是线性的、孤立的、易遗忘的。大量阅读之后面临以下困境：

- 过几周就忘了一篇论文的核心方法和贡献
- 无法快速定位"谁解决过类似问题，用的什么思路"
- 看不到自己阅读的论文之间的思想传承关系
- 无法从全局视角感知一个方向的知识演化脉络

### 目标

构建一个**个人科研论文知识库**，它不只是摘要的堆砌，而是一个随时间不断积累、自动关联、可检索的活性知识系统。具体来说，它需要能回答以下四类问题：

| 问题类型 | 示例                                                                 |
| -------- | -------------------------------------------------------------------- |
| 论文速查 | "这篇论文的核心贡献是什么？它解决了什么问题？"                       |
| 思想溯源 | "这个工作站在谁的肩膀上？它的直接思想来源是哪几篇？"                 |
| 范式分析 | "这篇论文用了什么科学创新范式？和我领域里的其他论文相比有什么不同？" |
| 语义检索 | "给定一个研究方向，哪些论文最相关？它们之间如何关联？"               |

### 思想来源

本系统融合了两个核心理念：

- **[LLM Wiki 模式](./llm_wiki.md)**：以 LLM 为维护者、以持久化 Markdown 为载体的增量知识库。知识一次提炼，长期积累，不在每次查询时重新推导。
- **[Sci-Reasoning](https://github.com/AmberLJC/Sci-Reasoning)**：从论文中提取结构化思想脉络与科学创新范式分类，将科研创新行为解码为可分析、可比较的标准模式。

---

## 二、系统整体架构

系统由四个层次构成，每个层次在前一层的基础上生成：

```
Layer 0: 原始资料层
  用户手动上传的论文原始文件（LaTeX 源文件 + PDF），只读，不修改。
      ↓  LLM 解析，生成结构化产物
Layer 1: 论文产物层
  每篇论文对应三个结构化文件（三件套），是后续一切的信息来源。
      ↓  LLM 整合，跨论文分析
Layer 2: 知识 Wiki 层
  跨论文的知识组织：全局索引、概念页、研究方向页、科学发现图谱。
      ↓  嵌入 + 索引
Layer 3: 检索接口层
  对外暴露的语义搜索与图谱查询接口，支持 RAG 调用。
```

---

## 三、需求实现状态总览

本文档是长期维护文档。每次新增、删除或调整功能时，都应同步更新本节，明确哪些需求已经完成、哪些仍在规划中、哪些仍需决策。

### 3.1 当前已实现需求

| 范围 | 需求 | 当前状态 |
| ---- | ---- | -------- |
| Layer 0 | 从 `raw/{paper-slug}/` 读取原始 LaTeX 资料，保持原始文件只读 | 已实现 |
| Layer 0 | 自动识别入口 `.tex` 文件，支持 `main.tex`、包含 `\begin{document}` 的文件、最大 `.tex` 文件兜底 | 已实现 |
| Layer 0 | 递归内联 `\input` / `\include`，解析多文件 LaTeX 论文 | 已实现 |
| Layer 0 | 抽取 abstract、introduction、related work、method、experiments 等核心章节 | 已实现 |
| Layer 0 | 提供 `paper-wiki parse <slug>`，不调用 LLM，仅打印解析摘要 | 已实现 |
| Layer 1 | 调用 OpenAI-compatible LLM 生成 `summary.md` | 已实现 |
| Layer 1 | 调用 OpenAI-compatible LLM 生成 `prior_works.json`，并用 Pydantic 校验；主论文元信息不再在该文件重复保存 | 已实现 |
| Layer 1 | 调用 OpenAI-compatible LLM 生成 `sci_pattern.json`，并用 Pydantic 校验；主论文元信息不再在该文件重复保存 | 已实现 |
| Layer 1 | `summary.md` 自动包含 YAML frontmatter，默认 `reviewed: false` | 已实现 |
| Layer 1 | 生成文件只写入 `artifacts/{paper-slug}/`，不更新 wiki、图谱、索引 | 已实现 |
| CLI | 提供 `paper-wiki ingest <slug>` 生成单篇论文 Layer 1 三件套 | 已实现 |
| CLI | 提供 `paper-wiki ingest <slug> [slug ...]` 批量生成多篇论文 Layer 1 三件套 | 已实现 |
| CLI | 提供 `paper-wiki ingest-all` 扫描 `raw/`，为未生成完整三件套的论文批量生成 Layer 1 artifacts | 已实现 |
| Layer 2 | 提供 `paper-wiki graph plan <slug> [slug ...]`，从 reviewed artifacts 生成图谱快照与 JSONL 增量事件 | 已实现 |
| Layer 2 | 提供 `paper-wiki graph apply`，把 JSONL 增量事件幂等写入 Neo4j | 已实现 |
| Layer 2 | 支持 `graph_state/` 与 `graph_updates/graph_updates.jsonl` 增量更新流程 | 已实现 |
| CLI | 支持 `--overwrite` 控制是否覆盖已有 Layer 1 产物 | 已实现 |
| CLI | 支持 `--summary-prompt`、`--prior-works-prompt`、`--sci-pattern-prompt` 切换 prompt | 已实现 |
| 配置 | 从 `.env` 读取 `API_KEY`、`BASE_URL`、`MODEL_NAME` 及 OpenAI-style aliases，并支持 `NEO4J_URI`、`NEO4J_USERNAME`、`NEO4J_PASSWORD`、`NEO4J_DATABASE` | 已实现 |
| 测试 | 覆盖 LaTeX parser、Pydantic models、mock LLM pipeline、CLI 多 slug ingest、raw 待处理发现与 graph planner 增量事件 | 已实现 |

### 3.2 尚未实现需求

| 范围 | 需求 | 当前状态 |
| ---- | ---- | -------- |
| 人工审查 | `paper-wiki review <slug>` 命令，将人工确认后的 artifact 标记为可入库 | 未实现 |
| Layer 2 | `wiki/index.md` 全局论文目录自动维护 | 未实现 |
| Layer 2 | `wiki/log.md` 操作日志自动追加 | 未实现 |
| Layer 2 | `wiki/concepts/` 概念页生成与维护 | 未实现 |
| Layer 2 | `wiki/topics/` 研究方向页生成与维护 | 未实现 |
| Layer 2 | 科学发现图谱节点、边的构建、持久化与查询；当前已实现 Paper 节点、prior work typed 关系、Neo4j 增量入库，详见 [Neo4j 科学发现图谱需求与技术方案](./Neo4j%20科学发现图谱需求与技术方案.md) | 部分实现 |
| Layer 3 | summary、prior works、concepts 的 embedding 与向量索引 | 未实现 |
| Layer 3 | 自然语言语义检索、GraphRAG、图谱路径查询 | 未实现 |
| Layer 3 | FastAPI HTTP API | 未实现 |
| CLI | `search`、`lint`、`rebuild-index`、`status`、`serve` 等命令 | 未实现 |
| 可观测性 | LLM token 用量、成本统计、错误响应归档 | 未实现 |
| E2E | 真实 API smoke test 与 CI 条件执行策略 | 未实现 |

### 3.3 待决策需求

| 问题 | 当前状态 |
| ---- | -------- |
| RAG 索引粒度：整篇 summary、章节级、句子级或混合粒度 | 待决策 |
| GraphRAG 与普通 RAG 的职责边界、结果融合方式 | 待决策 |
| 图谱可视化方式 | 待决策 |
| 概念页自动创建阈值与人工审核流程 | 待决策 |
| 外部前作节点的去重、规范化、升级为完整论文节点的策略 | 待决策 |

---

## 四、数据组织结构

```
Paper-wiki/
├── raw/                    # Layer 0：原始论文文件（只读）
│   └── {paper-slug}/       # 每篇论文一个文件夹，命名为 {论文名称}
│       ├── main.tex        # LaTeX 主文件（推荐；也支持自动识别其他入口 .tex）
│       ├── paper.pdf       # PDF 文件（可选；当前实现主要读取 LaTeX）
│       └── ...             # 其他 .tex、图片、bib 等
│
├── artifacts/              # Layer 1：每篇论文三件套
│   └── {paper-slug}/
│       ├── summary.md         # 论文精读 Markdown
│       ├── prior_works.json   # 先前工作与思想谱系
│       └── sci_pattern.json   # 科学创新范式分类
│
├── graph_state/            # Layer 2：图谱本地快照（已部分实现）
│   ├── papers.json
│   └── prior_work_relations.json
│
├── graph_updates/          # Layer 2：图谱增量事件日志（已部分实现）
│   ├── graph_updates.jsonl
│   └── checkpoint.json
│
├── wiki/                   # Layer 2：跨论文知识库（规划，未实现）
│   ├── index.md            # 全局论文目录
│   ├── log.md              # 操作日志
│   ├── concepts/           # 概念页（如 RLHF、KV Cache）
│   ├── topics/             # 研究方向概述页
│   └── graph/              # 科学发现图谱数据
│       └── xxxx.json       # 存储图结构数据
│
└── prompts/                # LLM Prompt 模板
    ├── paper_summary.py                # 生成 summary.md 的 Prompt
    ├── paper_summary_v2.py             # 生成 summary.md 的新版 Prompt
    ├── prior_work_prompt.py            # 生成 prior_works.json 的 Prompt
    ├── sci_pattern_classify_prompt.py  # 生成 sci_pattern.json 的 Prompt
    └── pattern_taxonomy.json           # 15 种科学范式定义（参考 Sci-Reasoning）
```

**命名规则**：每篇论文的文件夹名（slug）格式为 `{论文名称}`，系统内作为唯一标识符。

---

## 五、论文三件套（Layer 1 核心）

每篇论文收录后，由 LLM 解析 LaTeX 源文件，生成三个结构化文件。这三个文件是整个系统的信息基础。

### 5.1 `summary.md` — 论文精读

**作用**：每篇论文最核心的阅读产物。将原始论文压缩为一份精炼、结构化、人类可读的 Markdown 文档。

**核心叙事逻辑**：按照"完整科研故事"的顺序组织内容——

> 发现了什么问题 → 前人怎么做的 → 还差什么 → 本文怎么做 → 结果如何

**文档结构**（六个章节，顺序固定）：

| 章节                     | 内容要求                                                                   |
| ------------------------ | -------------------------------------------------------------------------- |
| **研究背景**       | 现有方法的具体失败场景（不能笼统说"效果不好"），以及本文瞄准的那个具体缺口 |
| **本文主张与贡献** | 贡献类型（四选一）+ 2-4 条核心贡献，每条须对应"解决了什么问题"             |
| **方法**           | 不依赖公式也能看懂的直觉解释 + 关键设计决策 + 必要时的核心公式             |
| **实验与结果**     | 建立 Claim ↔ 实验的显式对应，不只罗列数字                                 |
| **边界与局限**     | 本文明确不解决什么，以及作者承认的局限                                     |
| **个人评注**       | 留给读者自行填写：关联论文、对自己研究的价值、存疑之处                     |

**贡献类型**（必须从四类中选一，记录在 Frontmatter）：

| 类型       | 含义                                 |
| ---------- | ------------------------------------ |
| 问题定义型 | 重新定义了一个失败场景或研究问题     |
| 机制解释型 | 揭示了模型/系统为什么表现出某种行为  |
| 方法改进型 | 提出了在已定义问题上表现更好的新方法 |
| 评测基准型 | 构建了数据集、基准或评测框架         |

---

### 5.2 `prior_works.json` — 先前工作与思想谱系

**作用**：捕捉这篇论文的"学术 DNA"——它直接站在哪些工作的肩膀上，每种前作发挥了什么角色。这是构建科学发现图谱的数据来源。

**内容要求**：识别 5-7 篇直接影响核心创新的前作，重质量而非数量。不包含通用工具类引用和泛泛相关工作。

**每条前作记录**包含：标题、作者、年份、arXiv ID（如有）、角色分类、与当前论文核心创新的直接关系描述（一句话）。

**文档还包含**：一段 200-300 字的综合叙述，描述这些前作如何共同启发了当前工作。

**六种角色分类**：

| 角色               | 含义                                         |
| ------------------ | -------------------------------------------- |
| Baseline           | 当前论文主要改进或对比的核心系统             |
| Inspiration        | 其具体思想直接激发了当前论文的关键创新       |
| Gap Identification | 其局限或失败推动了当前研究方向               |
| Foundation         | 引入了当前论文所用的核心问题定义/数据集/框架 |
| Extension          | 当前论文直接扩展、修改或泛化了其方法         |
| Related Problem    | 解决了紧密相关问题，其思路启发了当前工作     |

---

### 5.3 `sci_pattern.json` — 科学创新范式分类

**作用**：将论文的核心创新行为归入标准化的科学思维模式，便于跨论文横向比较和规律发现。

**内容要求**：指定主要范式（一个）、次要范式（0-2 个）、置信度，以及简短的分类理由。

**范式体系**：采用来自 [Sci-Reasoning](https://github.com/AmberLJC/Sci-Reasoning) 的 15 种科学创新范式（定义见 `prompts/pattern_taxonomy.json`）：

| ID  | 范式名称                           | 核心描述                                     |
| --- | ---------------------------------- | -------------------------------------------- |
| P01 | Gap-Driven Reframing               | 发现具体局限，将问题重新定义以适配更好的解法 |
| P02 | Cross-Domain Synthesis             | 从其他领域引入思想或机制，设计兼容层         |
| P03 | Representation Shift               | 替换核心表示或原语，简化问题结构             |
| P04 | Modular Pipeline Composition       | 将复杂任务分解为可组合的专用模块             |
| P05 | Data & Evaluation Engineering      | 构建数据集、基准或评测框架，让目标可测量     |
| P06 | Principled Probabilistic Modeling  | 以概率模型替换启发式方法，量化不确定性       |
| P07 | Formal-Experimental Tightening     | 实验观察→理论形式化→预测验证的闭环         |
| P08 | Approximation Engineering          | 设计保持理论性质的可扩展近似方案             |
| P09 | Inference-Time Control             | 以推理时控制代替重训练，实现灵活行为调整     |
| P10 | Inject Structural Inductive Bias   | 将领域结构（对称性、局部性）注入模型         |
| P11 | Multiscale & Hierarchical Modeling | 粗到细的层次建模，高效捕捉长程结构           |
| P12 | Mechanistic Decomposition          | 分解可解释机制并用因果干预验证               |
| P13 | Adversary Modeling                 | 显式建模对手行为以增强鲁棒性                 |
| P14 | Numerics & Systems Co-design       | 算法与底层实现协同设计以实现实际加速         |
| P15 | Data-Centric Optimization          | 以数据选择和生成为主要性能杠杆               |

---

## 六、科学发现图谱（Layer 2 核心，未实现）

### 6.1 概念

这是整个系统最有价值的"涌现"产物。当收录的论文积累到一定数量后，以论文为节点、以先前工作关系为有向边，自然形成一张**研究思想传承图**。

```Shell
         [VAE, 2013]
              │ Foundation
              ▼
    [Diffusion Model, 2020] ◄─── Inspiration ─── [Score Matching, 2019]
              │
              │ Gap Identification
              ▼
     [LDM (Stable Diffusion), 2022]
              │ Extension
              ▼
     [ControlNet, 2023]
```

### 6.2 节点

（节点中包含什么属性待商榷）

### 6.3 边

每条有向边来自 `prior_works.json` 中的一条记录，包含：源论文（当前论文）、目标论文（前作）、关系角色、关系描述一句话。

### 6.4 图谱支持的查询类型

| 查询       | 描述                                                           |
| ---------- | -------------------------------------------------------------- |
| 溯源查询   | 从某篇论文出发，沿 Foundation/Inspiration 关系向上追溯思想来源 |
| 影响力查询 | 找出所有以某篇论文为前作的后续工作                             |
| 范式聚类   | 按科学范式筛选论文节点，发现同范式下的方法演进                 |
| 范式空白   | 统计范式组合分布，发现覆盖稀少的组合，辅助发现研究机会         |
| 关联路径   | 查找两篇论文之间是否存在思想传承路径                           |

---

## 七、Wiki 知识层（Layer 2，未实现）

Wiki 层是跨论文的知识组织，由 LLM 在 Ingest 过程中自动维护。

### 7.1 全局目录（`wiki/index.md`）

按时间倒序列出所有已收录论文，每条记录包含：slug、标题、年份、发表会议、主要范式、一句话摘要。是 LLM 进行查询时的入口。

### 7.2 操作日志（`wiki/log.md`）

追加式记录每次操作：时间、操作类型（收录/查询/维护）、涉及的论文、触发的 Wiki 更新。日志是系统演化的历史记录。

### 7.3 研究方向页（`wiki/topics/`）

宏观研究方向的综述，内容包括：该方向在收录论文中的演化时间线、核心未解决问题、该方向内论文的范式分布。由 LLM 基于已收录论文自动生成并更新。

---

## 八、核心工作流

### 8.1 Ingest（当前已实现：生成 Layer 1 三件套）

用户将论文 LaTeX 源文件和 PDF 放入 `raw/{slug}/` 目录。当前已实现的 Ingest 范围只包括 Layer 0 → Layer 1：

1. 解析 LaTeX 源文件，调用闭源大语言模型, 生成 `summary.md`
2. 解析 LaTeX 源文件，调用闭源大语言模型, 生成 `prior_works.json`
3. 解析 LaTeX 源文件，调用闭源大语言模型,  生成 `sci_pattern.json`

CLI 支持单篇或多篇论文：

```bash
paper-wiki ingest GraphWalker --overwrite
paper-wiki ingest GraphWalker 2508.00719 Search-Self-Play --overwrite
paper-wiki ingest-all
```

批量生成时按传入顺序逐篇处理；若某篇失败，后续论文仍会继续处理，命令最终以非零退出码标识存在失败。
`ingest-all` 会扫描 `raw/` 下所有包含 `.tex` 的论文目录，默认只处理未生成完整 `summary.md`、`prior_works.json`、`sci_pattern.json` 的论文；传入 `--overwrite` 时会重跑所有 raw 论文。该命令仍然只写入 `artifacts/{slug}/`，不会更新 Layer 2/Layer 3 资源。

完整收录工作流中的以下步骤仍未实现：

4. **人工审查**：检查三件套的关键元数据是否准确（标题、arXiv ID、前作列表等等），直接修改错误内容，确认后将 `reviewed` 标记为 `true`
5. 将新论文节点和关系边合并到科学发现图谱
6. 更新受影响的概念页（`wiki/concepts/`）
7. 更新全局目录（`wiki/index.md`）
8. 追加日志（`wiki/log.md`）

**人工审查是必要环节**。LLM 在提取前作信息时存在幻觉风险（论文标题不存在、arXiv ID 错误），只有通过人工确认（`reviewed: true`）的 artifact 才会被纳入图谱和 RAG 索引。

### 8.2 Query（知识检索，未实现）

收录若干论文后，通过两种方式查询：

**自然语言检索（语义查询）**：以自然语言提问，系统在 Wiki 中找到相关论文和概念页，综合回答。有价值的回答可以保存为 Wiki 新页面，让知识持续积累。

**图谱查询（结构化查询）**：按论文关系、范式、影响力等维度查询，返回论文列表或关系路径。

### 8.3 Lint（Wiki 健康检查，未实现）

定期检查 Wiki 的完整性和一致性，发现以下问题：

- 多篇论文频繁引用的前作，尚未以外部节点的形式记录
- 应当存在但还未创建的概念页
- 图谱中的孤立节点（无入边也无出边）
- summary.md 中的描述与后来收录论文存在矛盾之处

---

## 九、检索接口（Layer 3，未实现）

检索接口基于 Wiki 层的全部内容构建，对外提供查询能力：

检索应该分为 RAG检索和GrapRAG检索，这两种检索的粒度不同.

(待定)

| 查询类型   | 描述                                             |
| ---------- | ------------------------------------------------ |
| 语义搜索   | 以自然语言查询，返回相关论文和 Wiki 页面         |
| 元数据过滤 | 按范式、年份、发表会议、领域标签组合过滤         |
| 图谱邻居   | 给定一篇论文，返回其前作和后续工作               |
| 图谱路径   | 查询两篇论文之间的思想传承路径                   |
| 论文详情   | 返回指定论文的 summary、prior_works、sci_pattern |
| 概念检索   | 返回某概念相关的所有论文和概念页                 |

接口以 HTTP API 形式暴露，可供外部工具、Agent 及 RAG 系统调用。

---

## 十、尚待决策的问题

| 问题             | 选项                                   | 当前倾向                 |
| ---------------- | -------------------------------------- | ------------------------ |
| RAG 索引粒度     | 整篇 summary / 按章节切分 / 按句子切分 | 待定，需通过实际使用验证 |
| 图谱可视化方式   |                                        |                          |
| 概念页的触发阈值 | 被 N 篇以上论文涉及时自动创建          |                          |

---
