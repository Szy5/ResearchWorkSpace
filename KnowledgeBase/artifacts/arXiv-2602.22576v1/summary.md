#  Search-P1: Path-Centric Reward Shaping for Stable and Efficient Agentic RAG Training

## 1. 研究动机与贡献

问题背景（为什么要做）
- **Retrieval-Augmented Generation (RAG)** 通过检索外部知识缓解 LLM 的“静态知识/幻觉”问题，但传统的单轮检索在需要多步、跨文档综合推理的任务上表现受限。
- **Agentic RAG** 让模型在推理过程中主动决定是否、何时以及检索什么，能支持多轮检索并逐步构建答案；但是用强化学习训练这类检索-推理策略时存在关键挑战：
  - 稀疏奖励（sparse rewards）：仅用最终答案的正确/错误作为回报，忽略了中间检索与推理过程的质量；
  - 低样本效率：部分正确或部分有用的轨迹被判为“失败”并丢弃，训练信号浪费；
  - 收敛慢：大多数样本共享相似的二元回报，无法提供丰富梯度信息。

论文核心贡献
- 提出 **Path-Centric Reward Shaping**：将奖励从“只看最终结果”扩展为“评价完整的推理-检索路径（path）”，从而获得更密集、更有信息的训练信号。
- 两个关键组成：
  1. **Dual-Track Path Scoring**：从两个角度对路径打分——**自洽性（self-consistency）**和**参考对齐（reference-alignment）**，并使用顺序无关的步骤覆盖（order-agnostic step coverage）来容忍路径多样性。
  2. **Soft Outcome Scoring**：对不完全正确的轨迹给予部分分数（partial credit），把“失败样本”变成有用学习信号，提升样本效率与收敛速度。
- 实验显示在多个公共 QA 基准和企业内部广告问答集（**AD-QA**）上，相较 `Search-R1` 与若干强基线平均提升约 $7.7$ 个百分点准确率。

---

## 2. 方法介绍

总体思路（直观）
- 不把训练目标仅限于最终答案的正确与否，而是把“推理-检索的整条路径”作为监督对象：好的路径应该在步骤覆盖、事实一致性、以及与高质量参考规划器（reference planner）输出的一致性上都表现良好。
- 通过将路径级别的分数反馈给策略学习（例如强化学习/策略微调），优化模型在检索时的决策（什么时候检索、检索什么、何时终止并回答）。

关键术语（首次加粗）
- **路径（path）**：记作 $p$，表示模型执行的一次多轮交互序列，包含每轮的检索动作与所得到的证据片段及中间推理结果。
- **路径得分（path score）**：由两条轨迹评估通路构成：$R_{\text{self}}$（自洽）与 $R_{\text{ref}}$（参考对齐），此外加上软化的最终答案分数 $R_{\text{soft}}$。

形式化（简明公式化）
- 将路径表示为一组“步骤”而非严格序列以支持多样性：若 $\text{steps}(p)=\{s_1,\dots,s_n\}$，参考步骤集合为 $S_{\text{ref}}$，则采用“顺序无关的覆盖度”：
  $$
  C_{\text{cov}}(p, S_{\text{ref}}) = \frac{|\text{steps}(p) \cap S_{\text{ref}}|}{|S_{\text{ref}}|}.
  $$
