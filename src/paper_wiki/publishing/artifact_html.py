from __future__ import annotations

from pathlib import Path

from paper_wiki.publishing.exceptions import ArtifactHTMLNotFoundError, ArtifactPathError
from paper_wiki.publishing.models import ArtifactHTML


def _ensure_child_path(path: Path, parent: Path) -> None:
    try:
        path.relative_to(parent)
    except ValueError as exc:
        raise ArtifactPathError(f"HTML path escapes artifact directory: {path}") from exc


def resolve_artifact_html(artifacts_dir: Path, slug: str, html_path: str) -> ArtifactHTML:
    """Resolve and read an HTML file under artifacts/{slug}."""
    artifact_dir = (artifacts_dir / slug).resolve()
    if not artifact_dir.exists() or not artifact_dir.is_dir():
        raise ArtifactHTMLNotFoundError(f"artifact directory does not exist: {artifact_dir}")

    target = (artifact_dir / html_path).resolve()
    _ensure_child_path(target, artifact_dir)
    if not target.exists() or not target.is_file():
        raise ArtifactHTMLNotFoundError(f"HTML file does not exist under {artifact_dir}: {html_path}")

    if target.suffix.lower() not in {".html", ".htm"}:
        raise ArtifactPathError(f"artifact HTML path must end with .html or .htm: {target}")

    return ArtifactHTML(
        slug=slug,
        artifact_dir=artifact_dir,
        html_path=target,
        relative_html_path=str(target.relative_to(artifact_dir)),
        content=target.read_text(encoding="utf-8"),
    )

