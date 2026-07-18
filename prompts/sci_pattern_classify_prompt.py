sci_pattern_classify_system_prompt="""你是一位擅长分类研究思维模式的专家."""

sci_pattern_classify_user_prompt="""
TAXONOMY:
{taxonomy_ref}

原论文:
{papers_text}

对原论文进行分类。输出JSON格式如下并且使用中文进行回答：
{{"classifications": [{{"paper_index": 1, "primary_pattern": "P01", "secondary_patterns": ["P03"], "confidence": "high", "reasoning": "brief"}}]}}

reasoning 中提到论文、模型、数据集名称时使用直引号 "…"，禁止使用中文书名号《…》。
"""