# Autonomous Knowledge Graph Exploration \\ with Adaptive Breadth-Depth Retrieval

Authors: Joaqu\'in~Polonuer1; ~---; Lucas~Vittor1; ~---; I\~naki~Arango1; ~---; Ayush~Noori1; ~---

## Abstract

Retrieving evidence for language model queries from knowledge graphs (KGs) requires balancing broad search across the graph with multi-hop traversal to follow relational links. Similarity-based retrievers provide coverage but remain shallow, whereas traversal-based methods rely on selecting seed nodes to start exploration, which can fail when queries span multiple entities and relations. We introduce : , a tool-using KG retriever that gives a language model control over this breadth-depth tradeoff using a two-operation toolset: global lexical search over node descriptors and one-hop neighborhood exploration that composes into multi-hop traversal. alternates between breadth-oriented discovery and depth-oriented expansion without depending on a fragile seed selection, a pre-set hop depth, or requiring retrieval training. adapts tool use to queries, using global search for language-heavy queries and neighborhood exploration for relation-heavy queries. On STaRK, reaches 59.1\% average Hit@1 and 67.4 average MRR, improving average Hit@1 by up to 31.4\% and average MRR by up to 28.0\% over retrieval-based and agent-based training-free methods. Finally, we distill 's tool-use trajectories from a large teacher into an 8B model via label-free imitation, improving Hit@1 by +7.0, +26.6, and +13.5 absolute points over the base 8B model on AMAZON, MAG, and PRIME datasets, respectively, while retaining up to 98.5\% of the teacher's Hit@1 rate.

## Introduction

Large language models rely on knowledge retrieval to ground and align their outputs in external evidence [ren2025investigating, wang2025survey, xia2025ground, zhang2024knowledge], from retrieval-augmented generation (RAG) to systems and memory modules that operate over *semi-structured* knowledge bases (SKB) that mix text with relational information [lewis_retrieval-augmented_2020, guu_realm_2020, karpukhin_dense_2020, izacard_leveraging_2021, mavromatis_gnn-rag_2025, chen_gril_2025, li2025retrollm]. Knowledge graphs (KGs) are a natural data representation for this setting because they organize evidence around entities and typed edges, support reuse across queries, and enforce relational constraints that a flat text index cannot express. This has motivated graph-aware retrievers and graph-grounded generation methods, including graph-based RAG and SKB retrievers that combine text and relational data [edge_local_2025, zhu_knowledge_2025, xia_knowledge-aware_2025, yao2025expandr, jeong2025database].

Retrieving evidence from KGs is challenging because it requires coordinating two competing search modes [wu_stark_2024, lee_hybgrag_2025, zhu-etal-2025-mitigating, yan2026explore]. Many queries require *breadth*: they mention multiple entities or loosely connected concepts, so the retriever must cover the graph broadly to reach the right region. Other queries require *depth*: the supporting evidence only appears after following specific multi-hop relational paths. Similarity-based retrievers provide global coverage but often remain shallow and underuse relational structure, whereas traversal-based methods can be brittle because they must choose seed entities to start exploration; when seeds are incomplete or ambiguous, the search stays local and misses evidence elsewhere.

Existing work tackles these breadth-depth requirements in isolation rather than jointly [ko2025cooprags, ma2025think, wang2025corag]. *Structure-aware* retrievers extend text-based retrieval with relational structure, for example, by learning node embeddings that aggregate information from nearby neighbors or by generating candidates using a local graph neighborhood before ranking them [lee_hybgrag_2025, zhu_knowledge_2025, lei_mixture_2025]. These methods capture local structure, but they typically encode a fixed neighborhood around each node, so deeper multi-hop queries require expanding the encoded context or stacking additional message-passing and retrieval stages, which increases complexity and cost [wan2025digest, hu2025remindrag, verma2024plan]. By contrast, *traversal-based approaches* perform multi-hop exploration, but they depend on identifying a small set of seed entities from which exploration begins [@{markowitz_tree--traversals_2024}; @{sun_think--graph_2024}]. When seeds are incomplete or ambiguous, exploration stays local and misses relevant information elsewhere in the graph [liu2025ontology, ma2025think]. Many systems also rely on task- or graph-specific training to learn traversal or scoring policies, which limits transfer across domains and graph schemas [li_multi-field_2025, lei_mixture_2025, wu_avatar_2024, yu_can_2025]. As a result, existing methods struggle to combine global search with targeted relational reasoning for adaptive retrieval.

