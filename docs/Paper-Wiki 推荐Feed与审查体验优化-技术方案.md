# Paper-Wiki 推荐Feed与审查体验优化 技术方案

> 版本：v1.1（已实现）| 创建：2026-07-14 | 最后更新：2026-07-15 | 状态：已按本文档实现并通过测试
> 关联文档：[Paper-Wiki 需求文档](<./Paper-Wiki%20需求文档.md>) 第十/十一节、[Paper2Recommend 技术方案](<./Paper2Recommend%20技术方案.md>)
> 背景：M7（Web接入发现层）落地并投入使用后，用户对 `TodayFeed`/`PaperDetail` 的真实使用反馈，本文档是这批反馈对齐后的实现方案。
> **实现状态（2026-07-15）**：七节列出的改动清单已全部落地，`pytest` 79 passed（新增13个）、前端 `vitest` 10 passed（新增3个），`tsc --noEmit`/`vite build` 均通过。

---

## 一、本次优化的五个点（背景摘要）

1. `TodayFeed` 卡片摘要目前是 arXiv 原始 abstract（未处理、经常带 `arXiv:xxx Announce Type: new Abstract:` 这类样板前缀），需要用大模型生成一句话摘要用于"粗筛"
2. 推荐理由文案 `与《XXX》相似度92%` 的书名号改成引号
3. `刷新推荐` / `批量生成` 是异步 job，目前轮询只能看到 `pending/running/succeeded/failed` 四态，中间是黑箱，需要有可读的中间进度
4. `PaperDetail` 里 Markdown 正文的图片经常过大，需要按比例收窄显示
5. `PaperDetail` 页面结构调整：去掉 Sections/Figures/References 统计方块；标题等元信息本身要能编辑（而不是另外新增一份重复展示）；Prior Works 只把 title/authors/year/arxiv_id 做成可编辑字段；Reviewed 拆成两个独立开关（中栏"元信息"、右栏"前作"）

以下按模块给出确定的实现方案。**除非本文档另有说明，所有改动都复用现有接口/组件，不新增数据库或后台队列框架**，延续 [Paper-Wiki 技术方案_v1.md](<./Paper-Wiki%20技术方案_v1.md>) 第十一节的既定原则。

---

## 二、TodayFeed 候选摘要生成

### 2.1 架构边界

`discovery/` 包保持不感知 LLM 不变（`discovery.recommend.run()` 签名和行为都不变，现有单测不用改）。新增的 LLM 摘要生成是 **Web 层的业务能力**，放在 `web/services/candidate_summary.py`，只在 `POST /api/recommendations/refresh` 这个已有的异步 job 里被调用，不影响 `paper-wiki recommend run` CLI（如果后面 CLI 也要这个能力，加一个 `--with-summary` flag 单独评估，本次不做）。

### 2.2 Prompt（新增 `prompts/candidate_summary_v1.py`）

```python
candidate_summary_system_prompt="""
你是一位AI科研助理，任务是把一篇论文的标题和摘要，压缩成一句约50字的中文简介，帮读者在几秒内粗筛"这篇论文大概讲什么、值不值得进一步看"。

## 写作要求（必须遵守）
1. 只使用提供的标题和摘要中的信息，不要编造摘要中没有提到的内容。
2. 用中文撰写一句话，长度控制在50字左右（不超过60字）。
3. 直接说清楚这篇论文做了什么，不要写"本文提出了一种方法"这类空话，也不要复述标题。
4. 不使用任何Markdown标记，输出纯文本，因为这段文字会直接展示在推荐卡片里。
"""


candidate_summary_user_prompt="""
请用一句话（约50字）概括下面这篇论文，用于推荐信息流的粗筛展示：

标题：{PAPER_TITLE}

摘要：
{PAPER_ABSTRACT}
"""
```

复用 `paper_wiki.ingestion.prompt_loader.resolve_prompt_path` / `load_prompt_module` 加载，`{PAPER_TITLE}`/`{PAPER_ABSTRACT}` 用 `.replace()` 替换，跟 `SummaryGenerator` 的加载方式完全一致。

### 2.3 数据模型

`discovery/models.py: RankedCandidate` 新增字段：

```python
class RankedCandidate(SearchCandidate):
    reason: str = ""
    display_summary: str = ""   # 新增：LLM生成的一句话卡片摘要，失败/未生成时为空
```

