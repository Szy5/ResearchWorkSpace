sci_pattern_classify_system_prompt="""You are an expert at classifying research thinking patterns. Be concise."""

sci_pattern_classify_user_prompt="""TAXONOMY:
{taxonomy_ref}

PAPERS:
{papers_text}

Classify each paper. Output JSON only:
{{"classifications": [{{"paper_index": 1, "primary_pattern": "P01", "secondary_patterns": ["P03"], "confidence": "high", "reasoning": "brief"}}]}}"""