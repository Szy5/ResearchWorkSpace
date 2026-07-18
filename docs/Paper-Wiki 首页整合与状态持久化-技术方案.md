# Paper-Wiki 首页整合与状态持久化 技术方案

> 版本：v2.0（草案，待实施）| 创建：2026-07-15
> 关联文档：[Paper-Wiki 推荐Feed与审查体验优化-技术方案](<./Paper-Wiki%20推荐Feed与审查体验优化-技术方案.md>)（v1.1，已实现）、[DESIGN.md](../DESIGN.md)
> 背景：v1.1 落地并投入使用后，用户实际使用中提出 5 点新反馈，本文档是这批反馈的确定实现方案。**本文档只是方案，不在本轮直接改代码**，供后续 Agent 按此实施。

---

## 一、本次要解决的五个问题（背景摘要）

1. 推荐理由里的书名号 `《》` 问题——v1.1 §三 已经把 `discovery/recommend.py` 里模板拼接的 `reason` 字符串从 `《X》` 改成了 `"X"`，但用户反馈问题**没有解决**——说明书名号出现在别的地方，不是那处模板字符串。
2. `今日推荐` 和 `检索 / 添加` 应该合并到同一个首页里；两边卡片被勾选后应该"移动"到第三个区域做批量生成，且生成时要有一个固定区域展示进度日志。
3. `全部论文` 页面当前分三块（论文列表 / 正文 / 右侧栏），下滑时这三块应该各自独立滚动，而不是混在一起；同时 `Publish` 面板应该放在右侧栏最上面，不是最下面。
4. 批量生成过程中如果切换到其它页面，生成状态/进度就消失了——这是因为承载状态的组件被卸载了，不是"设计问题"而是"状态生命周期"问题，必须挪到不随页面切换卸载的地方。
5. 下一轮改动要以 `DESIGN.md` 为基准做视觉重构，不是继续在旧的冷灰色调 + 无衬线标题上小修小补。

以下按模块给出确定的实现方案，尽量复用现有接口/组件/端点，**不涉及新的后端 API**（问题 1 涉及一处 prompt 文案调整 + 一个前端展示层归一化函数，问题 2/3/4/5 都是纯前端改动）。

---

## 二、书名号 `《》` → 直引号 `"…"`（真正的根因）

### 2.1 根因

v1.1 只修了 `discovery/recommend.py: _rerank()` 里那一处**确定性拼接**的 `reason` 字符串（`f'与 "{title}" 相似度...'`），这处代码本身没有书名号了（已核实：`src/paper_wiki/discovery/recommend.py:102` 现在就是直引号）。

用户看到的书名号来自**大模型自由生成的正文**，不受任何 f-string 模板控制：

- `summary.md`（`prompts/paper_summary_v3.py` 生成）在讨论相关工作/对比方法时，中文写作习惯性地用书名号引用论文/模型/数据集名字，比如"相比《BERT》……"。
- `prior_works.json` 的 `relationship_sentence` / `synthesis_narrative`（`prompts/prior_work_prompt.py` 生成）。
- 候选卡片一句话简介 `display_summary`（`prompts/candidate_summary_v1.py` 生成）。
- `sci_pattern.json` 的 `reasoning`（`prompts/sci_pattern_classify_prompt.py` 生成）。

这几处 prompt 目前都**没有**任何关于引用符号的格式约束，所以模型用不用书名号完全随机——这才是"改了却没解决"的真正原因：改的不是书名号真正的来源。

### 2.2 修复方案（两层，缺一不可）

**第一层（治本，管未来新生成的内容）**：在上述四个 prompt 的"写作要求"里各加一条规则（措辞对齐现有 `paper_summary_v3.py` 的编号列表风格）：

```
N. **引用格式**：正文中提到其他论文、模型、数据集名称时使用直引号 "…"，禁止使用中文书名号《…》。
```

- `prompts/paper_summary_v3.py`（当前正在使用的版本；`paper_summary_v2.py`/`paper_summary.py` 是历史版本，视是否还被引用决定要不要同步改，实现时用 `grep -rn "paper_summary_v2\|paper_summary\b"` 确认调用方）
- `prompts/prior_work_prompt.py`
- `prompts/candidate_summary_v1.py`
- `prompts/sci_pattern_classify_prompt.py`

**第二层（治标，覆盖已经生成、不会重新跑一遍的历史内容）**：新增一个前端共享工具函数，在渲染层做归一化，不依赖重新生成：

```ts
// web/frontend/src/utils/textFormat.ts
export function normalizeQuotes(text: string): string {
  return text.replace(/《([^《》]*)》/g, '"$1"')
}
```

接入点（凡是渲染大模型自由生成文本的地方都过一遍）：