**Present work.** We introduce : , a tool-using KG retriever that gives a language model control over evidence discovery using a minimal set of tools for global lexical search and neighborhood exploration. does not require selecting seed entities to start exploration or establishing a maximum hop depth in advance; instead, the model alternates between broad global search and targeted multi-hop traversal based on the query and what it has retrieved so far. We evaluate on the heterogeneous graphs in the STaRK retrieval benchmark and show consistent gains across all settings. We further study compute-accuracy tradeoffs by varying the tool-call budget and the number of parallel agents, and we distill 's tool-use policy into an 8B model via label-free trajectory imitation, preserving most of the performance of teacher model at substantially lower inference cost [kang_distilling_2025].

Our contributions are threefold. (i) We introduce , a training-free retrieval framework that equips language models with a minimal but expressive tool interface for adaptive retrieval from KGs. (ii) We show that balances breadth-oriented retrieval with depth-oriented multi-hop traversal without task- or graph-specific training, achieving strong performance on STaRK. (iii) We distill 's tool-use policy without labeled supervision into a compact Qwen3-8B model [yang_qwen3_2025, kang_distilling_2025], preserving retrieval quality while reducing inference cost.

## Related Work

Retrieval-augmented generation grounds LLM outputs in external evidence [lewis_retrieval-augmented_2020, guu_realm_2020]. Recent work injects structure by building graphs to aggregate evidence. GraphRAG performs local-to-global retrieval over entity-centric graphs [edge_local_2025], and related methods retrieve textual subgraphs for multi-hop queries [zhu_knowledge_2025, hu_grag_2025, he_g-retriever_2024, li_simple_2025]. These approaches improve how evidence is organized but the retrieval process itself remains static.

Complementary to document-centric graph indices, semi-structured knowledge base retrievers directly combine text and explicit relations. KAR grounds query expansion in KG structure [xia_knowledge-aware_2025], GraphSearch mixes graph and text channels with iterative refinement [yang_graphsearch_2025] and HybGRAG routes queries across a bank of retrieval modules with self-reflection [lee_hybgrag_2025]; CoRAG highlights cooperative hybrid retrieval that preserves global semantic access beyond local neighborhoods [zheng_corag_2025]. In parallel, parametric retrievers such as MoR and mFAR learn to fuse lexical, semantic, and structural signals for ranking [lei_mixture_2025, li_multi-field_2025]. Across these variants, retrieval is framed as scoring candidates from a static index. differs in that retrieval is formulated as an interactive process: the model dynamically switches between global search and neighborhood expansion, guided by the query requirements and without relying on task-specific supervision.

A separate line of work treats the KG as an environment for iterative interaction. Earlier agents follow relation paths using reinforcement learning or learned policies [das_go_2018, xiong_deeppath_2017, sun_pullnet_2019, asai_learning_2020]. In the LLM era, tool-use frameworks such as ReAct [yao_react_2023] and prompt-optimization methods such as AvaTaR [wu_avatar_2024] enable interactive evidence gathering. Within KG retrieval, traversal-based approaches expand from seed entities using prompted heuristics or learned policies, including Tree-of-Traversals, Think-on-Graph, and GraphFlow [@{markowitz_tree--traversals_2024}; @{sun_think--graph_2024}; @yu_can_2025; @ma2025think]; related KG-grounded reasoning methods also emphasize multi-step planning or navigation on the KG [@luo_reasoning_2024; @{sun_search--graph_2025}]. Traversal-based agents are effective when the correct starting entities are known, but they are prone to anchoring errors and can over-commit to local neighborhoods once exploration begins. In , global search remains available throughout the trajectory, allowing the agent to retain a complete view of the KG at each step. This design enables coordination between global discovery and multi-hop expansion within a single retrieval. Recent work also explores using reinforcement learning to enable LLMs to explore reasoning paths over KGs [yan2026explore, wang2026kg].

Existing work varies in whether it treats retrieval as static ranking over an index or as sequential decision-making on the graph, and in whether it requires graph-specific supervision to learn a ranking function or a traversal policy. adapts its search strategy online through a minimal, graph-native tool interface. It is training-free; when needed, its tool-use policy can be distilled into compact models from interaction trajectories without ground-truth relevance labels, improving efficiency while preserving retrieval quality.

## Untitled

We study retrieval over a knowledge graph , where $V$ and $E$ denote entities and edges, $\phi_V$ and $\phi_E$ assign a type to each node and relation, and $d_V(v)$ denotes the text attributes associated with node $v$, such as titles, descriptions, or other metadata. Given a natural-language query $Q$, retrieval is formulated as an interactive process in which an agent $\mathcal{A}=\langle \mathrm{LLM},\mathcal{T}\rangle$ queries the graph through a tool interface $\mathcal{T}$ [yao_react_2023, schick_toolformer_2023] and produces a trajectory $\tau = \bigl((s_1,A_1,o_1),\dots,(s_T,A_T,o_T)\bigr)$. At step $t$, $s_t$ contains $Q$ and the interaction history, $A_t$ is a sequence of tool invocations, and $o_t$ is the observation returned after executing $A_t$.