### 2.4 生成逻辑（`web/services/candidate_summary.py`，新文件）

```python
def enrich_with_display_summary(snapshot: RecommendationSnapshot, settings: Settings) -> None:
    """对 snapshot.candidates 逐条生成卡片摘要，原地写入 display_summary，并重新落盘快照文件。"""
```

- 只处理 `snapshot.candidates`（已经是排序后裁到 `max_papers` 的最终列表，比如15条），不处理整个候选池，成本可控
- 复用 `paper_wiki.ingestion.llm_client.build_llm_client(settings)`
- 逐条调用 `llm.complete(system, user)`，单条失败（超时/异常）只 `logger.warning` 并跳过，`display_summary` 留空，不影响其它候选、不中断整个 job
- 生成过程中按 2.5 小节的日志约定打点，用于进度展示
- 生成完成后，用 `snapshot.model_dump_json(indent=2)` 重新写回 `settings.resolved_artifacts_dir() / ".recommendations" / f"{snapshot.date}.json"` 和 `latest.json`（跟 `recommend.run()` 里落盘逻辑一致的两个路径），这样刷新一次之后，`GET /api/recommendations/today` 直接读到的就是带摘要的版本，不需要重复调用 LLM

### 2.5 接入点（`web/routers/recommendations.py: refresh()`）

```python
def task() -> dict[str, Any]:
    snapshot = recommend_service.run(max_papers=..., arxiv_query=..., settings=settings)
    candidate_summary.enrich_with_display_summary(snapshot, settings)
    return snapshot.model_dump(mode="json")
```

### 2.6 前端展示（`CandidateCard.tsx`）

摘要文本改为 `candidate.display_summary || candidate.abstract`（跟 VibeIDEA `tldr || abstract` 的兜底思路一致）。`client.ts` 的 `SearchCandidate`/`RankedCandidate` 类型加 `display_summary: string`。

---

## 三、推荐理由文案调整

`discovery/recommend.py: _rerank()` 里：

```python
# 改前
reason = f"与《{ordered_corpus[best_index].title}》相似度{max(0.0, sims[best_index]) * 100:.0f}%"
# 改后
reason = f'与 "{ordered_corpus[best_index].title}" 相似度{max(0.0, sims[best_index]) * 100:.0f}%'
```

仅此一处字符串改动。

---

## 四、异步任务进度提示

### 4.1 设计原则

不引入 WebSocket/SSE（v1 技术方案已明确不做实时推送），沿用现有"轮询 `GET /api/jobs/{job_id}`"模型，只是让轮询返回的内容从"四个状态词"升级成"一句人话+图标"。**不直接把后端 `logger.info` 的原始文本透传给用户**——原始日志是给开发者看的技术文本，用户看到的必须是翻译后的、可读的短句。

### 4.2 新增日志点（只加日志，不改任何函数签名/返回值）

| 文件 | 位置 | 新增日志 |
| --- | --- | --- |
| `discovery/recommend.py: run()` | 拉取语料前 | `logger.info("正在获取 Zotero 口味语料")` |
| `discovery/recommend.py: run()` | 拉取候选池前 | `logger.info("正在拉取 arXiv 候选池")` |
| `discovery/recommend.py: run()` | 调用 `_rerank()` 前 | `logger.info("正在计算相似度排序")` |
| `web/services/candidate_summary.py` | 循环体内 | `logger.info("正在为候选生成摘要 (%d/%d)", index, total)` |
| `discovery/sources/arxiv_source.py: fetch()` | `find_main_tex()` 成功之后、`_download_pdf()` 之前 | `logger.info("已找到主文件，正在下载 PDF")` |

### 4.3 翻译表（新文件 `web/services/progress_messages.py`）

```python
def translate_progress(raw_message: str) -> str:
    """把内部 logger 文本映射成用户可读的图标+短句；未识别的一律走兜底文案。"""
```

匹配方式：对 `raw_message` 做子串包含匹配（`in` 判断即可，不需要正则），按下表从上到下第一个命中的规则生效：

