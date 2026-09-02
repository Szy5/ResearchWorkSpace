# Autonomous Knowledge Graph Exploration \\ with Adaptive Breadth-Depth Retrieval

> **核心主张**：通过把知识图（KG）检索任务建模为对两个最简工具的交替调用——全局词表搜索与一跳邻居扩展——可以让大型语言模型在不做额外任务/图谱训练的前提下，自适应地在“广度（coverage）”与“深度（multi-hop）”之间权衡，从而显著提升实体级检索质量，并能将该工具调用策略无标签蒸馏到小模型以降低推理成本。

## 1. 问题背景

### 1.1 现有方法的局限
- 相似度/检索式方法（例如基于文本索引或向量检索）：提供全局覆盖但通常“浅”——不能有效利用KG的关系结构来执行必需的多跳推理，因而在需要多跳证据链的查询上失败。
- 结构感知（structure-aware）检索：通过学习节点嵌入或把固定邻域编码进索引来捕捉局部结构，但通常对邻域大小或消息传递层数做出固定设计，面对更深或可变跳数的查询时需要额外复杂度或额外检索阶段，成本上升且泛化受限。
- 遍历（traversal）/代理式方法：能做多跳推理，但高度依赖正确的种子实体（seed）与起始定位；当查询涉及多个实体或未给出明确种子时，容易“锚定”错误区域导致错过其他相关子图。此外很多方法需要图/任务特定的训练（RL或监督策略），影响跨域迁移。
总结：现有方法往往在“广度”（覆盖全图的能力）与“深度”（按关系逐跳追踪证据）之间各取其一，缺乏在运行时基于查询自适应切换两者的轻量且不需训练的机制。

### 1.2 本文瞄准的缺口
- 需要一个训练-free、图原生且极简的操作接口，使得语言模型能在检索过程中动态决定何时做全局搜索以发现新的实体/线索，何时做局部邻居扩展以跟随关系链路，从而：
  - 不依赖预先选定的种子实体或预设的最大跳数；
  - 不做任务或图谱专属训练；
  - 在单一检索过程内协调“广度”与“深度”以覆盖多实体/多关系查询与多跳查询两类情形。

## 2. 贡献
类型：方法改进型

1. 解决了“广度-深度”权衡问题：提出 **ARK**（Autonomous Retrieval over KGs），将检索建模为对两类最小工具的交替调用——`Global Search`（基于节点描述的词表检索）与 `Neighborhood Exploration`（一跳邻居扩展）；通过让 LLM 控制工具选择，ARK 可以在运行时根据查询与已检索证据自适应选择广度优先或深度优先策略，从而同时处理多实体覆盖和多跳链路需求。
2. 训练-free 且图原生的检索范式：ARK 不依赖图/任务专用的训练、种子选择或固定跳深；检索过程是交互式的、可解释的，并且提供明确的推理时预算—性能权衡（例如工具调用预算和并行代理数量可调）。
3. 可蒸馏的交互策略：展示如何无标签地把大型教师模型的工具调用轨迹蒸馏到紧凑模型（`Qwen3-8B`），在保留大部分教师性能的同时显著降低推理成本——在若干数据集上实现了显著的绝对 Hit@1 提升。

## 3. 方法

### 3.1 核心思路
直观上，把 KG 检索拆成两类最基本的动作：
- 全局发现（breadth）：通过节点描述的文本检索把潜在相关实体带进视野，保证覆盖性，不受当前游走位置限制；
- 局部跟踪（depth）：通过从已发现实体做一跳邻居扩展来沿关系路径追踪因果/证据链。  

让 LLM 决定什么时候调用哪种动作，模型可以在“发现新实体区域”与“沿着关系链深入”之间自由切换，避免了依赖单一种子或预设跳数的缺陷。因为工具非常简单（仅两种操作），该方案无需额外训练即可在不同图谱/任务间迁移；而且通过记录调用轨迹，策略是可解释、可蒸馏的。

### 3.2 方法细节
- 工具集合（两类操作，写成接口形式）：
  - `Global Search(q, k)`：对查询 $q$ 在节点描述索引上进行词表/文本检索，返回 top-$k$ 节点候选集合 $S_{\text{global}}$（按字面/词汇相似度或倒排得分）。
  - `Neighborhood Exploration(v)`：给定节点 $v$，返回其一跳邻居集合 $N(v)$（携带节点文本与关系类型），可被视为单步拓展。
- 检索轨迹与预算：
  - 定义检索轨迹为 $\tau = (o_1, o_2, \dots, o_T)$，每一步 $o_t$ 为一次工具调用，$o_t \in \{\text{GlobalSearch}, \text{NeighborhoodExplore}\}$。轨迹长度受到调用预算 $B$ 的约束： $\sum_{t=1}^T c(o_t) \le B$，其中 $c(\cdot)$ 可为各工具的成本（可设为 1 或按开销加权）。
  - 在每一步，LLM 基于当前查询 $q$、历史检索结果与工具返回的节点文本输出下一步选择或终止信号。系统 prompt 指明可用的节点/关系类型、工具签名、输出格式与停止准则（实现细节公开在仓库）。
- 最终候选合并与排名：
  - 在轨迹结束后，把所有被发现的节点集合 $S_{\text{all}}$（包括全局搜索候选与邻居扩展得到的节点）合并并按简单策略排序（例如按检索得分/出现次数/语言模型生成的置信度）；使用标准实体检索指标评估最终排序（$\text{Hit}@1$, $\text{MRR}$）。
- 无监督蒸馏（label-free imitation）：
  - 使用教师模型在大量查询上生成工具调用轨迹（即 $\tau$ 序列）与最终候选排序作为“行为标签”；
  - 训练一个较小的学生模型（`Qwen3-8B`）以模仿在同样输入下选择工具与生成终止/输出决策，从而在推理时复制教师的检索策略而无需使用显式相关性标签。
