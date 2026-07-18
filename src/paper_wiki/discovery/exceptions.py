from __future__ import annotations


class DiscoveryError(RuntimeError):
    """Base class for user-facing discovery/search failures."""


class ArxivAPIError(DiscoveryError):
    """arXiv returned an error, timed out, or produced an unreadable payload."""


class MainTexNotFoundError(DiscoveryError):
    """A downloaded source archive does not contain a recognizable main tex file."""


class SlugAlreadyExistsError(DiscoveryError):
    """raw/{slug}/ already exists and fetch was not asked to overwrite it."""


class RecommendError(RuntimeError):
    """Base class for user-facing recommendation failures."""


class ZoteroConfigError(RecommendError):
    """Zotero credentials are missing or rejected by the API."""

