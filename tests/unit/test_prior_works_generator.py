from paper_wiki.ingestion.generators.prior_works_generator import PriorWorksGenerator


class _TranslateLLM:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        return "本文直接建立在 \"Graph-R1\" 之上。"


def test_english_narrative_is_translated() -> None:
    llm = _TranslateLLM()
    generator = PriorWorksGenerator(llm, prompts_dir=None)  # type: ignore[arg-type]

    result = generator.ensure_chinese_narrative("This work builds directly on Graph-R1.")

    assert result == "本文直接建立在 \"Graph-R1\" 之上。"
    assert llm.calls == 1


def test_chinese_narrative_is_kept() -> None:
    llm = _TranslateLLM()
    generator = PriorWorksGenerator(llm, prompts_dir=None)  # type: ignore[arg-type]
    narrative = "本文受 \"Search-R1\" 与 \"Graph-R1\" 启发，将检索动作改为菜单选择。"

    assert generator.ensure_chinese_narrative(narrative) == narrative
    assert llm.calls == 0