| 匹配子串（出现在原始日志里） | 展示文案 |
| --- | --- |
| `开始生成每日推荐` | 🔍 正在生成今日推荐... |
| `正在获取 Zotero 口味语料` | 📚 正在读取你的阅读口味... |
| `正在拉取 arXiv 候选池` | 🌐 正在抓取 arXiv 最新论文... |
| `正在计算相似度排序` | 🧮 正在计算相似度排序... |
| `正在为候选生成摘要` | 📝 正在生成候选摘要...（可直接把原始日志里的 `(4/15)` 部分拼进展示文案，因为那部分对用户也是有效信息） |
| `推荐生成完成` | ✅ 推荐生成完成 |
| `sentence-transformers不可用` | ⚠️ 相似度模型不可用，按原始顺序展示 |
| `开始拉取：arxiv_id=` | 📥 正在下载论文源码... |
| `已找到主文件，正在下载 PDF` | 📄 已找到论文主文件，正在下载 PDF... |
| `步骤 1/` 且包含 `构建 Layer1 通用 assets` | 📄 正在解析论文结构... |
| `assets 已存在，复用 assets` | 📄 已找到现有论文结构，复用中... |
| 包含 `生成 summary.md` | 📝 正在生成精读摘要... |
| 包含 `生成 prior_works.json` | 🔗 正在分析前序工作... |
| 包含 `生成 sci_pattern.json` | 🏷️ 正在识别科学范式... |
| `已将 prior_works` | ✨ 正在整合摘要内容... |
| `Layer1 语义产物生成完成` | ✅ 生成完成 |
| （以上都不匹配） | ⚙️ 处理中... |

批量生成走"先 fetch 再 ingest"路径（`discovery.search.fetch(and_ingest=True)`）时，fetch 和 ingest 内部的日志会按时间顺序自然接力，翻译表统一处理，不需要区分调用来源。

### 4.4 JobManager 改动（`web/services/job_manager.py`）

- `JobRecord` 新增字段：`progress: str | None = None`
- `_run(job_id, task)` 执行 `task()` 期间，挂一个临时 `logging.Handler`：
  - 监听 `paper_wiki` 根 logger（这样 `paper_wiki.ingestion.pipeline`、`paper_wiki.discovery.recommend`、`paper_wiki.discovery.sources.arxiv_source`、`paper_wiki.web.services.candidate_summary` 这些子 logger 的消息都能被捕获，不用逐个 attach）
  - `emit()` 里先判断 `record.thread == threading.get_ident()`（`ThreadPoolExecutor` 是多个 worker 线程并发跑不同 job，必须按线程号过滤，否则会串台）再处理，只处理 `INFO` 级别
  - 调用 `translate_progress(record.getMessage())`，通过 `self._update(job_id, progress=translated)` 写入
  - `task()` 结束后（无论成功失败）要 `logger.removeHandler(handler)`，避免 handler 泄漏

### 4.5 API 契约

`JobResponse`（`web/schemas/job.py`）新增 `progress: str | None = None`。前端 `client.ts: JobResponse` 类型同步加 `progress: string | null`。

### 4.6 前端展示

`pollJob()` 的 `onUpdate` 回调里能拿到 `progress`，三处消费方分别展示：
- `TodayFeed.tsx`：每张卡片状态徽标旁边多一行 `job.progress` 文本（批量生成时逐条候选各自独立展示）
- `SearchAndAdd.tsx`（按ID拉取 tab）：现有的 `status` 提示文案改成实时展示 `job.progress`
- `PaperDetail.tsx`（regenerateSummary）：现有的 `Job ${status}` 提示改成优先展示 `job.progress`，没有的时候兜底显示 `Job ${status}`

---

## 五、图片按比例显示

`web/frontend/src/styles.css`，`.markdown-body img` 规则调整：

```css
.markdown-body img {
  @apply my-5 mx-auto block border border-line bg-white cursor-zoom-in;
  max-width: 70%;
}
```

新增一个轻量 lightbox 交互（新文件 `web/frontend/src/components/ImageLightbox.tsx` 或直接在 `MarkdownView.tsx` 内用一个 `expandedSrc: string | null` 的 state + 一个全屏遮罩层实现，点击图片时 `setExpandedSrc(src)`，遮罩层点击关闭）：点击缩小图 → 全屏/接近全屏展示原图，再点一次关闭。不引入第三方 lightbox 依赖，几十行 CSS+state 就够。

70% 是初始值，具体数值实现时可以按几张真实论文截图效果微调，不是硬性要求。

---

## 六、PaperDetail 三栏重构

### 6.1 中栏：去掉统计方块，页头本身变为可编辑

删除现有的：

