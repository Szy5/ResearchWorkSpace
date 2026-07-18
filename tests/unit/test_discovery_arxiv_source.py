from __future__ import annotations

import io
from pathlib import Path
import tarfile

from paper_wiki.core.config import Settings
from paper_wiki.discovery.models import SearchCandidate
from paper_wiki.discovery.sources import arxiv_source


ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v2</id>
    <updated>2024-01-03T00:00:00Z</updated>
    <published>2024-01-02T00:00:00Z</published>
    <title>  Test   Paper  </title>
    <summary> A useful abstract. </summary>
    <author><name>Ada Lovelace</name></author>
    <category term="cs.AI"/>
    <arxiv:announce_type>new</arxiv:announce_type>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.99999v1</id>
    <updated>2024-01-04T00:00:00Z</updated>
    <published>2024-01-04T00:00:00Z</published>
    <title>Updated Paper</title>
    <summary>Only an update.</summary>
    <arxiv:announce_type>replace</arxiv:announce_type>
  </entry>
</feed>
"""


class FakeResponse:
    def __init__(self, text: str = "", content: bytes = b"ok", status_code: int = 200) -> None:
        self.text = text
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("bad status")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def iter_content(self, chunk_size: int) -> list[bytes]:
        return [self.content]


def test_daily_candidates_parses_only_new_entries(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(arxiv_source.ArxivThrottle, "acquire", lambda self: None)
    monkeypatch.setattr(arxiv_source.requests, "get", lambda *args, **kwargs: FakeResponse(text=ATOM))
    settings = Settings(project_root=tmp_path, raw_dir=tmp_path / "raw", artifacts_dir=tmp_path / "artifacts")

    candidates = arxiv_source.daily_candidates("cs.AI", settings=settings)

    assert candidates == [
        SearchCandidate(
            title="Test Paper",
            authors=["Ada Lovelace"],
            year=2024,
            abstract="A useful abstract.",
            url="https://arxiv.org/abs/2401.12345",
            venue="cs.AI",
            arxiv_id="2401.12345",
            publication_date="2024-01-02",
            source="arxiv",
        )
    ]


RSS_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>oai:arXiv.org:2607.10562</id>
    <updated>2026-07-14T00:00:00Z</updated>
    <published>2026-07-14T00:00:00Z</published>
    <title>RSS Feed Paper</title>
    <summary>An abstract from the daily RSS feed.</summary>
    <author><name>Grace Hopper</name></author>
    <category term="cs.AI"/>
    <arxiv:announce_type>new</arxiv:announce_type>
  </entry>
</feed>
"""


def test_daily_candidates_normalizes_oai_style_rss_ids(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(arxiv_source.ArxivThrottle, "acquire", lambda self: None)
    monkeypatch.setattr(arxiv_source.requests, "get", lambda *args, **kwargs: FakeResponse(text=RSS_ATOM))
    settings = Settings(project_root=tmp_path, raw_dir=tmp_path / "raw", artifacts_dir=tmp_path / "artifacts")

    candidates = arxiv_source.daily_candidates("cs.AI", settings=settings)

    assert candidates[0].arxiv_id == "2607.10562"
    assert candidates[0].url == "https://arxiv.org/abs/2607.10562"


def test_normalize_arxiv_id_strips_oai_prefix() -> None:
    assert arxiv_source.normalize_arxiv_id("oai:arXiv.org:2607.10562") == "2607.10562"
    assert arxiv_source.normalize_arxiv_id("oai:arXiv.org:2607.10562v3") == "2607.10562"


def test_find_main_tex_prefers_single_matching_bbl(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "paper.tex").write_text("no document here", encoding="utf-8")
    (source / "paper.bbl").write_text("refs", encoding="utf-8")
    (source / "other.tex").write_text(r"\begin{document}other\end{document}", encoding="utf-8")

    assert arxiv_source.find_main_tex(source) == source / "paper.tex"


def test_extract_source_preserves_tarball(tmp_path: Path) -> None:
    archive_path = tmp_path / "source.tar"
    with tarfile.open(archive_path, "w") as archive:
        payload = b"\\begin{document}Hi\\end{document}"
        info = tarfile.TarInfo("main.tex")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    destination = tmp_path / "out"
    destination.mkdir()
    arxiv_source._extract_source(archive_path, destination)

    assert (destination / "main.tex").read_text(encoding="utf-8") == r"\begin{document}Hi\end{document}"

