## General response to all reviewers
We sincerely thank the detailed comments from all reviewers. We have carefully revised the paper according to the comments, and the edits have been highlighted in BLUE.  We also provide a detailed response to each comment below. Here we highlight our major revisions, and respond to each reviewer below. We hope our responses can properly address your concerns.

1. Addressing the comments of Reviewer ZzpQ, we have revised the approach section (Section 4) by providing more explanation to improve its readability.
2. Addressing the comments of Reviewer ZzpQ and qFDd, we have revised the experiment settings by providing more details about the used LLMs (Appendix A.6) and version of ChatGPT (Appendix A.5).
3. Addressing the comments of Reviewers ZzpQ and 1bmQ, we have discussed the transferability of RoG to other KGs and provided the results in Appendix A.7.1.
4. Addressing the comments of Reviewers 1bmQ and cFys, we have carefully revised the math equations to make them more rigorous.
5. Addressing the comments of Reviewers 1bmQ and cFys, we have presented the performance of RoG trained on single datasets and compared it with other finetuned LLMs in Appendix A.7.2 and A.7.3, respectively, to enable a fair comparison.

## Response to Reviewer ZzpQ
We thank the reviewer for the positive comments. We have revised the manuscript according to your comments and provided a detailed response to each comment below.  We hope our answers can address your questions.

## Weakness 1
>  The approach section was hard to read. --- More specifically, the order of explanation was a bit hard to follow. Before explaining the optimization, I think explaining the flow of information step-by-step will be helpful when you point to Figure 3 in the beginning. In the optimization part, explaining what kind of ground-truth supervision is used was not very explicit. Using the retrieved paths from the KG as a source of supervision could be made clear earlier in the approach.

### Response
Thank you for your comment. We have revised the approach section to improve its readability. Regarding the framework, we have introduced the components of our method at the beginning and described them in the caption of Figure 2, where we provide a step-by-step description of our approach. 

Additionally, regarding the issue of what ground-truth supervision is, we would like to clarify that we use the shortest paths that connect the questions and answer entities in the KG as the supervision signals. We have revised Equation 4 in our paper to clarify this point. The detailed derivation can be found in Appendix A.1 and our responses to Reviewer 1bmQ.

## Weakness 2
> The training approach seems to be very costly. It needs training and instruction-tuning for the LLMs to generate the relation and KG-specific paths. If we train with a specific KG the results will improve in answering questions from that specific KG --which of course is the scope of this work. However, I am not sure if this helps LLM's QA capability in general and the issues set in front including hallucination and lack of knowledge in general.

### Response
Admittedly, the training process of our method could be costly. However, we want to emphasize that after training, our method enables the generalizability of transferring to new KGs and QA datasets with only a few steps of finetuning. 

In Appendix A.7.1, we evaluate the transferability of RoG to other KGs. We select the MetaQA-3hop dataset, which is based on Wiki-Movies KGs. The experiment results show that RoG trained on Freebase KGs can be effectively transferred to Wiki-Movies KGs with only 1000 samples. The performance of transferring is better than training from scratch. This indicates that RoG empowers the reasoning on graph ability via training, which can be transferred to new KGs to improve the model's performance on this new KG. We also present the training and transferring time below (also in Table 12). As can be seen, the transferring time is much less than the training time.

Performance on MetaQA-3hop (F1)

|  Method   | Only Train on Wiki-Movies | Transferring from Freebase |
| :---: | :-----------------------: | :------------------------: |
|  RoG  |           41.32           |           50.68            |

Training time comparison.
| Time | Training on Freebase | Transferring to Wiki-Movies |
| :--: | :------------------: | :-------------------------: |
| RoG  |        38 hours        |            2 hours            |

## Question 1: 
> If I understood correctly when you refer to retrieval and reasoning/planning modules of ROG, those are the outcome of instruction-tuning of a specific large language model. When you discussed the ROG model, it was not clear to me what was the base LLM; Which language model was used and tuned for those results of ROG? when you combine ROG with other language models in Table 4, which one has been used again in the planning module?

