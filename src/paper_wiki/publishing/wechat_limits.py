"""Length limits of WeChat draft fields, counted the way the WeChat editor does.

The editor counts a CJK / full-width character as 1, a half-width (ASCII)
character as 0.5 and a supplementary-plane character (emoji) as 2.
"""

from __future__ import annotations

TITLE_LIMIT = 32
DIGEST_LIMIT = 120
AUTHOR_LIMIT = 8


def _char_weight(char: str) -> float:
    code = ord(char)
    if code > 0xFFFF:
        return 2.0
    if code < 0x80 or 0xFF61 <= code <= 0xFF9F:
        return 0.5
    return 1.0


def wechat_length(text: str) -> float:
    return sum(_char_weight(char) for char in text)


def fit_wechat_length(text: str, limit: float, *, ellipsis: str = "…") -> str:
    """Collapse whitespace and trim to ``limit`` editor characters."""
    clean = " ".join((text or "").split())
    if wechat_length(clean) <= limit:
        return clean
    budget = limit - wechat_length(ellipsis)
    out: list[str] = []
    used = 0.0
    for char in clean:
        weight = _char_weight(char)
        if used + weight > budget:
            break
        out.append(char)
        used += weight
    return "".join(out).rstrip(" ,，、:：;；-—") + ellipsis
