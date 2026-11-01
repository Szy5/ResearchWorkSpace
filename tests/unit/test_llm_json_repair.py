import json

from paper_wiki.ingestion.llm_client import OpenAIClient, repair_llm_json


def test_repair_llm_json_escapes_inner_quotes() -> None:
    broken = (
        '{\n'
        '  "relationship_sentence": "本文直接借鉴了 "CycleGAN" 中的循环一致性思想。"\n'
        '}'
    )

    repaired = repair_llm_json(broken)

    assert json.loads(repaired)["relationship_sentence"] == '本文直接借鉴了 "CycleGAN" 中的循环一致性思想。'


def test_extract_json_repairs_gemini_style_payload() -> None:
    client = object.__new__(OpenAIClient)
    text = """```json
{
  "prior_works": [
    {
      "title": "CycleGAN",
      "authors": "Zhu et al.",
      "year": 2017,
      "arxiv_id": "1703.10593",
      "role": "Inspiration",
      "relationship_sentence": "本文直接借鉴了 "CycleGAN" 中通过逆向映射来评估转换质量的循环一致性思想。"
    }
  ],
  "synthesis_narrative": "先前工作如 "ReAct" 与 "Search-R1" 启发了本文。"
}
```"""

    parsed = client._extract_json(text)

    assert parsed["prior_works"][0]["title"] == "CycleGAN"
    assert '"CycleGAN"' in parsed["prior_works"][0]["relationship_sentence"]
    assert '"ReAct"' in parsed["synthesis_narrative"]