```tsx
<div className="mb-4 grid grid-cols-3 gap-2 text-sm">
  <div className="metric"><strong>{detail.sections_count}</strong><span>Sections</span></div>
  <div className="metric"><strong>{detail.figures_count}</strong><span>Figures</span></div>
  <div className="metric"><strong>{detail.references_count}</strong><span>References</span></div>
</div>
```

页头区域（现在的 `<h1>{title}</h1>` + `<p>authors · venue · year</p>`）改成跟 Summary 一样的 preview/edit 双态：

- **预览态**（默认）：跟现在展示效果一致，纯文本
- **编辑态**：`<h1>` 变成 `<input>`（标题），下面一行拆成 authors（逗号分隔文本框，保存时 `split(',').map(trim)` 成 `string[]`）、venue、year（`type="number"`）、arxiv_id 四个小输入框
- 编辑态下方新增一个 **"Review"按钮**：点击后 `PATCH /api/papers/{slug}/meta`，body 携带编辑后的 title/authors/venue/year/arxiv_id + `meta_reviewed: true` + `expected_updated_at`；成功后弹出"元信息已更新"提示（复用现有 `status` 提示条即可，不需要新组件），并自动切回预览态

`references_count`/`figures_count`/`sections_count` 这三个字段本身不用从后端 `PaperDetail` schema 里删，只是前端不再展示——万一以后别处要用（比如 6.3 提到的管理页面存储统计）还能接着复用，不折腾后端契约。

### 6.2 右栏：Prior Works 只暴露需要核对的字段

`PriorWorksView.tsx` 编辑态从"整块 JSON textarea"改成逐条结构化编辑：

- 每条 prior work：Title / Authors / Year / arXiv ID 四个可编辑输入框
- `role`（角色徽标）、`relationship_sentence`（关系说明）**只读展示**，不提供编辑框（这两个是 LLM 分析结论，本次审查重点是身份信息不是分析结论）
- `synthesis_narrative`（综合叙述）保持只读展示，不编辑
- 新增/删除某条 prior work 的能力保留（对应需求文档 10.4 节"+ 添加新前作"/"删除"），只是编辑时只让改那四个字段
- 底部一个 **"Review"按钮**：点击后依次调用 `PATCH /api/papers/{slug}/prior-works`（保存编辑后的 prior_works 内容，接口不变）→ 成功后再调用 `PATCH /api/papers/{slug}/meta`，body 只带 `prior_works_reviewed: true` + 最新的 `expected_updated_at`（用第一步返回的 `updated_at`，避免乐观锁冲突）；两步都成功后弹出"前作信息已更新"提示

### 6.3 数据模型：Reviewed 拆成两个开关

`assets/models.py: PaperAssetMeta` 新增两个字段：

```python
class PaperAssetMeta(BaseModel):
    ...
    reviewed: bool = False            # 含义不变，但改为服务端派生值，不再接受客户端直接赋值
    meta_reviewed: bool = False       # 新增：中栏"元信息+摘要"是否已审查
    prior_works_reviewed: bool = False  # 新增：右栏"前作"是否已审查
```

**派生规则**：`reviewed = meta_reviewed and prior_works_reviewed`，这个计算只在 `PaperRepository` 写入路径里做一次，不放进 Pydantic 校验器（避免 `PaperAssetMeta` 单独被外部代码构造/校验时也强制触发这条业务规则，校验器应该只管字段本身合法性，不管跨字段业务派生）。

**Web 层改动**：
- `web/schemas/paper.py: PaperMetaPatch` 去掉 `reviewed: bool | None` 字段（不再接受客户端直接设置），新增 `meta_reviewed: bool | None = None` 和 `prior_works_reviewed: bool | None = None`
- `web/services/paper_repository.py: update_meta()` 的 `mutate()` 闭包，在 `manifest.paper = PaperAssetMeta.model_validate(values)` 之前，加一行：

```python
values["reviewed"] = bool(values.get("meta_reviewed")) and bool(values.get("prior_works_reviewed"))
```

**历史数据迁移**：现有 `manifest.json` 如果是 `reviewed: true`（旧的单开关标记的），升级后 `meta_reviewed`/`prior_works_reviewed` 会因为字段缺失而落到默认值 `False`，直接反算 `reviewed` 就会变回 `False`，相当于已审查的论文"退回"待审查状态。为避免这个回退，在 `PaperAssetMeta` 上加一个 `@model_validator(mode="after")`：