- `MarkdownView.tsx`：`normalizeMathDelimiters()` 旁边加一步 `normalizeQuotes()`，覆盖 `summary.md` 正文。
- `CandidateCard.tsx`：`candidate.display_summary || candidate.abstract` 和 `reason` 渲染前过一遍。
- `PriorWorksView.tsx`：预览态的 `relationship_sentence`、`synthesis_narrative` 渲染前过一遍。

两层加起来：新内容从生成源头就不会再出现书名号；旧内容不用重新跑 ingestion，前端渲染时就已经是直引号。

---

## 三、首页整合：今日推荐 + 检索/添加 + 批量生成暂存区

### 3.1 现状问题

`TodayFeed.tsx` 和 `SearchAndAdd.tsx` 是两个平级 tab，且各自维护自己的 `selected: Set<string>` 和批量生成逻辑（`TodayFeed.generate()`）；`SearchAndAdd` 的关键词检索 tab 只能"加入待筛选池"（调用 `App.stageCandidates`，写入提升到 `App` 的 `staged` 状态），并**不能**在自己的 tab 里直接批量生成——用户得手动切回"今日推荐"才能对已暂存的候选做生成。这就是用户说的"没有真正放在一起"。

### 3.2 目标结构

把 `view` 从 `'today' | 'search' | 'papers'` 简化为 `'home' | 'papers'`，新建 `Home.tsx` 承载三个区域：

```
┌─────────────────────────────────────────┐
│ Region 1  今日推荐（原 TodayFeed 的候选池） │
├─────────────────────────────────────────┤
│ Region 2  检索 / 添加（原 SearchAndAdd）  │
└─────────────────────────────────────────┘
        （勾选后卡片从上面两个区域消失）
┌─────────────────────────────────────────┐
│ Region 3  生成暂存区（新组件 GenerationTray）│
│   · 已暂存卡片的精简列表 + 移出按钮        │
│   · [批量生成] 按钮                       │
│   · 固定高度的进度日志列表（逐条 job.progress）│
└─────────────────────────────────────────┘
```

Region 3 不是 `Home.tsx` 的子组件，而是提升到 `App.tsx` 里**始终挂载**的一个新组件 `GenerationTray.tsx`（贴屏幕底部，`fixed inset-x-0 bottom-0`，有内容时展开、无内容时收起——沿用现有 `selected.size > 0` 才出现的交互习惯，只是把它从页面级提升为 App 级）。原因见第五节——这同时是问题 2 和问题 4 的共同解法。

### 3.3 交互模型

- Region 1 / Region 2 的卡片勾选框不再各自维护 `selected` 状态，改成直接调用共享 hook 的 `stage(item)`；一旦被 stage，该卡片从所在 Region 的候选池数组里 filter 掉（视觉上"移动到了"Region 3）。
- Region 3 里每条暂存项有一个"移出"按钮调用 `unstage(key)`，移出后该卡片重新出现在原来的 Region（今日推荐的候选按原始顺序插回；搜索结果本来就还在 `results` 数组里，只是不再置灰）。
- "批量生成"按钮调用 `generate()`：对当前所有暂存项跑 `batchIngest`（已有接口，逻辑照搬现有 `TodayFeed.generate()`），随后用现有 `pollJob` 轮询，把每条的 `progress` 写回共享状态供 Region 3 的日志列表展示。
- `SearchAndAdd.tsx` 里"按 arXiv ID 拉取"（`FetchByIdTab`）的"拉取后立即生成"选项保持不变（这是单条同步操作，不走暂存池，语义上不冲突）；"仅拉取源码"分支现在改成调用 `stage()` 直接把拉取到的论文放进 Region 3，而不是像现在这样只是"加入待筛选池"却看不到反馈。

### 3.4 涉及文件

**新增**：

- `web/frontend/src/hooks/useBatchGeneration.ts`：把 `App.tsx` 现有的 `staged`/`stageCandidates` 状态，和原来在 `TodayFeed.tsx` 里的 `jobStatus`/`generating`/`generate()` 逻辑合并成一个 hook，返回 `{ staged, jobStatus, generating, stage, unstage, generate }`。只在 `App.tsx` 里实例化一次。
- `web/frontend/src/components/GenerationTray.tsx`：Region 3 的 UI，消费 `useBatchGeneration()` 的返回值。
- `web/frontend/src/pages/Home.tsx`：合并 `TodayFeed.tsx`（今日推荐候选池渲染 + 刷新按钮）与 `SearchAndAdd.tsx`（关键词检索 tab + arXiv ID 拉取 tab）的展示逻辑，勾选行为改为调用 props 传入的 `stage`。

**删除/退役**：

- `TodayFeed.tsx`、`SearchAndAdd.tsx`——渲染逻辑迁移进 `Home.tsx` 后即可删除，避免留死代码。