- 自洽性分数衡量同一问题下不同模型/样本路径之间的一致性（例如用自举采样的多数投票/相似度统计）：
  $$
  R_{\text{self}}(p) = \text{consistency\_score}\big(p, \{p'\}\big),
  $$
  其中相似度可通过语义相似度函数 $\text{sim}(\cdot,\cdot)$ 或基于答案同质性的投票实现。
- 参考对齐分数比较路径的步骤集合与离线生成的高质量参考规划器输出（reference planner）：
  $$
  R_{\text{ref}}(p) = C_{\text{cov}}\big(p, S_{\text{ref}}\big)\quad\text{（可用 soft-match 取代精确匹配）}.
  $$
- 最终的路径级奖励可线性组合（论文采用类似的混合策略）：
  $$
  R_{\text{path}}(p) = \alpha\, R_{\text{self}}(p) + \beta\, R_{\text{ref}}(p) + \gamma\, R_{\text{soft}}(p),
  $$
  其中 $R_{\text{soft}}$ 是对最终答案的软判分，用来给“近对/部分正确”的答案以部分回报（例如基于答案 F1、语义相似度或分段正确率）。

体系结构与训练流程（概览）
1. 用基础 LLM 执行 agentic RAG 任务，生成许多轨迹 $p$（包含检索动作与中间推理）。
2. 离线生成或预先收集参考路径集合 $S_{\text{ref}}$（reference planner），作为参考对齐的标杆。
3. 对每条轨迹计算 $R_{\text{self}}$ 与 $R_{\text{ref}}$（顺序无关匹配 + soft 相似度），以及 $R_{\text{soft}}$。
4. 将组合的 $R_{\text{path}}$ 作为强化学习/策略微调的回报，更新检索-推理策略（可接到现有 `Search-R1` 式的 RL 框架上）。

图示（来自论文）
- 下图为方法概览：两条路径评分通路（自洽 + 参考对齐）和软化的最终结果评分共同构成路径级奖励。
![Overview of framework. Our approach introduces path-centric reward shaping for agentic RAG training, comprising: (1) Dual-Track Path Scoring that evaluates trajectories from both self-consistency and reference-alignment perspectives, and (2) Soft Outcome Scoring that extracts training signals even from incorrect answers.](assets/figures/main.jpg)

为何解决了原问题
- 稀疏奖励 → 通过 $R_{\text{self}}$ 与 $R_{\text{ref}}$ 在中间步骤上给出密集信号，避免只有“最终对/错”的二元反馈。
- 低样本效率 → $R_{\text{soft}}$ 把部分正确的轨迹赋予部分回报，使其仍能贡献梯度。
- 收敛慢 → 更丰富、更细粒度的回报分布提供更稳定的训练信号，加速学习。

实现要点（工程/实践提醒）
- 参考路径 $S_{\text{ref}}$ 可以用强化的检索器或启发式规划器离线生成；重要的是保证多样性与质量，以免引入偏差。
- 顺序无关的覆盖匹配需要设计语义级别的 step-matching（例如基于向量相似度），而不是仅靠字符串匹配。
- 超参数 $\alpha,\beta,\gamma$ 控制三个分量的重要性，论文通过消融验证其必要性。

代码/方法名首次出现用反引号：`Search-R1`、`HiPRAG`。

---

## 3. 实验结果

实验设置（简要）
- 基线：`Search-R1`（RL outcome-only）、`HiPRAG`（近似的先进方法），以及传统 RAG、CoT 等。
- 模型规模：在 Qwen2.5 的 $7$B 与 $3$B 模型上评测。
- 数据集：7 个公共 QA 基准（含多跳与单跳），以及企业内部 **AD-QA**（广告问答）。

主要结果（要点摘要）
- 平均性能（Qwen2.5-7B）：论文方法（记作 **Search-P1/本方法**）在平均准确率上达 $47.3\%$，而 `Search-R1` 为 $39.6\%$，提升接近 $7.7$ 个百分点（与摘要一致）。
- 局部亮点：在多个公共与内部任务上均领先，尤其在内部广告问答 **AD-QA** 上本方法达 $86.2\%$（显著高于基线）。
- 不同模型规模上均显示一致提升（$7$B 与 $3$B 均优于基线）。

表格节选（文字版高亮）
- Qwen2.5-7B：`Search-R1` 平均 $39.6$ → 本方法 $47.3$（最佳）；`HiPRAG` $42.9$。
- Qwen2.5-3B：`Search-R1` 平均 $33.6$ → 本方法 $41.5$。
- 多个数据集上本方法在 NQ、TriviaQA、PopQA、Musique 等均取得较大提升。

消融（验证设计的必要性）
- 去掉参考对齐（w/o Reference-Alignment）：平均降到 $42.0$。
- 去掉自洽性（w/o Self-Consistency）：平均降到 $44.2$。
- 两者都保留（Full）：$47.3$。这表明**双轨评分**中的两条通路都对性能有实质贡献。

直观结论
- 两条路径评分（自洽 + 参考对齐）与软化最终得分的组合能显著提高对多步检索-推理流程的学习。
- 部分失败样本不再是“纯噪声”，而是可回收的学习资源，从而提升样本利用率与训练稳定性。

---

## 4. 简要总结

核心结论（一句话）
- 本文提出的 **Path-Centric Reward Shaping** 把奖励放在“完整的检索-推理路径”上，通过 **Dual-Track Path Scoring**（自洽 + 参考对齐）和 **Soft Outcome Scoring** 把稀疏、二元的回报信号变为密集且有区分度的路径级监督，从而提升 agentic RAG 的样本效率、稳定性与最终性能。

优点与适用场景
- 适合需要多轮检索与跨文档、多步骤推理的应用（例如广告策略建议、复杂问答、知识密集型客服）。
- 能平滑地与现有 RL 或策略微调管线结合，且对模型规模的适应性较好（在 $3$B 与 $7$B 均见效）。

局限与未来方向
- 依赖高质量的参考路径生成器；若参考路径偏差较大，可能引入错误偏好。
- 步骤匹配需要鲁棒的语义相似度量，工程上需权衡精度与效率。
- 可进一步探索自适应地权衡三类分数（自动调整 $\alpha,\beta,\gamma$）以及在更大规模模型/更复杂检索场景的泛化。

如果你想把这篇方法复现到已有的 agentic RAG 管线，我可以：
- 给出具体的伪代码训练循环（含路径采样、参考路径生成、相似度匹配与回报计算）；
- 建议一套合理的超参数初始化（$\alpha,\beta,\gamma$）与评价指标；
- 或者将论文中的表格结果转换为更细粒度的对比图表，帮助你决定在何处切换到路径级奖励。需要哪项，告诉我即可。
