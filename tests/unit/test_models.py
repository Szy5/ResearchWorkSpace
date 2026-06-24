import pytest
from pydantic import ValidationError

from paper_wiki.core.models import PriorWorkEntry, PriorWorksDoc, SciPatternDoc


def test_prior_works_schema_accepts_valid_roles() -> None:
    doc = PriorWorksDoc(
        target_slug="tiny",
        target_title="Tiny",
        prior_works=[
            PriorWorkEntry(
                title="Prior",
                authors="A. Author et al.",
                year=2024,
                role="Foundation",
                relationship_sentence="It defines the graph reasoning setting used by the current work.",
            )
        ],
        synthesis_narrative="A concise synthesis.",
    )

    assert doc.prior_works[0].role.value == "Foundation"


def test_pattern_schema_rejects_unknown_pattern() -> None:
    with pytest.raises(ValidationError):
        SciPatternDoc(
            target_slug="tiny",
            target_title="Tiny",
            primary_pattern="P99",
            confidence="high",
            reasoning="Invalid pattern should fail.",
        )