**改动**：

- `App.tsx`：`view` 类型简化为 `'home' | 'papers'`；导航项从 4 个减到 3 个（首页 / 全部论文 / 待审查——待审查沿用现有"papers 视图 + `libraryFilter=false`"跳转方式不变）；实例化 `useBatchGeneration()`，把返回值传给 `Home`，并在 `<main>` 外层渲染 `<GenerationTray />`。
- `CandidateCard.tsx`：勾选回调语义不变（`onToggleSelect` 换成调用 `stage`/`unstage`，props 接口基本不用改）。

---

## 四、`全部论文` 页面：三栏独立滚动 + Publish 置顶

### 4.1 现状问题（根因，不是"随便改改 CSS"）

当前 `.workbench` / `.workbench-panels` / `react-resizable-panels` 的 `Panel` 都没有显式约束 `overflow`，所以内容溢出时找不到边界，实际表现是整个窗口一起滚（或者滚动行为不可预测），而不是用户期望的"论文列表 / 正文 / 右侧栏"三个独立滚动容器。

`PaperDetail.tsx` 内部现在是一个 `grid grid-cols-1 gap-5 2xl:grid-cols-[minmax(0,1fr)_360px]`，`<article>`（正文）和 `<aside>`（右侧栏）是这个 grid 的两列，两者都没有 `overflow-y-auto`。**即使**补上 `overflow-y-auto`，grid/flex 子元素默认 `min-height: auto`，会撑开父容器而不是触发内部滚动条——这是最容易被漏掉的一步，必须显式加 `min-h-0`，否则加了 `overflow-y-auto` 也不会生效。

### 4.2 修复方案

- `App.tsx`：`Group`（`workbench-panels`）和两个 `Panel`（`paper-list`/`paper-detail`）各加 `overflow-hidden`，把"允许内部滚动、不允许自己被撑高"的边界立在这一层。
- `Dashboard.tsx`：最外层 `<section>` 从 `min-h-[calc(100vh-112px)]` 改成 `h-full min-h-0 overflow-y-auto`——论文列表自己独立滚。
- `PaperDetail.tsx`：
  - 承载 `<article>`/`<aside>` 的 grid 容器加 `h-full min-h-0`。
  - `<article className="min-w-0">` 改成 `<article className="min-w-0 h-full min-h-0 overflow-y-auto">`——正文独立滚。
  - `<aside className="space-y-4">` 改成 `<aside className="space-y-4 h-full min-h-0 overflow-y-auto">`——右侧栏独立滚，跟正文互不影响。
- `PaperDetail.tsx` 的 `<aside>` 内部三个 `<section>` 调整渲染顺序：**Publish 面板放最前面**，然后 Pattern，然后 `PriorWorksView`（原顺序是 Pattern → PriorWorksView → Publish）。

---

## 五、批量生成状态不能因为切页面而消失

### 5.1 根因

`App.tsx` 用条件渲染切页面：`{view === 'today' ? <TodayFeed .../> : null}`——切到别的 `view` 时 `TodayFeed` 直接被卸载。`TodayFeed` 内部的 `selected`/`jobStatus`/`generating` 都是组件本地 `useState`，组件一卸载，这些状态就没了。

要注意：卸载并**不会**取消已经发出去的生成任务——`generate()` 里的 `pollJob` 只是失去了能更新的 UI，后端 job 其实还在跑，用户切回来看到的是"什么都没发生过"，但服务端可能已经生成完了，这是纯粹的前端状态生命周期问题，不是后端问题。

### 5.2 修复方案

跟第三节是同一个解法，这里只是把"为什么这样设计"讲清楚：**批量生成相关的状态必须活在一个不会因为 `view` 切换而卸载的地方**。具体做法就是第三节提到的 `useBatchGeneration()` hook + `GenerationTray.tsx`：

- hook 实例化在 `App.tsx`（`App` 本身永远不卸载，只有它的子视图会切换），状态天然跨页面存活。
- `GenerationTray` 渲染在 `<main>` 外层、`view` 判断之外，不管当前在首页还是全部论文页，只要有暂存/生成中的任务，这个固定区域就一直可见。

这样第二节的"进度日志区域"和第四节的"切页面状态消失"是同一次改动解决的两个问题，不需要分别处理。

---

## 六、按 `DESIGN.md` 做视觉重构

本文档不重复 `DESIGN.md` 已经写清楚的 token/组件映射，只列出**这一轮涉及的文件范围**，具体数值/字体/间距一律以 `DESIGN.md` 为准：

