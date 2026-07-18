from __future__ import annotations

from pathlib import Path


def validate_slug(slug: str) -> str:
    """Validate a user-controlled paper slug as one path segment."""
    if Path(slug).name != slug or slug in {"", ".", ".."}:
        raise ValueError("slug must be a single path segment")
    return slug
