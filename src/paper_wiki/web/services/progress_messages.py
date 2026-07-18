from __future__ import annotations

FALLBACK_MESSAGE = "⚙️ 处理中..."

# Ordered (substring, friendly message) pairs: the first substring found in the
# raw internal log line wins. Order matters where one message is a prefix of
# another concern (e.g. summary/prior_works/sci_pattern all start with "步骤").
_RULES: tuple[tuple[str, str], ...] = (
    ("开始生成每日推荐", "🔍 正在生成今日推荐..."),
    ("正在获取 Zotero 口味语料", "📚 正在读取你的阅读口味..."),
    ("正在拉取 arXiv 候选池", "🌐 正在抓取 arXiv 最新论文..."),
    ("正在计算相似度排序", "🧮 正在计算相似度排序..."),
    ("推荐生成完成", "✅ 推荐生成完成"),
    ("sentence-transformers不可用", "⚠️ 相似度模型不可用，按原始顺序展示"),
    ("开始拉取：arxiv_id=", "📥 正在下载论文源码..."),
    ("已找到主文件，正在下载 PDF", "📄 已找到论文主文件，正在下载 PDF..."),
    ("构建 Layer1 通用 assets", "📄 正在解析论文结构..."),
    ("assets 已存在，复用 assets", "📄 已找到现有论文结构，复用中..."),
    ("生成 summary.md", "📝 正在生成精读摘要..."),
    ("生成 prior_works.json", "🔗 正在分析前序工作..."),
    ("生成 sci_pattern.json", "🏷️ 正在识别科学范式..."),
    ("已将 prior_works", "✨ 正在整合摘要内容..."),
    ("Layer1 语义产物生成完成", "✅ 生成完成"),
    ("正在调用 Cursor 生成博客 HTML", "🎨 正在排版博客 HTML..."),
    ("博客 HTML 生成完成", "✅ 博客 HTML 生成完成"),
)


def translate_progress(raw_message: str) -> str:
    """Map an internal logger message to a short, user-facing icon+text line.

    "正在为候选生成摘要" carries a useful (current/total) count, which is kept
    verbatim instead of being collapsed to a fixed string. Anything else
    unrecognized falls back to a generic message rather than leaking
    developer-facing log text to the UI.
    """
    if "正在为候选生成摘要" in raw_message:
        return f"📝 {raw_message.strip()}..."
    for substring, friendly in _RULES:
        if substring in raw_message:
            return friendly
    return FALLBACK_MESSAGE