- `web/frontend/tailwind.config.js`：`theme.extend.colors` 按 `DESIGN.md` colors 小节补齐（`canvas`/`body`/`muted`/`moss-deep`/`moss-soft`/`copper-soft`/`error`/`error-soft`/`error-line`/`code-ink`，并把现有 `ink`/`fog`/`line` 的十六进制值换成 `DESIGN.md` 里偏暖的新值）；`theme.extend.fontFamily` 加 `serif: ['Source Serif 4', 'Georgia', 'Times New Roman', 'serif']`。
- `index.html`：加 `Source Serif 4`（400/600 两个字重）的 `<link>`/`@font-face`（若要求离线可用，自托管字体文件到 `web/frontend/public/fonts/`，不用 Google CDN）。
- `styles.css`：按 `DESIGN.md`"Components"小节逐条改——`.markdown-body h1/h2/h3` 换成 `font-serif`；`.paper-card h2`/`.candidate-card h3`/`.prior-card h3` 换成 `font-serif`；页面级标题（"My Papers"、"今日推荐"、"检索 / 添加论文"）的 `text-xl font-semibold` 换成 `font-serif text-[22px]`；`.paper-card-active`/`.candidate-card-selected` 去掉 `shadow-sm`，改成 `border-2 border-moss`（对应 DESIGN.md "Elevation & Depth" Level 2）。
- 本节改动应该放在第二～四节的结构性改动**之后**做（先把 `Home.tsx`/`GenerationTray.tsx`/三栏滚动这些新结构搭好，再统一套色板和字体，避免边改结构边改样式互相踩踏，返工两次）。

---

## 七、改动清单汇总（供实现者对照）

**新增文件**：

- `web/frontend/src/hooks/useBatchGeneration.ts`
- `web/frontend/src/components/GenerationTray.tsx`
- `web/frontend/src/pages/Home.tsx`
- `web/frontend/src/utils/textFormat.ts`（`normalizeQuotes`）

**删除文件**：

- `web/frontend/src/pages/TodayFeed.tsx`
- `web/frontend/src/pages/SearchAndAdd.tsx`

**后端/Prompt 改动**：

- `prompts/paper_summary_v3.py` / `prompts/prior_work_prompt.py` / `prompts/candidate_summary_v1.py` / `prompts/sci_pattern_classify_prompt.py`：各加一条"引用格式用直引号，不用书名号"的写作要求。

**前端结构改动**：

- `App.tsx`：`view` 类型简化、导航项减到 3 个、实例化 `useBatchGeneration`、挂载 `GenerationTray`、`Group`/`Panel` 加 `overflow-hidden`。
- `Dashboard.tsx`：独立滚动容器。
- `PaperDetail.tsx`：正文/右侧栏独立滚动容器（含 `min-h-0` 修正）、`<aside>` 内 Publish 面板置顶、勾选逻辑收敛到共享 hook。
- `CandidateCard.tsx`：勾选回调接共享 hook；`display_summary`/`reason` 渲染前过 `normalizeQuotes`。
- `MarkdownView.tsx`：正文渲染前过 `normalizeQuotes`。
- `PriorWorksView.tsx`：`relationship_sentence`/`synthesis_narrative` 预览态过 `normalizeQuotes`。

**视觉改动**（在结构改动之后做，细节见 `DESIGN.md`）：

- `tailwind.config.js`、`index.html`（字体加载）、`styles.css`。

**测试改动（实现时需要同步补）**：

- `web/frontend/src/pages/Discovery.test.tsx`：原本测 `TodayFeed`/`SearchAndAdd` 相关行为的用例迁到测 `Home.tsx`；书名号相关 mock 数据（`'与你读过的《Deep Learning》相似度92%'`）要么改成直引号数据验证 `normalizeQuotes`，要么保留书名号数据专门断言归一化生效。
- `App.test.tsx`：nav 项从 4 个变 3 个，快照/断言需要同步。
- 新增 `web/frontend/src/hooks/useBatchGeneration.test.ts`：覆盖 stage/unstage/跨"页面切换"状态不丢失（用 `App.tsx` 整体渲染，切换 `view` 后断言暂存状态还在）。
- 新增 `web/frontend/src/utils/textFormat.test.ts`：`normalizeQuotes` 的单测。
- `tests/unit/test_summary_generator.py`（或对应 prompt 单测）：如果有对 prompt 文本内容的断言，同步补新增的引用格式规则行。

**不涉及的范围（明确不做）**：

- 不新增/修改任何后端 API 契约（`display_summary`/`progress`/`batchIngest` 等已有字段和端点直接复用）。
- 不引入全局状态管理库（Redux/Zustand 等）——一个自定义 hook + 提升到 `App.tsx` 已经够用，符合现有代码"能用 props 就不用额外抽象"的风格。
- 不改 `PaperDetail` 的 preview/edit 双态逻辑、`meta_reviewed`/`prior_works_reviewed` 拆分（v1.1 已完成，本次不动）。
