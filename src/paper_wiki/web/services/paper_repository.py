from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any

from filelock import FileLock
from pydantic import ValidationError

from paper_wiki.assets.models import AssetsManifest, PaperAssetMeta
from paper_wiki.assets.reader import AssetsReader
from paper_wiki.core.config import Settings, get_settings
from paper_wiki.core.models import PriorWorksDoc
from paper_wiki.core.validation import validate_slug
from paper_wiki.web.mappers import map_paper_meta
from paper_wiki.web.schemas.paper import PaperDetail, PaperListItem

logger = logging.getLogger(__name__)


class PaperRepositoryError(Exception):
    """Base class for repository-level errors surfaced by the web API."""


class PaperNotFoundError(PaperRepositoryError):
    """Raised when a paper artifact cannot be found."""


class PaperConflictError(PaperRepositoryError):
    """Raised when optimistic locking detects a stale update."""


class PaperValidationError(PaperRepositoryError):
    """Raised when a requested paper update fails validation."""


class PaperRepository:
    """Filesystem-backed repository for v1 web paper review workflows."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.assets_reader = AssetsReader(self.settings)

    def list_papers(self, *, reviewed: bool | None = None, query: str | None = None) -> list[PaperListItem]:
        artifacts_dir = self.settings.resolved_artifacts_dir()
        if not artifacts_dir.exists():
            return []

        items: list[PaperListItem] = []
        for manifest_path in sorted(artifacts_dir.glob("*/manifest.json"), key=lambda path: path.parent.name):
            try:
                manifest = self._read_manifest_path(manifest_path)
            except Exception as exc:
                logger.warning("跳过不可读取的 manifest：%s, error=%s", manifest_path, exc)
                continue
            if reviewed is not None and manifest.paper.reviewed is not reviewed:
                continue
            item = self._list_item(manifest, manifest_path.parent)
            if query and not self._matches_query(item, query):
                continue
            items.append(item)
        return items

    def get_paper(self, slug: str) -> PaperDetail:
        validate_slug(slug)
        try:
            bundle = self.assets_reader.load(slug)
        except FileNotFoundError as exc:
            raise PaperNotFoundError(str(exc)) from exc
        except ValueError as exc:
            raise PaperValidationError(str(exc)) from exc

        artifact_dir = bundle.artifact_dir
        return PaperDetail(
            slug=slug,
            updated_at=bundle.manifest.updated_at,
            meta=map_paper_meta(bundle.manifest.paper),
            summary=self._read_optional_text(artifact_dir / "summary.md"),
            prior_works=self._read_optional_json(artifact_dir / "prior_works.json"),
            sci_pattern=self._read_optional_json(artifact_dir / "sci_pattern.json"),
            references_count=len(bundle.references.references),
            figures_count=len(bundle.figures.figures),
            sections_count=len(bundle.sections.sections),
        )

    def update_meta(self, slug: str, patch: dict[str, Any], *, expected_updated_at: str) -> PaperDetail:
        def mutate(manifest: AssetsManifest, artifact_dir: Path) -> None:
            values = manifest.paper.model_dump()
            values.update(patch)
            # `reviewed` is always server-derived from the two sub-flags, never
            # settable directly by the client (see meta_reviewed/prior_works_reviewed).
            values["reviewed"] = bool(values.get("meta_reviewed")) and bool(values.get("prior_works_reviewed"))
            manifest.paper = PaperAssetMeta.model_validate(values)

        self._mutate_manifest(slug, expected_updated_at=expected_updated_at, mutate=mutate)
        return self.get_paper(slug)

    def update_summary(self, slug: str, summary: str, *, expected_updated_at: str) -> PaperDetail:
        def mutate(manifest: AssetsManifest, artifact_dir: Path) -> None:
            self._write_text_atomic(artifact_dir / "summary.md", summary.rstrip() + "\n")

        self._mutate_manifest(slug, expected_updated_at=expected_updated_at, mutate=mutate)
        return self.get_paper(slug)

    def update_prior_works(
        self,
        slug: str,
        prior_works_payload: dict[str, Any],
        *,
        expected_updated_at: str,
    ) -> PaperDetail:
        try:
            doc = PriorWorksDoc.model_validate(prior_works_payload)
        except ValidationError as exc:
            raise PaperValidationError(str(exc)) from exc

        def mutate(manifest: AssetsManifest, artifact_dir: Path) -> None:
            self._write_text_atomic(
                artifact_dir / "prior_works.json",
                doc.model_dump_json(indent=2) + "\n",
            )

        self._mutate_manifest(slug, expected_updated_at=expected_updated_at, mutate=mutate)
        return self.get_paper(slug)

    def mark_blog_html_generated(self, slug: str, html_path: str) -> PaperDetail:
        """Record a successful ``cursor_render.render_blog_html()`` result in manifest.json.

        This runs from a background job after the render succeeds, not from a
        user-editable PATCH endpoint, so unlike update_meta/update_summary/
        update_prior_works it does not take an ``expected_updated_at`` — there is
        no "stale tab" to guard against, it simply wins on write.
        """
        validate_slug(slug)
        artifact_dir = self.settings.resolved_artifacts_dir() / slug
        manifest_path = artifact_dir / "manifest.json"
        if not manifest_path.is_file():
            raise PaperNotFoundError(f"assets manifest does not exist: {manifest_path}")

        lock = FileLock(str(artifact_dir / ".paper-wiki.lock"))
        with lock:
            manifest = self._read_manifest_path(manifest_path)
            try:
                values = manifest.paper.model_dump()
                values["blog_html_path"] = html_path
                values["blog_html_generated_at"] = self._now()
                manifest.paper = PaperAssetMeta.model_validate(values)
            except ValidationError as exc:
                raise PaperValidationError(str(exc)) from exc
            manifest.updated_at = self._now()
            self._write_json_atomic(manifest_path, manifest.model_dump(mode="json"))

        return self.get_paper(slug)

    def resolve_artifact_file(self, slug: str, relative_path: str) -> Path:
        validate_slug(slug)
        clean_path = Path(relative_path)
        if clean_path.is_absolute() or ".." in clean_path.parts or relative_path.strip() in {"", ".", ".."}:
            raise PaperValidationError("file path must be relative and stay inside the artifact directory")

        artifact_dir = (self.settings.resolved_artifacts_dir() / slug).resolve()
        candidates = [(artifact_dir / clean_path).resolve()]
        if clean_path.parts and clean_path.parts[0] == "figures":
            candidates.append((artifact_dir / "assets" / clean_path).resolve())

        for candidate in candidates:
            try:
                candidate.relative_to(artifact_dir)
            except ValueError as exc:
                raise PaperValidationError("file path must stay inside the artifact directory") from exc
            if candidate.is_file():
                return candidate

        raise PaperNotFoundError(f"artifact file does not exist: {relative_path}")

    def _mutate_manifest(self, slug: str, *, expected_updated_at: str, mutate: Any) -> None:
        validate_slug(slug)
        artifact_dir = self.settings.resolved_artifacts_dir() / slug
        manifest_path = artifact_dir / "manifest.json"
        if not manifest_path.is_file():
            raise PaperNotFoundError(f"assets manifest does not exist: {manifest_path}")

        lock = FileLock(str(artifact_dir / ".paper-wiki.lock"))
        with lock:
            try:
                manifest = self._read_manifest_path(manifest_path)
            except ValidationError as exc:
                raise PaperValidationError(str(exc)) from exc
            if manifest.updated_at != expected_updated_at:
                raise PaperConflictError(
                    f"manifest was updated by another writer: expected {expected_updated_at}, "
                    f"actual {manifest.updated_at}"
                )
            try:
                mutate(manifest, artifact_dir)
                manifest.updated_at = self._now()
                self._write_json_atomic(manifest_path, manifest.model_dump(mode="json"))
            except ValidationError as exc:
                raise PaperValidationError(str(exc)) from exc

    def _list_item(self, manifest: AssetsManifest, artifact_dir: Path) -> PaperListItem:
        sci_pattern = self._read_optional_json(artifact_dir / "sci_pattern.json") or {}
        return PaperListItem(
            slug=manifest.slug,
            title=manifest.paper.title or manifest.slug,
            authors=manifest.paper.authors,
            abstract=manifest.paper.abstract,
            year=manifest.paper.year,
            venue=manifest.paper.venue,
            reviewed=manifest.paper.reviewed,
            updated_at=manifest.updated_at,
            has_summary=(artifact_dir / "summary.md").is_file(),
            has_prior_works=(artifact_dir / "prior_works.json").is_file(),
            has_sci_pattern=(artifact_dir / "sci_pattern.json").is_file(),
            primary_pattern=str(sci_pattern.get("primary_pattern") or ""),
            primary_pattern_name=str(sci_pattern.get("primary_pattern_name") or ""),
        )

    def _matches_query(self, item: PaperListItem, query: str) -> bool:
        needle = query.casefold().strip()
        haystack = " ".join(
            [
                item.slug,
                item.title,
                item.abstract,
                item.venue,
                " ".join(item.authors),
                item.primary_pattern,
                item.primary_pattern_name,
            ]
        ).casefold()
        return needle in haystack

    def _read_manifest_path(self, manifest_path: Path) -> AssetsManifest:
        return AssetsManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

    def _read_optional_text(self, path: Path) -> str:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8")

    def _read_optional_json(self, path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_text_atomic(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)

    def _write_json_atomic(self, path: Path, payload: dict[str, Any]) -> None:
        self._write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
