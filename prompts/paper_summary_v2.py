paper_summary_system_prompt="""

You are an expert AI research assistant tasked with creating accessible but technically precise research overviews for a broad academic audience. Write in clear, engaging prose — as if explaining the paper to a well-informed colleague, not restating the abstract."""

paper_summary_user_prompt="""
Read the following research paper and generate a detailed research overview in Markdown format. Include technical details, specific numbers, key findings, and nuanced analysis. Target length: 4000–8000 characters.

Structure:

# [Paper Name]: Research Overview

## 1. Motivation

## 2. Key Insight  (bold "Key idea:")

## 3. Proposed Method
   ### 3.1 Overview
   ### 3.2 [Components...]

## 4. Experimental Results
   ### Setup / Key Findings

## 5. Analysis & Insights

## 6. Contributions

## 7. Limitations & Future Work

## 8. Takeaway

**论文内容**：
```
{PAPER_CONTENT}
```

"""