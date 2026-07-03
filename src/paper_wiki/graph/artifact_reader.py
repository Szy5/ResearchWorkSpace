from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from paper_wiki.core.models import PriorWorksDoc, SciPatternDoc, SummaryFrontmatter
from paper_wiki.graph.models import ArtifactBundle


class ArtifactReader:
    """读取并校验 reviewed Layer1 三件套。"""

    def __init__(self, artifacts_dir: Path) -> None:
        self.artifacts_dir = artifacts_dir

    def load(self, slug: str) -> ArtifactBundle:
        artifact_dir = self.artifacts_dir / slug
        summary_path = artifact_dir / "summary.md"
        prior_works_path = artifact_dir / "prior_works.json"
        sci_pattern_path = artifact_dir / "sci_pattern.json"
        summary = self._load_summary(summary_path)
        prior_works = PriorWorksDoc.model_validate_json(prior_works_path.read_text(encoding="utf-8"))
        sci_pattern = SciPatternDoc.model_validate_json(sci_pattern_path.read_text(encoding="utf-8"))
        artifact_hash = self._artifact_hash(summary_path, prior_works_path, sci_pattern_path)
        return ArtifactBundle(
            slug=slug,
            summary=summary,
            prior_works=prior_works,
            sci_pattern=sci_pattern,
            summary_path=summary_path,
            prior_works_path=prior_works_path,
            sci_pattern_path=sci_pattern_path,
            artifact_hash=artifact_hash,
        )

    def _load_summary(self, summary_path: Path) -> SummaryFrontmatter:
        text = summary_path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, flags=re.DOTALL)
        if not match:
            raise ValueError(f"summary.md is missing YAML frontmatter: {summary_path}")
        frontmatter = yaml.safe_load(match.group(1)) or {}
        for key in ["slug", "title", "venue", "arxiv_id"]:
            if key in frontmatter and frontmatter[key] is not None and not isinstance(frontmatter[key], str):
                frontmatter[key] = str(frontmatter[key])
        return SummaryFrontmatter.model_validate(frontmatter)

    def _artifact_hash(self, *paths: Path) -> str:
        digest = hashlib.sha256()
        for path in paths:
            digest.update(path.read_bytes())
        return digest.hexdigest()
