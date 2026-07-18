from __future__ import annotations

import io
from pathlib import Path
import tarfile

from paper_wiki.core.config import Settings
from paper_wiki.discovery.sources import arxiv_source


def test_fetch_downloads_extracts_and_writes_raw_dir(monkeypatch, tmp_path: Path) -> None:
    def fake_download_source(arxiv_id: str, destination: Path, settings: Settings) -> None:
        with tarfile.open(destination, "w") as archive:
            files = {
                "main.tex": b"\\documentclass{article}\\begin{document}\\input{sections/method}\\end{document}",
                "sections/method.tex": b"Method body",
                "main.bbl": b"Refs",
            }
            for name, payload in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))

    def fake_download_pdf(arxiv_id: str, destination: Path, settings: Settings) -> bool:
        destination.write_bytes(b"%PDF")
        return True

    settings = Settings(project_root=tmp_path, raw_dir=tmp_path / "raw", artifacts_dir=tmp_path / "artifacts")
    monkeypatch.setattr(arxiv_source, "_download_source_archive", fake_download_source)
    monkeypatch.setattr(arxiv_source, "_download_pdf", fake_download_pdf)

    result = arxiv_source.fetch("2401.12345v1", settings=settings)

    assert result.slug == "2401.12345"
    assert result.entry_file == "main.tex"
    assert result.has_pdf is True
    assert (tmp_path / "raw" / "2401.12345" / "main.tex").exists()
    assert (tmp_path / "raw" / "2401.12345" / "sections" / "method.tex").exists()
    assert (tmp_path / "raw" / "2401.12345" / "paper.pdf").exists()