## Response
We use LLaMA2-Chat-7B as the LLMs in our experiments. When we combine RoG with other language models, we use the planning module to generate plans (relation paths). The plans are executed on KGs to retrieve the reasoning paths. The retrieved paths are fed into different LLMs during inference using the reasoning prompts template shown in Appendix A.10. This enables them to be combined with RoG without retraining. We have revised the paper by adding more details to the implementation settings in Appendix A.6.

## Response to Reviewer qFDd

## Question 1
> Can you clarify which version of ChatGPT was used?

### Response
We greatly appreciate the reviewer’s recognition of our work. We want to clarify that we use ChatGPT-3.5-turbo in our experiments. Experiments are conducted with models released between July. to Sept., 2023. We have revised the paper (Appendix A.5) to clarify this point.

## Response to Reviewer 1bmQ

We sincerely thank the reviewer for specific comments. We have provided a detailed response to each comment below. We hope our answers can properly address your concerns.

## Weakness 1
> There is some nonrigorous math in the paper. 

### Response
We truly thank the reviewer for pointing out these issues! We have carefully revised the paper to fix the nonrigorous math equations.

The revised Equation 4 in our paper is shown here. 
$$
\begin{align}
    \mathcal{L}_{\text{plan}} = D_{KL}(Q(z)||P_\theta(z|q)) &= D_{KL}(Q(z|a, q, \mathcal{G})||P_\theta(z|q)),\tag{1} \\
    &\simeq - \frac{1}{|\mathcal{Z^*}|}\sum_{z\in\mathcal{Z^*}} \log P_\theta(z|q),\tag{2}
\end{align}
$$
where $\mathcal{Z}^*\subseteq\mathcal{Z}$ denotes the set of shortest paths between $e_q$ and $e_a$ in KGs, and $\mathcal{Z}$ denotes all valid relation paths in KGs.

Due to the limitation of space, we put the detailed derivation in Appendix A.1, which is also shown as follows.

The posterior distribution $Q(z)$ can be approximated by $Q(z|a, q, \mathcal{G})$, given as
$$
\begin{equation}
    \tag{3}
    Q(z) \simeq Q(z|a,q,\mathcal{G}) = \begin{cases}
    & \frac{1}{|\mathcal{Z}|}, \exists w_z(e_q,e_a)\in \mathcal{G},\\
    & 0, \text{else},
    \end{cases}
\end{equation}
$$
where we assume a uniform distribution over all valid relation paths $\mathcal{Z}$ [1].

Thus, the KL divergence can be calculated as
$$
\begin{align}
\mathcal{L}_{\text{plan}} = D_{KL}(Q(z)||P_\theta(z|q)) &= D_{KL}(Q(z|a, q, \mathcal{G})||P_\theta(z|q)), \tag{4}\\
&=\mathbb{E}_{z\sim Q(z|a, q, \mathcal{G})}[\log Q(z|a, q, \mathcal{G})-\log P_\theta(z|q)], \tag{5}\\
&= - \mathbb{E}_{z\sim Q(z|a, q, \mathcal{G})}\log P_\theta(z|q) + \text{CONST}, \tag{6}
\end{align}
$$
where the expectations cannot be computed exactly because of the large number of valid relation paths $\mathcal{Z}$, so we approximate it by using the set of shortest paths $\mathcal{Z}^*\subseteq\mathcal{Z}$ between $e_q$ and $e_a$ in KGs. This can be formulated as
$$
\begin{align}
\mathcal{L}_{\text{plan}} = - \sum_{z\in\mathcal{Z^*}} Q(z|a, q, \mathcal{G}) \log P_\theta(z|q) + \text{CONST}. \tag{7}
\end{align}
$$
By assuming a uniform distribution over the set of shortest paths $\mathcal{Z}^*$, we can rewrite Eq. (7) as
$$
\begin{align}
\mathcal{L}_{\text{plan}} & = - \frac{1}{|\mathcal{Z^*}|}\sum_{z\in\mathcal{Z^*}} \log P_\theta(z|q) + \text{CONST}.\tag{8}
\end{align}
$$
We keep the CONST in the equation. However, we omit it in the final objective since it makes no contributions to the optimization. 

