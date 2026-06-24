---
slug: GraphWalker
title: 'GraphWalker: Agentic Knowledge Graph Question Answering via Synthetic Trajectory
  Curriculum'
authors:
- Shuwen Xu
- Yao Xu
- Jiaxiang Liu
- Chenhao Yuan
- Wenshuo Peng
venue: ''
arxiv_id: ''
tags: []
contribution_type: 方法改进型
reviewed: false
added_date: '2026-06-24'
---

> 核心主张：通过自动合成的多样化轨迹（GraphSynth）构建广泛的探索先验，并在此基础上用精炼的专家轨迹（GraphRoll）进行阶段化微调，然后接一个轻量级的 RL 优化，能显著提升 agentic KGQA 在大规模、噪声 KG 上的泛化与最终性能。

## 1. 问题背景

### 1.1 现有方法的局限
- Prompting / 直接交互方法（如 ToG、GoG）：依赖提示设计或闭源大模型的即时推理，缺乏在交互环境中“自主导航”的训练，因而难以在实际 KG 的多样化结构上形成稳健策略；实战中会频繁卡在搜索空间或循环错误上。
- SFT（监督微调）方法：通常以有限且人工/合成的预定义轨迹训练；这些轨迹往往结构单一、覆盖不足，造成模型缺少广域探索能力，遇到未见推理结构时无法有效扩展。
- RL（策略优化）方法：常在事先抽取的子图或简化环境上训练策略（子图偏差）；缺乏一个结构多样的 SFT 基础会导致探索被严重限制，策略难以在全局、稀疏奖赏的真实 KG 上学习起效。
- 共同后果：在长链、多跳、结构多样的推理任务（尤其出域路径）上，模型表现不稳，难以取得可迁移的导航与纠错能力。

### 1.2 本文瞄准的缺口
- 核心缺口是“缺乏广泛的探索先验（exploration prior）”：即没有一套能覆盖 KG 多样结构、供 agent 在真实推理时进行有效探索与自适应的训练轨迹集合。
- 进一步，缺少能训练 agent 反思与错误恢复（reflection & recovery）的高质量专家交互样本，使得后续的策略优化（RL）受限于起点（policy initialization）和收敛上界。

## 2. 贡献
类型：方法改进型

1. 系统识别并量化“探索先验缺失”是 agentic KGQA 泛化瓶颈，提出以合成轨迹建立广域探索 prior 的方案。解决的问题：突破现有 SFT 与 RL 在搜索空间起点上的局限；做法：用受约束随机游走生成大量结构多样的轨迹（GraphSynth-15k）作为 Stage-1 SFT 语料。
2. 提出阶段化微调（Stage-Wise SFT） + 轻量 RL 的训练流程，分工明确：Stage 1 建立探索能力，Stage 2 用少量高质量专家轨迹（GraphRoll-6k）训练反思与纠错，再用稀疏 EM 奖励的 GRPO 进行策略微调。解决的问题：提升最终 RL 的上界与样本效率。
3. 构建并公开两类语料：GraphSynth（15k 条、受约束随机游走合成）和 GraphRoll（6k 条、结果导向拒绝采样得到的专家轨迹），并通过消融与零样本测试证明合成轨迹能扩大可搜寻的路径分布，从而增强出域推理表现（在 CWQ、WebQSP、GrailQA 与作者构建的 GraphWalkerBench 上）。

## 3. 方法

### 3.1 核心思路（直觉）
- 直觉上，agent 在复杂 KG 中要成功多跳推理，需要先具备“去哪儿搜”的先验——即熟悉不同结构链条、关系模式和常见导航策略。直接用少量“专家”轨迹或在小子图上做 RL 无法提供这种覆盖面。
- 因此先用受约束的随机游走（Constrained Random Walk, CRW）大规模合成多样轨迹，让模型在 SFT 阶段形成广泛的探索行为习惯（不追求每条轨迹都完美）；随后用精炼的专家轨迹教会模型如何反思、回溯和纠错；最后以稀疏但精确的 EM 奖励做轻量策略优化，利用先前建立的探索先验使 RL 更高效且能突破以前的性能上限。

### 3.2 方法细节
总体流程：
1. 数据构建
   - GraphSynth-15k：在全图上对问题模板/目标实体执行 Constrained Random Walk（约束包括关系类型过滤、最大步数、语义相关性阈值等），收集多样但不必全都成功到达真实答案的交互轨迹，形成广域探索语料库。
   - GraphRoll-6k：基于对模型在 GraphSynth 阶段表现的输出进行结果导向的拒绝采样（outcome-based rejection sampling），挑选并/或合成高质量专家轨迹（含反思步骤、回溯决策），以训练错误恢复与反思能力。