```python
@model_validator(mode="after")
def _migrate_legacy_reviewed_flag(self) -> "PaperAssetMeta":
    """兼容升级前只有单一 reviewed 字段的旧 manifest：
    读到 reviewed=True 但两个新字段还是默认值时，隐式当作两者都已审查过。"""
    if self.reviewed and not self.meta_reviewed and not self.prior_works_reviewed:
        object.__setattr__(self, "meta_reviewed", True)
        object.__setattr__(self, "prior_works_reviewed", True)
    return self
```

这条迁移只读时生效，不会主动重写磁盘上的 `manifest.json`；等这篇论文下次被任何一次 `update_meta`/`update_prior_works` 写操作触碰到，两个新字段就会被落盘固化，属于自然而然的懒迁移，不需要额外写一次性迁移脚本。

**已知影响面**（供后续实现者/评审参考，本次不需要处理）：`docs/Paper-Wiki 管理页面-需求文档.md` 3.1 节规划的 `POST /api/papers/batch-review`（body 里原本设想是 `{slugs, reviewed: bool}`）依赖单一 `reviewed` 字段直接赋值，这个改动落地后，那个尚未实现的接口需要相应调整为同时设置 `meta_reviewed` + `prior_works_reviewed`，而不是一个 `reviewed`——等管理页面那个模块真正排期实现时需要同步更新那份文档，本次不用现在改。

---

## 七、改动清单汇总（供实现者对照）

**新增文件**：
- `prompts/candidate_summary_v1.py`
- `web/services/candidate_summary.py`
- `web/services/progress_messages.py`
- `web/frontend/src/components/ImageLightbox.tsx`（或在 `MarkdownView.tsx` 内联实现，二选一）

**后端改动文件**：
- `discovery/models.py`：`RankedCandidate` 加 `display_summary`
- `discovery/recommend.py`：`_rerank()` 去书名号；`run()` 加3条日志
- `discovery/sources/arxiv_source.py`：`fetch()` 加1条日志
- `web/routers/recommendations.py`：`refresh()` 接入 `candidate_summary.enrich_with_display_summary`
- `web/services/job_manager.py`：`JobRecord` 加 `progress`；`_run()` 挂日志捕获 handler
- `web/schemas/job.py`：`JobResponse` 加 `progress`
- `web/schemas/paper.py`：`PaperMetaPatch` 去 `reviewed`，加 `meta_reviewed`/`prior_works_reviewed`
- `web/services/paper_repository.py`：`update_meta()` 派生 `reviewed`
- `assets/models.py`：`PaperAssetMeta` 加两个字段 + 迁移校验器

**前端改动文件**：
- `web/frontend/src/api/client.ts`：类型加字段（`display_summary`/`progress`/meta patch 两个新字段），`pollJob` 不变
- `web/frontend/src/components/CandidateCard.tsx`：摘要展示优先 `display_summary`
- `web/frontend/src/pages/TodayFeed.tsx`：卡片展示 `job.progress`
- `web/frontend/src/pages/SearchAndAdd.tsx`：fetch tab 展示 `job.progress`
- `web/frontend/src/pages/PaperDetail.tsx`：删统计方块；页头改可编辑；`regenerateSummary` 展示 `job.progress`
- `web/frontend/src/components/PriorWorksView.tsx`：编辑态改结构化字段编辑
- `web/frontend/src/styles.css`：图片样式

**测试改动（实现时需要同步补）**：
- `tests/unit/test_discovery_recommend.py`：书名号断言要改
- `tests/unit/test_web_paper_repository.py` / `test_web_routers.py`：`_write_demo_artifact` 等 fixture 里 `reviewed` 相关断言要适配两个新字段；新增迁移校验器的单测
- 新增 `tests/unit/test_candidate_summary.py`、`tests/unit/test_progress_messages.py`
- 前端 `Discovery.test.tsx`：mock 数据补 `display_summary`/`progress` 字段

**不涉及的范围（明确不做）**：
- 不引入 WebSocket/SSE
- 不改 CLI `paper-wiki recommend run` 行为
- 不做 Prompt 在线编辑
- `docs/Paper-Wiki 管理页面-需求文档.md` 里的模块本次不涉及，只是六.3 节提了一个未来的影响面
