from __future__ import annotations


class PublishingError(RuntimeError):
    """Base class for user-facing publishing failures."""


class ArtifactHTMLNotFoundError(PublishingError):
    """Raised when a requested artifact HTML file cannot be found."""


class ArtifactPathError(PublishingError):
    """Raised when a requested artifact path escapes its paper directory."""


class HTMLValidationError(PublishingError):
    """Raised when HTML is unsafe or unsupported for publishing."""


class CursorRenderError(PublishingError):
    """Raised when summary.md is missing, the headless Cursor agent fails, or produces no HTML."""


class WeChatConfigError(PublishingError):
    """Raised when required WeChat configuration is missing."""


class WeChatAPIError(PublishingError):
    """Raised when the WeChat API returns an error payload."""

    def __init__(self, code: int | None, message: str, *, response: dict | None = None) -> None:
        self.code = code
        self.message = message
        self.response = response or {}
        detail = f"WeChat API error"
        if code is not None:
            detail += f" {code}"
        detail += f": {message}"
        super().__init__(detail)