2. 两阶段 SFT（Stage-Wise SFT）
   - Stage 1：在 GraphSynth 上对模型进行监督微调（SFT），目标是学会在多样结构上进行稳健的逐步查询/导航，建立探索 prior。
   - Stage 2：在 GraphRoll 上进一步 SFT，使模型学会检测错误、执行回溯和纠错策略（reflection/recovery）。
3. 轻量级 RL（GRPO）
   - 在 Stage-Wise SFT 后，进行基于稀疏准确匹配（Exact-Match, EM）奖励的策略优化，使用 GRPO（paper 中提到的算法名）对策略微调以提高最终 EM 性能。
   - 奖励定义（简化版）：
     R(τ) = 1 if answer(τ) matches gold else 0
   - RL 目标：最大化期望奖励
     J(θ) = E_{τ∼π_θ}[R(τ)]
     可用策略梯度估计 ∇_θ J(θ) ≈ E[∇_θ log π_θ(τ) R(τ)]。
- 关键设计要点
   - 合成轨迹不是为直接训练正确答案而生，而是为扩展搜索行为分布，降低 RL 在全图探索时的稀疏性。
   - GraphRoll 的 outcome-based 策略确保 Stage 2 聚焦于高质量回溯/反思范例，而非重复合成噪声。
   - 稀疏 EM 奖励保持训练目标与最终评测一致，避免引入代理奖励偏差。

## 4. 实验与结果
评测设置：
- 基准数据集：CWQ (ComplexWebQuestions), WebQSP；另外在 GrailQA 做零样本/出域评估，并用作者构建的 GraphWalkerBench 验证对未见推理路径的鲁棒性。
- 比较对象：Prompting-based 方法（ToG、GoG 等）、SFT-only 方法、先前的 RL 方法（例如 KG-R1）及少量强基线微调模型。
- 训练流程对比与消融：
  - 全流程（GraphSynth → GraphRoll → RL）
  - 无 GraphSynth（直接 GraphRoll → RL）
  - 无 GraphRoll（GraphSynth → RL）
  - 无 RL（仅两阶段 SFT）
主要结论（实验与对应声明）：
- RQ1（性能领先）：GraphWalker 在 CWQ 与 WebQSP 上取得 SOTA 性能（相较于同类 agentic KGQA 方法显著提升），表明阶段化 SFT + RL 的组合能提升最终 EM 性能；这支持论文关于“两个 SFT 阶段能解锁更高 RL 上界”的主张。
- RQ2（GraphSynth 的作用）：将 GraphSynth 纳入 Stage 1 明显扩大了模型在出域推理（GrailQA 与 GraphWalkerBench）上的成功率；消融显示缺少 GraphSynth 时，RL 在全图上陷入探索瓶颈，最终性能下降，说明合成轨迹确实扩展了搜索空间并提高了策略的泛化。
- RQ3（阶段贡献）：消融 Stage 2（GraphRoll）会降低模型的错误恢复与多步回溯成功率；Stage 1 缺失则使得 RL 难以提升或收敛到较低水平，实验对应作者提出的“Stage 1 提供探索 scaffold，Stage 2 提高反思能力”的设计动机。
- RQ4（数据构建）：关于数据构建管线（CRW 的约束、结果导向筛选），作者通过对子组件的消融验证了每一项（如关系过滤、最大步数、拒绝采样阈值）对最终泛化的贡献。
- 额外观察：在相同轻量 RL 预算下，基于 GraphWalker 的 agent 在稀疏 EM 奖励下相比未采用阶段化 SFT 的 baselines 达到更快的提升且最终更高。

（注：原文提供的是相对结论与 ablation 方向，具体数值在原论文完整表格中呈现；本文摘要避免编造具体数字）

## 5. 局限与边界
- 合成轨迹质量依赖于 CRW 的约束设计：不恰当的约束或采样策略可能引入偏差，使探索先验失效；作者使用受约束随机游走并有拒绝采样来缓解，但仍依赖超参与启发式规则。
- GraphSynth 本质上是“合成”的，存在与真实人为专家轨迹分布的差距；Stage 2 的 GraphRoll 只能部分弥补此分布差异。
- RL 部分使用稀疏且二值的 EM 奖励，未尝试更细粒度或回报形状的奖励，这在某些需要软评分或部分正确的场景下可能受限。
- 规模与计算：在超大规模 KG 或极其稀疏的实体分布下，CRW 的覆盖与后续训练成本仍是挑战；作者在论文中未声称解决 KG 规模极限或自动调整约束的通用方法。
- 不解决的问题：GraphWalker 不解决 KG 的构建/补全问题、也不直接降低对问题模板/问题理解的依赖；其改进聚焦于 agent 在给定 KG 上的交互训练范式。

---