The revised Equation 6 in our paper is presented here.
$$
\begin{align}
    \mathcal{L}_{\text{reason}} &= \mathbb{E}_{z\sim Q(z|a, q, \mathcal{G})}[\log P_\theta(a|q,z,\mathcal{G})],\tag{9}\\ 
    &= \sum_{z\in\mathcal{Z}^*_K} \log P_\theta(a|q,z,\mathcal{G}), \tag{10}\\ 
    &=  \log P_\theta(a|q,\mathcal{Z}^*_{K},\mathcal{G}). \tag{11}
\end{align}
$$
The expectation is approximated by sampling $K$ plans from the $\mathcal{Z^*}$, denoted as $\mathcal{Z}^*_K\subseteq \mathcal{Z}^*$. The conversion from Eq. (9) to Eq. (10) is based on the FiD framework [1], where we can simultaneously use multiple plans for reasoning. The FiD framework is introduced in Equation 5 of our paper, which is also shown here.

The FiD framework assumes each $z\in \mathcal{Z}$ contributes independently. The probability $P_\theta(a|q,\mathcal{Z},\mathcal{G})$ can be approximated as the product of each $P_\theta(a|q,z,\mathcal{G})$, which is formulated as
$$
\begin{equation}
    P_\theta(a|q,\mathcal{Z},\mathcal{G}) = \prod_{z\in\mathcal{Z}} P_\theta(a|q,z,\mathcal{G}). \tag{12}
\end{equation}
$$

We also want to clarify the marginalization in Equation 10 of our paper is reasonable based on the FiD framework shown in Eq. (12), which can be derived as

$$
\begin{align*}
&\text{Because:} \\
& P_\theta(a|q,\mathcal{Z},\mathcal{G}) = \prod_{z\in\mathcal{Z}} P_\theta(a|q,z,\mathcal{G}), \\
&\Rightarrow \\
&\log P_\theta(a|q,\mathcal{Z}^*_K, \mathcal{G}) = \log \sum_{z\in\mathcal{Z}^*_K} P_\theta(a|q,z,\mathcal{G}), \\
&\Rightarrow \\
&\underset{\theta}{\operatorname{arg max}}\log P_\theta(a|q,\mathcal{Z}^*_K, \mathcal{G}) = \underset{\theta}{\operatorname{arg max}} \log \sum_{z\in\mathcal{Z}^*_K} P_\theta(a|q,z,\mathcal{G}), \\
&= \underset{\theta}{\operatorname{arg max}} \log \sum_{z\in\mathcal{Z}^*_K}\sum_{w_z\in\mathcal{W}_z}\prod_{t=1}^{|a|}P_\theta(t_i|t_{<i}, q, w_z), \\
&\text{Q.E.D.}
\end{align*}
$$

[1] Singh, D., Reddy, S., Hamilton, W., Dyer, C., & Yogatama, D. (2021). End-to-end training of multi-document reader and retriever for open-domain question answering. Advances in Neural Information Processing Systems, 34, 25968-25981.


## Weakness 2
> Would the fine-tuned LLM generalize to other QA datasets, in addition to the datasets that it is fine-tuned on?

### Response
In Appendix A.7.1, we evaluate the transferability of RoG to other KGs. We select the MetaQA-3hop dataset, which is based on Wiki-Movies KGs. The experiment results show that RoG trained on Freebase KGs can be effectively transferred to Wiki-Movies KGs with only 1000 samples. The performance of transferring is better than training from scratch. This indicates that RoG empowers the reasoning on graph ability via training, which can be transferred to new KGs to improve the performance. We also present the training and transferring time here. The transferring time is much less than the training time.

Performance on MetaQA-3hop (F1)

|  F1   | Only Train on Wiki-Movies | Transferring from Freebase |
| :---: | :-----------------------: | :------------------------: |
|  RoG  |           41.32           |           50.68            |

Training time comparison.

| Time | Training on Freebase | Transferring to Wiki-Movies |
| :--: | :------------------: | :-------------------------: |
| RoG  |        38 hours        |            2 hours            |

## Weakness 3
> I don't see the usefulness of having RoG as a planning module for other LLMs.

