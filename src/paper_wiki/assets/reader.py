from __future__ import annotations

from pathlib import Path

from paper_wiki.assets.models import AssetsManifest, FiguresDoc, PaperAssetsBundle, ReferencesDoc, SectionsDoc
from paper_wiki.core.config import Settings, get_settings
from paper_wiki.core.validation import validate_slug


class AssetsReader:
    """Load canonical per-paper assets without reading raw/{slug}."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def load(self, slug: str) -> PaperAssetsBundle:
        self._validate_slug(slug)
        artifact_dir = self.settings.resolved_artifacts_dir() / slug
        manifest_path = artifact_dir / "manifest.json"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"assets manifest does not exist: {manifest_path}")

        manifest = AssetsManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        paper_path = self._asset_path(artifact_dir, manifest.files.paper_text)
        sections_path = self._asset_path(artifact_dir, manifest.files.sections)
        figures_path = self._asset_path(artifact_dir, manifest.files.figures)
        references_path = self._asset_path(artifact_dir, manifest.files.references)

        return PaperAssetsBundle(
            slug=slug,
            artifact_dir=artifact_dir,
            manifest=manifest,
            paper_markdown=paper_path.read_text(encoding="utf-8"),
            sections=SectionsDoc.model_validate_json(sections_path.read_text(encoding="utf-8")),
            figures=FiguresDoc.model_validate_json(figures_path.read_text(encoding="utf-8")),
            references=ReferencesDoc.model_validate_json(references_path.read_text(encoding="utf-8")),
        )

    def _asset_path(self, artifact_dir: Path, relative_path: str) -> Path:
        path = (artifact_dir / relative_path).resolve()
        path.relative_to(artifact_dir.resolve())
        if not path.is_file():
            raise FileNotFoundError(f"asset file does not exist: {path}")
        return path

    def _validate_slug(self, slug: str) -> None:
        validate_slug(slug)
