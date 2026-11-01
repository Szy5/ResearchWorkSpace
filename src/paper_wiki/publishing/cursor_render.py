from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from paper_wiki.core.config import Settings
from paper_wiki.ingestion.prompt_loader import load_prompt_module, resolve_prompt_path
from paper_wiki.publishing.exceptions import CursorRenderError
from paper_wiki.publishing.html_processor import sanitize_wechat_blog_html, validate_wechat_html

logger = logging.getLogger(__name__)


def _cursor_subprocess_env(settings: Settings) -> dict[str, str]:
    """Build env for ``agent -p``. Headless print mode needs CURSOR_API_KEY."""
    env = {key: value for key, value in os.environ.items() if value is not None}
    key = (settings.cursor_api_key or env.get("CURSOR_API_KEY") or "").strip()
    if key:
        env["CURSOR_API_KEY"] = key
    return env


def render_blog_html(slug: str, settings: Settings, *, theme: str | None = None) -> Path:
    """读取 artifacts/{slug}/summary.md，调用本机 Cursor 无头模式排版成公众号 HTML。"""
    artifact_dir = (settings.resolved_artifacts_dir() / slug).resolve()
    summary_path = artifact_dir / "summary.md"
    if not summary_path.is_file():
        raise CursorRenderError(f"summary.md 不存在：{summary_path}")
    return render_markdown_html(summary_path, settings, theme=theme)


def render_markdown_html(
    markdown_path: Path,
    settings: Settings,
    *,
    theme: str | None = None,
    preferred_name: str | None = None,
) -> Path:
    """Call Cursor headless to typeset a Markdown file into WeChat-ready HTML.

    Cursor's headless agent decides the output filename and writes into the Markdown
    file's directory, so this snapshots ``*.html`` mtimes before/after the call and
    picks the freshly changed WeChat fragment. When ``preferred_name`` is set and the
    chosen file differs, the content is copied to that name in the same directory.
    """
    markdown_path = markdown_path.resolve()
    if not markdown_path.is_file():
        raise CursorRenderError(f"Markdown 不存在：{markdown_path}")
    output_dir = markdown_path.parent

    resolved_theme = theme or settings.cursor_render_theme
    prompt_path = resolve_prompt_path(settings.resolved_prompts_dir(), settings.cursor_render_prompt_path)
    prompt_vars = load_prompt_module(prompt_path)
    prompt = (
        prompt_vars["blog_html_render_user_prompt"]
        .replace("{THEME}", resolved_theme)
        .replace("{SUMMARY_PATH}", str(markdown_path))
        .replace("{MARKDOWN_PATH}", str(markdown_path))
    )

    before = _snapshot_html_mtimes(output_dir)

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

    env = _cursor_subprocess_env(settings)
    if not env.get("CURSOR_API_KEY"):
        raise CursorRenderError(
            "缺少 CURSOR_API_KEY：无头排版（agent -p）不接受浏览器 login 态。"
            "请到 https://cursor.com/dashboard 创建 API Key，写入项目 .env 的 CURSOR_API_KEY=... 后重新部署。"
        )

    logger.info("正在调用 Cursor 排版 HTML：%s", markdown_path)
    try:
        result = subprocess.run(
            command,
            cwd=str(settings.project_root),
            capture_output=True,
            text=True,
            timeout=settings.cursor_headless_timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise CursorRenderError(
            f"Cursor 无头模式调用超时（>{settings.cursor_headless_timeout_seconds:.0f}s）"
        ) from exc
    except FileNotFoundError as exc:
        raise CursorRenderError(f"找不到 Cursor 无头模式可执行文件：{settings.cursor_headless_binary}") from exc

    if result.returncode != 0:
        stderr_tail = (result.stderr or result.stdout or "").strip()[-500:]
        hint = ""
        if "Authentication required" in stderr_tail or "login" in stderr_tail.lower():
            hint = "（请检查 .env 中 CURSOR_API_KEY 是否有效，改完后需重新部署 web 服务）"
        raise CursorRenderError(f"Cursor 无头模式调用失败（exit={result.returncode}）：{stderr_tail}{hint}")

    after = _snapshot_html_mtimes(output_dir)
    html_path = _pick_changed_html(before, after, output_dir)
    if html_path is None:
        raise CursorRenderError(f"Cursor 未在 {output_dir} 下生成或修改任何 HTML 文件")

    content = sanitize_wechat_blog_html(html_path.read_text(encoding="utf-8"))
    validate_wechat_html(content)
    html_path.write_text(content, encoding="utf-8")

    if preferred_name and html_path.name != preferred_name:
        target = output_dir / preferred_name
        if html_path.resolve() != target.resolve():
            shutil.copyfile(html_path, target)
        html_path = target
        html_path.write_text(content, encoding="utf-8")

    logger.info("博客 HTML 生成完成：%s", html_path)
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