- 设计要点与优势：
  - 不需要预设起始种子或最大跳数；
  - 在任何时刻全局搜索始终可用，避免了遍历方法的锚定错误；
  - 简化操作集降低策略学习与迁移难度，使得无标签蒸馏可行。

## 4. 实验与结果
- 评测设置：
  - 基准：使用 STaRK（异构、文本丰富的 KG 的实体级检索基准）评估（论文中在三个 STaRK 子图上测试）。
  - 指标：$\text{Hit}@1$ 与 $\text{MRR}$。
  - 对比方法：检索式基线、代理/遍历式训练-free 方法及结构感知检索器等。
  - 额外分析：通过改变工具调用预算 $B$ 和并行代理数量研究计算-准确度权衡；蒸馏实验在 AMAZON、MAG、PRIME 数据集上测试 `Qwen3-8B` 学生模型的提升与保真度。
- 主要结论（把 claim 与证据对应）：
  1. 自适应平衡广度与深度能显著提升检索质量：
     - ARK 在 STaRK 上实现平均 $\text{Hit}@1 = 59.1\%$ 与平均 $\text{MRR} = 67.4$（文中为 average MRR，表述为 67.4）。相较于若干检索式与训练-free 代理方法，平均 $\text{Hit}@1$ 提升最高达 $+31.4$ 个百分点，平均 $\text{MRR}$ 提升最高达 $+28.0$ 个百分点——证明了交替工具使用能在不同查询类型（多实体覆盖与多跳链）下同时获益。
  2. 运行时预算-性能可控且可伸缩：
     - 论文通过调节工具调用预算与并行代理数展示了一个清晰的预算—性能曲线：更多工具调用或更多并行代理通常提升检索质量，但收益存在递减；该分析支持在有限资源下选择合适的预算以达到所需性能。
  3. 无标签蒸馏可把策略转移到紧凑模型：
     - 把教师模型的工具调用轨迹蒸馏到 `Qwen3-8B` 后，在三个数据集上学生模型的 $\text{Hit}@1$ 比基础 8B 模型分别提高了 $+7.0$（AMAZON）、$+26.6$（MAG）和 $+13.5$（PRIME） 个百分点，同时在一些设置下学生保留了教师高达 $98.5\%$ 的 $\text{Hit}@1$，显示了蒸馏在降低推理成本时能较好保留检索策略的有效性。

## 5. 局限与边界
- 不解决的问题 / 已知局限：
  - ARK 仍依赖所提供的节点描述文本的质量：若节点描述稀疏或噪声大，`Global Search` 的覆盖能力会受限。
  - 虽然训练-free，但系统对大型 LLM（教师）推断阶段的代价敏感——需要通过蒸馏来降低成本，但蒸馏过程本身需要足够的交互轨迹数据与计算资源。
  - 对于需要复杂符号化推理或精确数值计算的查询，单靠词表式全局搜索与一跳扩展可能不足，仍需更强的结构化推理模块或任务特定策略。
  - 实验主要在 STaRK 和若干数据集上验证——跨更多异构图谱、不同语言或超大规模工业图的泛化需要进一步评估。
- 作者承认的限制：
  - 方法并非万能替代训练式检索器在某些领域的最优性能；其优势在于“通用性 + 解释性 + 无需任务级监督”的场景。蒸馏能缓解推理成本但有性能上限（取决于学生模型容量）。

---

## 科学发现范式

- 主要范式：P09 Inference-Time Control & Guided Sampling
- 次要范式：P04 Modular Pipeline Composition, P01 Gap-Driven Reframing
- 分类理由：该论文提出了一个训练-免费、在推理阶段通过调用工具来动态平衡广度与深度检索的框架（代码库/系统名为"ARK"），核心思想是用推理时的控制/采样机制而非权重更新来改变检索行为，直接对应模式"P09"。其次，论文通过一组可组合的两类工具（"global lexical search"与"neighborhood exploration"）构建检索流水线，体现了模块化管道设计，匹配"P04"。论文起点是识别现有相似度检索与遍历法在覆盖性与多跳能力上的缺口，并将问题重构为交互式工具使用以同时兼顾两者，符合"P01"；实验在"STaRK"上验证并将策略无标签蒸馏到"Qwen3-8B"，进一步支持上述归类。

## 先前工作分析

The literature grounding this work contains complementary technical threads. The "STaRK" benchmark establishes the concrete problem setting—heterogeneous, text-rich KGs and an entity-level Hit@1/MRR evaluation—that motivates methods which must balance global coverage and multi-hop relational reasoning. From the LLM agent side, "ReAct" formalized interleaving model reasoning with external tool actions, giving a template for exposing a small, prompt-specified toolset to control retrieval behavior. On the graph-traversal front, methods such as "Tree-of-Traversals" and "Think-on-Graph" concretely demonstrate multi-hop exploration policies but also reveal critical failure modes: dependence on seed selection and fixed hop strategies that cause anchoring and missed evidence. Complementing traversal work, hybrid retrievers like "HybGRAG" show how combining semantic retrieval and local graph signals improves coverage yet typically remain static scoring pipelines that cannot dynamically switch search modes. Finally, practical compression techniques from "Distilling Interactive Policies via Label-free Trajectory Imitation" provide an operational recipe for taking costly teacher interactions and producing a compact, label-free student model. Together these threads expose a clear opportunity: combine persistent global discovery with composable one-hop expansion under a promptable tool interface and then compress the resulting adaptive policy. The current paper naturally follows by implementing a minimal two-tool LLM agent that alternates breadth and depth without seed dependence, evaluates on "STaRK", and uses label-free trajectory distillation to yield an efficient distilled retriever.