Throughout the trajectory, the agent maintains an ordered list of retrieved nodes $\mathcal{R}$. At each step, it can [select]{.smallcaps} nodes returned by tools and append them to $\mathcal{R}$, or terminate by issuing a dedicated [finish]{.smallcaps} action. Execution ends either when the agent calls [finish]{.smallcaps} or when the maximum trajectory length $T_{\max}$ is reached. The final retrieval output is the ranked list $\mathcal{R}=(v_1,v_2,\dots)$, where earlier selections receive higher rank.

To rank candidate nodes returned by tools, we use a relevance function $\rel(q,d_V(v))\in\mathbb{R}_{\ge 0}$ that scores node $v$ for a textual subquery $q$ provided by the agent as a tool parameter. We implement $\rel$ with BM25 [robertson_probabilistic_2009] over an inverted index of node textual attributes [manning_introduction_2008], yielding fast and stable scoring for the many short, evolving subqueries issued during exploration.

### Tools

We implement the interaction described above through a small set of retrieval tools. Each tool returns a candidate set of nodes, which the agent may append to $\mathcal{R}$ or use to guide subsequent steps.\ retrieves the $k$ highest-scoring nodes in the graph under $\rel$ for an agent-issued subquery $q$, as shown in [\[fig:main-figure\]](#fig:main-figure){reference-type="ref+Label" reference="fig:main-figure"}a:

$$
\operatorname{Search}_G(q,k)
 \;:=\;
 \operatorname*{Top\text{-}k}_{v \in V}\; \rel(q, d_V(v))
$$

This tool provides broad entry points into the graph and is primarily used (i) to locate entities related to the user query $Q$, which will then be used for further exploration, and (ii) to handle cases where direct text matching suffices without requiring multi-hop reasoning.\ returns adjacent nodes of a node $v$ filtered by optional node and edge type constraints $F := (F_V, F_E)$ selected by the agent as tool parameters, and optionally ranked using an agent-generated subquery $q$ ([\[fig:main-figure\]](#fig:main-figure){reference-type="ref+Label" reference="fig:main-figure"}b).

The filtered one-hop neighborhood $N_F$ of a node $v$ is defined as:

$$
N_F(v)
 :=
 \left\{
 u \in N(v)
 \;\left|\;
 \begin{aligned}
 & \phi_V(u) \in F_V, \\
 & \phi_E(\{u, v\}) \in F_E
 \end{aligned}
 \right.
 \right\}
$$

where $N(v)$ denotes the open neighborhood of $v$ and $\{u, v\}$ denotes the edge connecting $v$ and $u$, regardless of direction. Edge directionality and relation types are exposed in the tool output. To control the size of the retrieved neighborhood, we introduce a fixed retrieval budget $k \in \mathbb{N}$:

$$
\operatorname{Neighbors}(v, q, F)
 := \operatorname*{Top\text{-}k}_{u \in N_F(v)} \; \rel(q, d_V(u))
$$

Each call to $\operatorname{Neighbors}$ retrieves a single-hop neighborhood. The agent performs multi-hop retrieval by calling this operator multiple times in sequence, optionally interleaved with global re-anchoring ([\[fig:main-figure\]](#fig:main-figure){reference-type="ref+Label" reference="fig:main-figure"}c). The number of hops is not fixed in advance; the agent decides when to stop expanding based on what it has retrieved so far.

### Parallel Exploration

[]{#sec:parallel_exploration label="sec:parallel_exploration"} We increase robustness by running $n$ independent instances of the same agent in parallel and aggregating their retrieved lists, akin to self-consistency and voting-based ensembling in LLM reasoning [wang_self-consistency_2023, kaesberg_voting_2025]. Each agent produces an ordered list of retrieved nodes $\mathcal{R}^{(i)}=(v^{(i)}_1,v^{(i)}_2,\dots)$ from an independent trajectory. We then combine these lists using a simple rank-fusion rule inspired by classical rank aggregation and data fusion methods [fagin_efficient_2003, cormack_reciprocal_2009].

Concretely, we concatenate the per-agent lists in agent order to form:

$$
L \;:=\; \mathcal{R}^{(1)} \,\Vert\, \mathcal{R}^{(2)} \,\Vert\, \cdots \,\Vert\, \mathcal{R}^{(n)},
$$

and let $\mathcal{V}_L$ be the set of unique nodes in $L$. The final ranking $\mathcal{R}$ orders nodes by decreasing frequency in $L$ (vote count), breaking ties by the earliest position at which a node appears in any trajectory, favoring nodes discovered earlier during exploration.

### Agent Distillation

[]{#subsec:distill label="subsec:distill"} While operates on off-the-shelf models, its behavior can be distilled into a smaller language model to reduce inference cost and latency [hinton_distilling_2015]. We adopt a standard teacher--student paradigm in which a student model imitates the tool-usage trajectories of a stronger teacher LLM via supervised fine-tuning [schick_toolformer_2023].

For each training query $Q$ on a given graph $G$, we run the teacher agent to collect trajectories $\tau$ as defined in [\[method\]](#method){reference-type="ref+Label" reference="method"}. Each trajectory contains the full interaction record: the agent's tool calls and parameters interleaved with the resulting tool observations.

The student is trained with next-token prediction on the collected trajectories [ouyang_training_2022]. We compute loss only on assistant-authored tokens; user messages and tool outputs are masked [huerta-enochian_instruction_2024, shi_instruction_2024]. This trains the student to reproduce the teacher's decisions, which tools to invoke and how to parameterize them, while tool execution remains external to the model.

Importantly, distillation does not require ground-truth evidence nodes for queries. Supervision is derived solely from teacher trajectories, making the approach applicable in realistic settings where relevance labels are unavailable: one can run a strong teacher to generate trajectories on a target graph and then fine-tune a smaller model directly from these interactions [schick_toolformer_2023, kang_distilling_2025].

## Experimental Setup

[]{#sec:experiments label="sec:experiments"} We measure retrieval performance on STaRK, a benchmark for entity-level retrieval over heterogeneous, text-rich KGs [wu_stark_2024].

### Benchmark

STaRK comprises three large, heterogeneous knowledge graphs. **AMAZON** is an e-commerce graph with roughly 1M entities and 9.4M relations, constructed from Amazon metadata, reviews [he_ups_2016], and question--answer pairs [mcauley_inferring_2015]. **MAG** is a scholarly graph with 1.9M entities and 39.8M relations derived from the Microsoft Academic Graph [wang_microsoft_2020]. **PRIME** is a biomedical graph built from PrimeKG [chandak_building_2023], containing 129K entities and 8.1M relations. Each node is associated with text-rich attributes, making STaRK a natural testbed for hybrid retrieval over structured and textual signals. Given a query, the retriever must return a ranked list of nodes that support the answer. We report agent configuration and hyperparameters in Appendix app:impl-details.

### Baselines and metrics

We compare with representative retrieval-based and agent-based baselines, focusing on methods that report results on all three graphs, as our goal is to evaluate performance consistently across different regimes and assess generality.

**BM25** [robertson_probabilistic_2009] is the same sparse, lexical retriever used for global search. We also include dense embedding retrievers that rank nodes by cosine similarity, using **ada-002** and **GritLM-7B**, an instruction-tuned 7B encoder [muennighoff_generative_2025]. **mFAR** [li_multi-field_2025] is a multi-field adaptive retriever that combines keyword matching with embedding similarity to learn query-dependent weights over different node fields. **KAR** [xia_knowledge-aware_2025] augments queries with knowledge-aware expansions and applies relation-type constraints during retrieval. **MoR** [lei_mixture_2025] is a trained retriever that combines multiple retrieval objectives.

**Think-on-Graph** [@{sun_think--graph_2024}] is a training-free LLM agent that iteratively expands paths in the graph using beam search. **GraphFlow** [yu_can_2025] learns a policy for generating multi-hop retrieval trajectories using GFlowNets [bengio_flow_2021]. **AvaTaR** [wu_avatar_2024] is a tool-using agent that optimizes prompting from positive and negative trajectories.

Results for KAR, mFAR, MoR, AvaTaR, and GraphFlow are reported as in their respective papers, which evaluate on the official STaRK splits and metrics. For Think-on-Graph, we report the numbers provided in the GraphFlow study, which includes a direct comparison to Think-on-Graph under the same STaRK setup [@yu_can_2025; @{sun_think--graph_2024}].

We follow the STaRK protocol and report Hit@1, Hit@5, Recall@20 (R@20), and Mean Reciprocal Rank (MRR), which capture top-rank precision, coverage of the ground-truth set, and overall ranking quality. Note that Hit@5 is reported in [\[tab:full-stark-results\]](#tab:full-stark-results){reference-type="ref+label" reference="tab:full-stark-results"} in the Appendix.

Our primary configuration uses GPT-4.1 as the backbone LLM throughout the paper. Appendix [\[tab:full-stark-results\]](#tab:full-stark-results){reference-type="ref+Label" reference="tab:full-stark-results"} additionally reports results with GPT-4o for comparability with prior KG retrievers such as KAR and Think-on-Graph, and with GPT-5.2 to verify that the retrieval interface transfers to a newer backbone on the same splits.

### Distillation Setup

For each graph, we collect teacher trajectories on the training split to distill into a smaller, lower-cost model ([\[subsec:distill\]](#subsec:distill){reference-type="ref+Label" reference="subsec:distill"}), offering a viable alternative when under tighter compute budgets. Using GPT-4.1 as the teacher, we run three times per training query with stochastic decoding (temperature $= 0.7$), producing three trajectories per query. We cap the distillation budget by subsampling up to 6,000 training queries per graph, yielding at most 18,000 trajectories per graph (full statistics in [\[tab:traj_counts\]](#tab:traj_counts){reference-type="ref+label" reference="tab:traj_counts"}) and summing to 94.4 million tokens. Each trajectory is limited to $T_{\max}{=}20$ steps and ends when the agent issues [finish]{.smallcaps} or reaches the step limit. We apply no trajectory filtering or rejection sampling, preserving a label-free setting. We then distill a Qwen3-8B [yang_qwen3_2025] student via supervised fine-tuning with LoRA adapters [hu_lora_2021], using next-token prediction over assistant-authored tokens only. We train for one epoch with a 16,384-token context length using AdamW [loshchilov_decoupled_2019] at learning rate $1\times 10^{-5}$, selecting checkpoints via early stopping on the official validation split. Training runs on a single NVIDIA H100 GPU and completes in approximately five hours.

### Benchmarking

[\[tab:stark-results\]](#tab:stark-results){reference-type="ref+Label" reference="tab:stark-results"} reports retrieval performance on STaRK, grouped by training regime. Across all methods assessed, achieves the best average performance.

Classical retrievers remain strong baselines on AMAZON, when queries are predominantly descriptive. By incorporating local structural cues, KAR improves over lexical methods, but its shallow neighborhood expansion is limited on multi-hop queries [xia_knowledge-aware_2025].

Think-on-Graph and GraphFlow highlight the benefits of multi-hop traversal, performing well on PRIME. Think-on-Graph is appealing due to its training-free setup, and GraphFlow shows that strong performance can be achieved with smaller backbones through reinforcement learning. However, both degrade on AMAZON's text-heavy, broad queries, as they lack global search primitives and can be sensitive to brittle anchoring and entity identification [@{sun_think--graph_2024}; @yu_can_2025].

performs consistently across regimes and is especially strong on MAG. This pattern aligns with its tool design. Global search offers a reliable anchor for text-heavy queries and supports strong top-rank accuracy on AMAZON. Typed, query-ranked one-hop expansion enables controlled multi-hop evidence gathering in relational settings, contributing to the best results on MAG and solid performance on PRIME, where it is surpassed only by the RL-trained GraphFlow.

While uses a large backbone, the distilled variant preserves most of these gains with a substantially smaller Qwen3-8B model via label-free trajectory imitation (Section sec:distillation-impact).

### Text vs. Relational Adaptive Retrieval

STaRK reports, for each graph, the average share of queries that are primarily textual versus primarily relational (multi-hop) (Fig. 5 in @wu_stark_2024). We use these proportions as a reference and compare them to 's tool-call allocation on our evaluation split. Concretely, we treat the fraction of global search calls as a proxy for text-centric evidence use and the fraction of neighborhood exploration calls as a proxy for relation-centric evidence. [\[fig:adaptive-tool-use\]](#fig:adaptive-tool-use){reference-type="ref+Label" reference="fig:adaptive-tool-use"} shows a proportional match: on AMAZON, where queries are mostly textual, relies almost entirely on global search (87.7%), whereas on MAG and PRIME, where relational requirements dominate, shifts toward neighborhood exploration to traverse multi-hop evidence (65.3% and 52.3%, respectively). Appendix app:trajectory-tool-usage complements this call-frequency view with trajectory-level statistics on re-anchoring after the first step and on tool mixing among successful runs.

### Impact of Toolset Design

We conduct various ablation studies to assess the impact of toolset design choices. [\[tab:toolset-ablation\]](#tab:toolset-ablation){reference-type="ref+Label" reference="tab:toolset-ablation"} demonstrates that neighborhood exploration is the main source of gains on relational, multi-hop queries. Removing this tool decreases performance on MAG and PRIME as the system is then limited to global lexical search without graph traversal. On AMAZON, performance drops more moderately and moves toward lexical baselines ([\[tab:stark-results\]](#tab:stark-results){reference-type="ref+label" reference="tab:stark-results"}).

We further separate two complementary controls in neighborhood exploration. Disabling query-based ranking causes smaller but consistent drops, suggesting that lexical matching within a local neighborhood helps surface relevant neighbors and prevents drift toward high-degree distractors. Disabling type-based filtering is more detrimental, especially in heterogeneous graphs such as PRIME ([\[tab:stark-statistics\]](#tab:stark-statistics){reference-type="ref+label" reference="tab:stark-statistics"}). In such environments, type constraints are important to direct the agent towards semantically relevant edges and nodes, preventing search from drifting into unrelated parts of the graph.

Note that we do not ablate global search because it is required: it maps query text to candidate nodes and provides the node identifiers needed to start neighborhood expansion. Without this initial anchor, the agent cannot reliably enter the right part of the graph, so the system fails outright.

### Compute-Performance Trade-offs

We next study how retrieval quality scales with the inference-time budget. [\[fig:n-agents\]](#fig:n-agents){reference-type="ref+Label" reference="fig:n-agents"} shows that performance improves monotonically as compute increases, moving from single-agent settings to parallel multi-agent configurations. We also report a single-agent vs. multi-agent comparison under the same total step budget in Appendix app:budget-control.

Additional compute helps most on queries that require multi-hop expansion, and yields smaller gains when global lexical search is already sufficient. Parallelization yields performance benefits with minimal overhead. Increasing the agent count, particularly the transition from one to two agents, results in substantial gains while only modestly increasing latency. Because agents run independently, end-to-end latency is determined by the bottleneck of the slowest agent rather than the cumulative runtime of all agents.

provides an interpretable budget-performance landscape. Practitioners can fix a latency or compute budget and choose an operating point in [\[fig:n-agents\]](#fig:n-agents){reference-type="ref+Label" reference="fig:n-agents"} that matches their needs, trading off depth and parallelism to balance quality and cost across graph regimes.

### Aggregation Strategy Comparison

Aggregation quality also matters once multiple trajectories have been collected. [\[tab:aggregation-comparison\]](#tab:aggregation-comparison){reference-type="ref+Label" reference="tab:aggregation-comparison"} compares our voting rule against two simpler ways of combining the outputs of three agents. Voting consistently outperforms both ordering-based merging and random merging, with the largest gains on MAG and PRIME. This supports the view that parallel exploration helps not only by increasing sampling diversity, but also by exposing a stable consensus signal over retrieved nodes.

### Relevance Function (Lexical vs.\ Dense)

The relevance function $\rel$ used to rank candidate nodes for agent-issued subqueries ([\[method\]](#method){reference-type="ref+Label" reference="method"}) can be implemented with either lexical (BM25) or dense retrieval. [\[tab:dense-ablation\]](#tab:dense-ablation){reference-type="ref+Label" reference="tab:dense-ablation"} compares the two options inside . BM25 is notably more precise on AMAZON and PRIME, while differences on MAG are marginal in both directions. This suggests that the advantage of dense retrieval in single-pass settings does not directly carry over to iterative retrieval: the agent can compensate for weaker lexical matching by issuing refined subqueries over successive steps and by discovering relevant nodes through neighborhood exploration rather than text similarity alone.

### Impact of Distillation

We also study how the distillation budget affects final performance. [\[fig:sft-impact\]](#fig:sft-impact){reference-type="ref+Label" reference="fig:sft-impact"} compares Qwen3-4B and Qwen3-8B students trained on increasing numbers of teacher trajectories across the three STaRK graphs; full results for all metrics are in [\[tab:full-stark-results\]](#tab:full-stark-results){reference-type="ref+Label" reference="tab:full-stark-results"}.

Distillation is data-efficient: using 10% of the trajectories recovers roughly half of the total improvement achieved with the full training set. This makes distillation practical when collecting trajectories is costly. In our setup, distilling the 600-query setting can be done in 30 minutes on a single H100 GPU.

Student size matters most on PRIME. Because base models perform poorly in this regime, distillation is more important, and the teacher-student gap is the largest. The stronger performance of the 8B student suggests that higher-capacity models better absorb the long-horizon, high-branching exploration patterns required for complex biomedical reasoning in PRIME.

### Neighborhood Exploration vs. Retrieval

We next examine how neighborhood exploration relates to retrieval success on MAG and PRIME. Here, successful trajectories refers to the runs (*i.e.*, tool call sequences) that retrieve the correct nodes and therefore score as correct on the retrieval metric for that query. [\[fig:neighbor-explore-distribution\]](#fig:neighbor-explore-distribution){reference-type="ref+Label" reference="fig:neighbor-explore-distribution"} shows two failure modes. First, many failed runs make no neighborhood calls at all, suggesting the agent does not recognize when relational evidence is needed and never moves beyond global anchoring into multi-hop expansion. Second, failed runs also show a long tail with many neighborhood calls, indicating the opposite problem: the agent keeps expanding without converging on relevant support, consistent with drift in high-branching parts of the graph.

In contrast, successful trajectories use neighborhood exploration sparingly, rarely exceeding ten calls, suggesting that strong retrieval relies on selective expansion rather than indiscriminate multi-hop traversal. These results underscore the need for retrieval methods like that balance the breadth-depth tradeoff: when succeeds, it adaptively switches from global anchoring to neighborhood expansion, and it stops expanding once it has found the needed support.

## Conclusion

[]{#conclusion label="conclusion"} We introduced , a training-free retrieval framework that exposes knowledge graphs through a minimal set of primitives for global search and local relational expansion. Across all three STaRK graphs, achieves strong and stable retrieval performance while exhibiting a clear and interpretable inference-time budget--performance trade-off. We further show that this adaptive retrieval behavior can be transferred to a compact backbone via label-free trajectory distillation with modest data and compute, preserving nearly all of the teacher's performance. Together, these results indicate that adaptive graph retrieval can be both practical and modular, and that exposing a small set of well-chosen retrieval operations is sufficient to unlock robust, general-purpose knowledge graph retrieval.

## Limitations

Despite strong retrieval performance, has limitations. First, agentic retrieval incurs higher latency than single-pass retrievers because it requires multiple LLM calls over an interaction trajectory. Larger budgets improve retrieval quality but also increase runtime. Second, our best-performing configuration relies on a large proprietary LLM, which can constrain scalability due to cost and availability. While is LLM-agnostic, retrieval quality can drop with smaller models; we partially mitigate this via trajectory distillation into Qwen3-8B [yang_qwen3_2025], though distilled agents still trail the teacher on challenging regimes. Third, assumes that node descriptors and relation information are sufficiently informative for BM25 global search and for ranking neighborhood expansions. Sparse or templated text can prevent the agent from locating relevant seed nodes or disambiguating them. Because the global search is lexical, mismatches in vocabulary (*e.g.*, paraphrases and domain-specific aliases) can cause under-retrieval. Fourth, our evaluation is centered on text-rich KG benchmarks, so performance gains may not transfer to graphs with limited text descriptions.

Although is a general retrieval approach, agentic graph exploration can create risks if used without safeguards. Retrieval errors can be treated as support for downstream decisions, and interaction traces may expose sensitive attributes if node text contains private information. Mitigation requires redaction for sensitive fields and bias audits prior to deployment.

## Ethical Considerations

This study does not use human annotators, crowdworkers, or research with human participants. Ethical concerns arise in downstream use of agentic retrieval over text-rich knowledge graphs. Retrieval errors can be treated as evidence and multi-step exploration can surface sensitive attributes present in graph text. The approach may also amplify biases in the underlying graph. If some languages and communities have sparse descriptions or different naming conventions, global lexical search and neighborhood ranking may under-retrieve relevant information, leading to unequal coverage across groups and reduced benefits for underrepresented stakeholders. We recommend safeguards before deployment, including redaction of sensitive fields and bias audits. Potential positive impact includes improving access to large knowledge graphs for language models, including information that may be difficult to access with text retrieval alone.

## Code Availability

All code used in this study is publicly available at <https://github.com/mims-harvard/ark>. A terminal-based chat implementation of is at <https://github.com/mims-harvard/ark-agent-cli>.

## Acknowledgments

We gratefully acknowledge the support of NSF CAREER 2339524, ARPA-H Biomedical Data Fabric (BDF) Toolbox Program, Harvard Data Science Initiative, Amazon Faculty Research, Google Research Scholar Program, AstraZeneca Research, Roche Alliance with Distinguished Scientists (ROADS) Program, Sanofi iDEA-iTECH Award, GlaxoSmithKline Award, Boehringer Ingelheim Award, Merck Award, Optum AI Research Collaboration Award, Pfizer Research, Gates Foundation (INV-079038), Aligning Science Across Parkinson's Initiative (ASAP), Chan Zuckerberg Initiative, John and Virginia Kaneb Fellowship at Harvard Medical School, Biswas Computational Biology Initiative in partnership with the Milken Institute, Harvard Medical School Dean's Innovation Fund for the Use of Artificial Intelligence, and the Kempner Institute for the Study of Natural and Artificial Intelligence at Harvard University. A.N. was supported by the Rhodes Scholarship. D.A.C. was funded by an NIHR Research Professorship (NIHR302440), a Royal Academy of Engineering Research Chair, and the InnoHK Hong Kong Centre for Cerebro-Cardiovascular Engineering, and was supported by the National Institute for Health Research Oxford Biomedical Research Centre and the Pandemic Sciences Institute at the University of Oxford. Any opinions, findings, conclusions, or recommendations expressed in this material are those of the authors and do not necessarily reflect the views of the funders.

### Dataset Statistics

**Table: Number of queries per dataset split for each STaRK graph.**

```latex
\begin{table}[H]
\centering
 \begin{tabular}{lrrr}
 \toprule
 Dataset & Train & Validation & Test \\
 \midrule
 PRIME & 6{,}162 & 2{,}240 & 2{,}016 \\
 MAG & 7{,}993 & 2{,}664 & 2{,}664 \\
 AMAZON & 5{,}915 & 1{,}547 & 1{,}638 \\
 \bottomrule
 \end{tabular}
 \caption{Number of queries per dataset split for each STaRK graph.}
 \label{tab:traj_counts}
\end{table}
```

**Table: Statistics of the constructed semi-structured knowledge graphs used in STaRK.**

```latex
\begin{table}[#1]
\centering
 \adjustbox{width=\columnwidth,center}{
 \begin{tabular}{lcccccc}
 \toprule
 Dataset
 & \makecell{Entity\\types}
 & \makecell{Relation\\types}
 & \makecell{Average\\degree}
 & \makecell{Entities}
 & \makecell{Relations}
 & \makecell{Tokens} \\
 \midrule
 AMAZON & 4 & 5 & 18.2 & 1{,}035{,}542 & 9{,}443{,}802 & 592{,}067{,}882 \\
 MAG & 4 & 4 & 43.5 & 1{,}872{,}968 & 39{,}802{,}116 & 212{,}602{,}571 \\
 PRIME & 10 & 18 & 125.2 & 129{,}375 & 8{,}100{,}498 & 31{,}844{,}769 \\
 \bottomrule
 \end{tabular}
 }
 \caption{Statistics of the constructed semi-structured knowledge graphs used in STaRK.}
 \label{tab:stark-statistics}
\end{table}
```

### Implementation Details

is run with $n{=}3$ parallel agents and a maximum trajectory length of $T_{\max}{=}20$.

For the distilled variant, we use Qwen3-8B [yang_qwen3_2025] (matching the model scale used by GraphFlow and Think-on-Graph with LLaMA3), trained via imitation on teacher trajectories, while keeping the tool interface and exploration hyperparameters fixed.

Each tool call is executed with a bounded retrieval budget. Neighborhood exploration uses a fixed budget of $k{=}20$ neighbors per expansion. Global search returns up to $k$ nodes from the full graph. By default $k{=}5$, but the agent may override this value as a tool parameter.

Each agent outputs an ordered list of selected nodes. We aggregate these lists by ranking nodes first by the number of agents that selected them (vote count), and breaking ties by the earliest position at which the node appears in any agent's list [\[sec:parallel_exploration\]](#sec:parallel_exploration){reference-type="ref+label" reference="sec:parallel_exploration"}. The aggregated ranking is truncated to the top 20 nodes to compute Recall@20; Hit@1 and MRR are computed on the same ranking.

### Additional Multi-Agent Analyses

[\[tab:budget-controlled\]](#tab:budget-controlled){reference-type="ref+Label" reference="tab:budget-controlled"} compares a single longer trajectory with three shorter parallel trajectories under the same total step budget (30 steps). The three-agent configuration performs better on all three graphs, indicating that the gains from multi-agent inference are not explained solely by taking more total steps.

### Trajectory-Level Tool Usage

[\[tab:trajectory-tool-mixing\]](#tab:trajectory-tool-mixing){reference-type="ref+Label" reference="tab:trajectory-tool-mixing"} summarizes tool usage at the trajectory level. Because every trajectory begins with [Global Search]{.smallcaps}, runs either remain global-search-only or invoke both tools. On AMAZON, most trajectories, including successful ones, remain global-only, consistent with its text-heavy queries. On MAG and PRIME, by contrast, successful retrieval usually requires combining [Global Search]{.smallcaps} with neighborhood expansion.

[\[tab:global-after-first-step\]](#tab:global-after-first-step){reference-type="ref+Label" reference="tab:global-after-first-step"} reports how often the agent returns to [Global Search]{.smallcaps} after the initial step. Re-anchoring is uncommon on AMAZON, but more frequent on MAG and especially PRIME, where retrieval more often requires shifting to a different region of the graph mid-trajectory. Together, [\[tab:trajectory-tool-mixing,tab:global-after-first-step\]](#tab:trajectory-tool-mixing,tab:global-after-first-step){reference-type="ref+Label" reference="tab:trajectory-tool-mixing,tab:global-after-first-step"} provide trajectory-level evidence for the two-tool design: AMAZON is often solved through lexical anchoring alone, whereas MAG and PRIME more often require combining global re-anchoring with local neighborhood expansion.

### Knowledge Graph Exploration Agent System Prompt

The system prompt instructs the agent on the available node and relation types, the two tool signatures ({Global Search} and {Neighborhood Exploration}), output formatting, and the stopping criterion. The full prompt is included in the public repository of at https://github.com/mims-harvard/ark.

{document}
