from __future__ import annotations

import hashlib
from pathlib import Path

from paper_wiki.assets.models import AssetsManifest
from paper_wiki.core.models import PriorWorksDoc, SciPatternDoc
from paper_wiki.graph.models import ArtifactBundle


class ArtifactReader:
    """读取并校验 reviewed Layer1 语义产物集合。"""

    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir

    def load(self, slug: str) -> ArtifactBundle:
        artifact_dir = self.artifacts_dir / slug
        manifest_path = artifact_dir / "manifest.json"
        summary_path = artifact_dir / "summary.md"
        prior_works_path = artifact_dir / "prior_works.json"
        sci_pattern_path = artifact_dir / "sci_pattern.json"
        manifest = AssetsManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
        if manifest.slug != slug:
            raise ValueError(f"manifest slug mismatch: expected {slug}, got {manifest.slug}")
        if not summary_path.exists():
            raise FileNotFoundError(f"summary.md does not exist: {summary_path}")
        prior_works = PriorWorksDoc.model_validate_json(prior_works_path.read_text(encoding="utf-8"))
        sci_pattern = SciPatternDoc.model_validate_json(sci_pattern_path.read_text(encoding="utf-8"))
        artifact_hash = self._artifact_hash(manifest_path, summary_path, prior_works_path, sci_pattern_path)
        return ArtifactBundle(
            slug=slug,
            manifest=manifest,
            prior_works=prior_works,
            sci_pattern=sci_pattern,
            manifest_path=manifest_path,
            summary_path=summary_path,
            prior_works_path=prior_works_path,
            sci_pattern_path=sci_pattern_path,
            artifact_hash=artifact_hash,
        )

    def _artifact_hash(self, *paths: Path) -> str:
        digest = hashlib.sha256()
        for path in paths:
            digest.update(path.read_bytes())
        return digest.hexdigest()