### Response
The reason why other LLMs, when integrated with the planning module of RoG cannot outperform the full RoG is that these LLMs are not trained to understand the reasoning paths and conduct reasoning, as mentioned in Section 4.2. This also demonstrates the importance of reasoning optimization.

However, even without training, This experiment shows that the plans generated by the planning module still exhibit great interpretability and can be used by other LLMs to improve their performance. This further opens the possibility of separating the reasoning and generation modules of RoG in the future. For example, we can use a relatively simple LLM to generate the plans and train a larger and more powerful LLM to conduct reasoning based on the generated plans. This experiment shows the flexibility of RoG in actual practices.

## Question 1
> Is RoG trained on both WebQSP and CWQ at the same time or is it trained separately on these two datasets? I'm not super familiar with the KGQA baselines, but I wonder if all baselines are trained on the same data as RoG. If the baselines are only trained on one of the datasets each time, then it's not fair to compare RoG with them, if RoG is trained on both of them at the same time.

### Response
We thank the reviewer for the question. We first want to clarify that the results reported in the paper are achieved by RoG jointly trained on the training set of both datasets. The reason is that RoG requires the questions and answers that are linked with entities in KGs for training. Since CWQ and WebQSP are both based on Freebase KGs, we use them together to maximize the ability of RoG for reasoning on Freebase KGs. One of the previous KGQA STOA -- Decaf [2] also jointly trains its model with multiple QA datasets on Freebase, including WebQSP and CWQ. 

To fairly compare with other methods (e.g., UniKGQA) that are only trained on a single dataset, we provide additional results of the performance of RoG trained on a single dataset. From the results (below), we can see that RoG trained on a single dataset still outperforms the STOA baselines (UniKGQA). Besides, we can also find that jointly training RoG on multiple datasets can further improve the performance. In the future, we will try to generate more QA datasets from Freebase to further improve the reasoning ability of RoG. We have revised the paper by providing the results in Appendix A.7.2.

Performance on WebQSP.
| Method  | Train Data            | Hits@1 | F1   |
| ------- | --------------------- | ------ | ---- |
| UniKGQA | WebQSP                | 77.2   | 72.2 |
| RoG     | WebQSP                | 81.5   | 67.1 |
| ROG     | WebQSP+CWQ            | 85.7   | 70.8 |

Performance on CWQ.
| Method  | Train Data            | Hits@1 | F1   |
| ------- | --------------------- | ------ | ---- |
| UniKGQA | CWQ                   | 51.2   | 49.1 |
| RoG     | CWQ                   | 59.1   | 52.9 |
| ROG     | WebQSP+CWQ            | 62.6   | 56.2 |

[2] Yu, D., Zhang, S., Ng, P., Zhu, H., Li, A. H., Wang, J., ... & Xiang, B. (2022, September). DecAF: Joint Decoding of Answers and Logical Forms for Question Answering over Knowledge Bases. ICLR 2023.

## Response to Reviewer cFys

## Weakness 1
> From equation 1, I understand the authors want to decompose the prediction task into two parts: getting hidden variable z and then predicting the answer with the hidden variable. However, it's not clear whether equations 2-6 are necessary. Could you provide more intuition behind for explanation?
> Even if motivation exists, I'm not sure why equation 3 holds. Why is there only one path / relation path and it's faithful? For example, there could be multiple solutions/paths; if so, equation 3 might not hold. The authors should provide more justification for the equation 3.

### Response
We thank the reviewer for the question and for pointing out the issue in Equation 3. 

In equation 1, we want to illustrate the general purpose of RoG, which first generates a set of plans (planning module) and then conducts the reasoning on KGs with the plans (retrieval-reasoning module). However, directly optimizing Equation 1 is intractable due to the combination of hidden variable $z$ [1]. Therefore, we derive the evidence lower bound (ELBO) of Equation 1 in Equation 2-6 and come up with the viable optimization objective in Equation 7.

To clarify the misunderstanding, we want to correct Equation 3 in our paper as follows:
$$
\begin{equation}
    Q(z) \simeq Q(z|a,q,\mathcal{G}) = \begin{cases}
    & \frac{1}{|\mathcal{Z}|}, \exists w_z(e_q,e_a)\in \mathcal{G},\\
    & 0, \text{else},
    \end{cases}
