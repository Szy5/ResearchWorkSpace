from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from paper_wiki.core.config import Settings
from paper_wiki.ingestion.prompt_loader import load_prompt_module, resolve_prompt_path
from paper_wiki.publishing.exceptions import CursorRenderError
from paper_wiki.publishing.html_processor import validate_wechat_html

logger = logging.getLogger(__name__)


def render_blog_html(slug: str, settings: Settings, *, theme: str | None = None) -> Path:
    """读取 artifacts/{slug}/summary.md，调用本机 Cursor 无头模式排版成公众号 HTML。

    Cursor 的 headless agent 自己决定输出文件名，并直接把结果写进 summary.md 所在
    目录（不是通过某个 --output 参数交回路径），所以这里用"调用前后给该目录的 html
    文件拍一次 mtime 快照、取变化最新的那个"来定位产物，而不是假设一个固定文件名。
    """
    artifact_dir = (settings.resolved_artifacts_dir() / slug).resolve()
    summary_path = artifact_dir / "summary.md"
    if not summary_path.is_file():
        raise CursorRenderError(f"summary.md 不存在：{summary_path}")

    resolved_theme = theme or settings.cursor_render_theme
    prompt_path = resolve_prompt_path(settings.resolved_prompts_dir(), settings.cursor_render_prompt_path)
    prompt_vars = load_prompt_module(prompt_path)
    prompt = (
        prompt_vars["blog_html_render_user_prompt"]
        .replace("{THEME}", resolved_theme)
        .replace("{SUMMARY_PATH}", str(summary_path))
    )

    before = _snapshot_html_mtimes(artifact_dir)

    command = [
        settings.cursor_headless_binary,
        "-p",
        "--force",
        "--trust",
        "--workspace",
        str(settings.project_root),
        "--output-format",
        "text",
        prompt,
    ]

    logger.info("正在调用 Cursor 生成博客 HTML")
    try:
        result = subprocess.run(
            command,
            cwd=str(settings.project_root),
            capture_output=True,
            text=True,
            timeout=settings.cursor_headless_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise CursorRenderError(
            f"Cursor 无头模式调用超时（>{settings.cursor_headless_timeout_seconds:.0f}s）"
        ) from exc
    except FileNotFoundError as exc:
        raise CursorRenderError(f"找不到 Cursor 无头模式可执行文件：{settings.cursor_headless_binary}") from exc

    if result.returncode != 0:
        stderr_tail = (result.stderr or result.stdout or "").strip()[-500:]
        raise CursorRenderError(f"Cursor 无头模式调用失败（exit={result.returncode}）：{stderr_tail}")

    after = _snapshot_html_mtimes(artifact_dir)
    html_path = _pick_changed_html(before, after, artifact_dir)
    if html_path is None:
        raise CursorRenderError(f"Cursor 未在 {artifact_dir} 下生成或修改任何 HTML 文件")

    content = html_path.read_text(encoding="utf-8")
    validate_wechat_html(content)

    logger.info("博客 HTML 生成完成")
    return html_path


def _snapshot_html_mtimes(directory: Path) -> dict[str, float]:
    if not directory.is_dir():
        return {}
    return {path.name: path.stat().st_mtime for path in directory.glob("*.html")}


def _pick_changed_html(before: dict[str, float], after: dict[str, float], directory: Path) -> Path | None:
    """Pick the freshly (re)written HTML file that is the actual WeChat-ready fragment.

    Cursor's headless agent can write more than one new/changed .html file in a
    single invocation: alongside the WeChat-ready fragment it sometimes also
    writes a "_预览" local-preview wrapper (a full <html> document with its own
    <script> for a copy-to-clipboard toast, meant for eyeballing in a browser,
    not for publishing). "Most recently modified" alone is not a safe signal —
    in practice the preview file can be written *after* the real one — so
    preview-named and full-document-wrapped candidates are filtered out first.
    """
    changed = [name for name, mtime in after.items() if name not in before or mtime > before[name]]
    candidates = [name for name in changed if "预览" not in name]
    if not candidates:
        candidates = changed
    if not candidates:
        return None

    def _is_full_page_wrapper(name: str) -> bool:
        head = (directory / name).read_text(encoding="utf-8", errors="ignore")[:200].lower()
        return "<!doctype html" in head or "<html" in head

    fragments = [name for name in candidates if not _is_full_page_wrapper(name)]
    if fragments:
        candidates = fragments

    newest = max(candidates, key=lambda name: after[name])
    return directory / newest
