from __future__ import annotations

import re


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


_WECHAT_ERROR_HINTS = {
    40001: "AppSecret 错误或 access_token 失效，请检查 WECHAT_SECRET",
    40013: "AppID 无效，请检查 WECHAT_APPID",
    40164: "调用方 IP 不在公众号 IP 白名单内，请在公众号后台「设置与开发 → 基本配置」添加服务器出口 IP",
    40007: "封面素材 media_id 无效",
    40005: "图片格式不受支持",
    40009: "图片超过大小限制（正文图片需小于 1MB）",
    45003: "标题超过长度限制（不超过 32 个字）",
    45004: "摘要超过长度限制（不超过 120 个字）",
    45110: "作者名超过长度限制（不超过 8 个字）",
    45009: "接口调用次数已达今日上限",
    48001: "公众号未获得该接口权限",
}


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
        hint = _WECHAT_ERROR_HINTS.get(code) if code is not None else None
        if code == 40164:
            ip = re.search(r"invalid ip (\S+)", message)
            hint = (
                f"当前出口 IP {ip.group(1) if ip else '未知'} 不在公众号 IP 白名单内。请在公众号后台"
                "「设置与开发 → 基本配置 → IP 白名单」加入该 IP；若出口 IP 经常变化，可在 .env 设置 "
                "WECHAT_PROXY 让微信请求走固定 IP 的代理"
            )
        if hint:
            detail = f"{hint}（{detail}）"
        super().__init__(detail)