\end{equation}
$$
where we assume there are multiple plans $z\in\mathcal{Z}$ which obey a uniform distribution [1].

[1] Singh, D., Reddy, S., Hamilton, W., Dyer, C., & Yogatama, D. (2021). End-to-end training of multi-document reader and retriever for open-domain question answering. NeurIPS 2021, 34, 25968-25981.

## Weakness 2
> One of the key points in the framework is the finetuned LLM (i.e., \theta). However, in the main paper, it's not clear how the LLM is finetuned. It seems the objective functions follow the equation 7. However, these two modules are not evaluated individually and there is no validation loss provided. Only the final framework performance can prove that these modules work as expected, which is not sufficient for readers to know why they can work.

### Response
We thank the reviewer for the question. We have revised the paper to clarify the training process of RoG in equation 7 (based on the comments of Reviewer 1bmQ). The objective in equation 7 contains two terms: retrieval-reasoning optimization and planning optimization.  We optimize the objective in Equation 7 by maximizing the likelihood of predicting the correct answer and generating valid plans. 

To demonstrate the performance of each module individually, we conduct ablation studies in Table 3, where we remove the planning and reasoning modules, respectively. From the results, we can see that both these modules are helpful for the performance of RoG.

Ablation studies of RoG.

| Method            | WebQSP (F1) | CWQ (F1) |
| ----------------- | ----------- | -------- |
| RoG               | 70.81       | 56.17    |
| RoG w/o planning  | 49.69       | 33.76    |
| RoG w/o reasoning | 49.56       | 22.26    |

## Weakness 3
> Over-claim sentences. The authors claim that their RoG framework can address the hallucination issue and lack of knowledge issue. However, studies with several cases are definitely not sufficient to prove them. I would suggest adding more comprehensive results or changing the claim.

### Response
Thank you for the comments. We have revised the paper by changing the claim to "RoG can **alleviate** the hallucination issue and lack of knowledge issue".


## Question 1
> For the KG, is that constructed by yourself and used for all tasks, or is it provided in the dataset?

### Response
For the KG, we use the KG preprocessed by previous works [2].

[2] He, G., Lan, Y., Jiang, J., Zhao, W. X., & Wen, J. R. (2021, March). Improving multi-hop knowledge base question answering by learning intermediate supervision signals. WSDM 2021

## Question 2
> In equation 4, the final equality, the constant term is missing.

### Response
Thanks for pointing it out, we have revised Equation 4. We omit the const in the final objective since it makes no contributions to the optimization. The detailed derivation can be found in Appendix A.1 and in our response to Reviewer 1bmQ.
$$
\begin{align}
    \mathcal{L}_{\text{plan}} = D_{KL}(Q(z)||P_\theta(z|q)) &= D_{KL}(Q(z|a, q, \mathcal{G})||P_\theta(z|q)), \\
    &\simeq - \frac{1}{|\mathcal{Z^*}|}\sum_{z\in\mathcal{Z^*}} \log P_\theta(z|q),
\end{align}
$$

## Question 3
> In Table 2, RoG is finetuned LM, but it's compared with LLMs under the zero/few-shot setting. Is that a fair comparison?

### Response
Thanks for the questions, we have revised our paper by providing the performance of LLM finetuned on the training set of WebQSP and CWQ. From the results, we can see that RoG still outperforms the LLMs finetuned on the training set of WebQSP and CWQ.  We have revised the paper by providing the results in Appendix A.7.3.

Performance comparison with various finetuned LLMs.

| Method                       | WebQSP (Hits@1) | CWQ (Hits@1) |
| ---------------------------- | --------------- | ------------ |
| Alpaca-7B  (Zero Shot)         | 51.78           | 27.44        |
| LLaMA2-Chat-7B  (Zero Shot) | 64.37           | 34.60        |
| Alpaca-7B (Finetuned)           | 74.57           | 55.98        |
| LLaMA2-Chat-7B  (Finetuned)  | 73.89           | 53.49        |
| RoG                          | 85.75           | 62.65        |

