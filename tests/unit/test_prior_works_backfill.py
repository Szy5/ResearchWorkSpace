from paper_wiki.ingestion.pipeline import IngestPipeline  # noqa: F401 - 建立安全的模块导入顺序
from paper_wiki.ingestion import prior_works_backfill
from paper_wiki.core.config import Settings
from paper_wiki.core.enums import PriorWorkRole
from paper_wiki.core.models import PriorWorkEntry, PriorWorksDoc
from paper_wiki.discovery.models import SearchCandidate


def _entry(**overrides) -> PriorWorkEntry:
    defaults = dict(
        title="Graph QA Foundations",
        authors="Smith et al.",
        year=None,
        arxiv_id="",
        role=PriorWorkRole.FOUNDATION,
        relationship_sentence="It defines the setup extended by the current work.",
    )
    defaults.update(overrides)
    return PriorWorkEntry(**defaults)


def _doc(entries: list[PriorWorkEntry]) -> PriorWorksDoc:
    return PriorWorksDoc(prior_works=entries, synthesis_narrative="Narrative.")


def test_backfills_title_authors_year_arxiv_id_on_confident_match(monkeypatch):
    settings = Settings(api_key="test")
    matched = SearchCandidate(
        title="Graph QA Foundations",
        authors=["Alice Smith", "Bob Lee"],
        year=2021,
        arxiv_id="2101.00001",
    )
    monkeypatch.setattr(prior_works_backfill.discovery_search, "search", lambda *a, **k: [matched])

    result = prior_works_backfill.backfill_prior_works_from_arxiv(_doc([_entry()]), settings)

    entry = result.prior_works[0]
    assert entry.arxiv_id == "2101.00001"
    assert entry.authors == "Alice Smith, Bob Lee"
    assert entry.year == 2021
    assert entry.title == "Graph QA Foundations"


def test_skips_backfill_when_no_candidate_is_similar_enough(monkeypatch):
    settings = Settings(api_key="test")
    unrelated = SearchCandidate(
        title="Completely Unrelated Paper About Robotics",
        authors=["Someone Else"],
        year=2019,
        arxiv_id="1901.99999",
    )
    monkeypatch.setattr(prior_works_backfill.discovery_search, "search", lambda *a, **k: [unrelated])

    result = prior_works_backfill.backfill_prior_works_from_arxiv(_doc([_entry()]), settings)

    entry = result.prior_works[0]
    assert entry.arxiv_id == ""
    assert entry.authors == "Smith et al."
    assert entry.year is None


def test_does_not_overwrite_entry_that_already_has_arxiv_id(monkeypatch):
    settings = Settings(api_key="test")
    called = False

    def _fail_if_called(*args, **kwargs):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(prior_works_backfill.discovery_search, "search", _fail_if_called)

    result = prior_works_backfill.backfill_prior_works_from_arxiv(
        _doc([_entry(arxiv_id="2010.00042")]), settings
    )

    assert not called
    assert result.prior_works[0].arxiv_id == "2010.00042"


def test_search_failure_is_swallowed_and_entry_left_untouched(monkeypatch):
    settings = Settings(api_key="test")

    def _raise(*args, **kwargs):
        raise RuntimeError("network down")

    monkeypatch.setattr(prior_works_backfill.discovery_search, "search", _raise)

    result = prior_works_backfill.backfill_prior_works_from_arxiv(_doc([_entry()]), settings)

    assert result.prior_works[0].arxiv_id == ""
