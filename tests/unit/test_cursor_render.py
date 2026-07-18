from __future__ import annotations

from pathlib import Path
import subprocess
from unittest.mock import patch

import pytest

from paper_wiki.publishing.cursor_render import render_blog_html
from paper_wiki.publishing.exceptions import CursorRenderError, HTMLValidationError


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.project_root = root
        self.cursor_headless_binary = "agent"
        self.cursor_headless_timeout_seconds = 5.0
        self.cursor_render_theme = "摸鱼绿"
        self.cursor_render_prompt_path = "blog_html_render_v1.py"

    def resolved_artifacts_dir(self) -> Path:
        return self.project_root / "artifacts"

    def resolved_prompts_dir(self) -> Path:
        return self.project_root / "prompts"


def _make_settings(tmp_path: Path) -> FakeSettings:
    prompts_dir = tmp_path / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "blog_html_render_v1.py").write_text(
        'blog_html_render_user_prompt = "用{THEME}把 {SUMMARY_PATH} 排版。"',
        encoding="utf-8",
    )
    return FakeSettings(tmp_path)


def _make_summary(tmp_path: Path, slug: str = "Demo") -> Path:
    artifact_dir = tmp_path / "artifacts" / slug
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "summary.md").write_text("# Demo\n\nContent", encoding="utf-8")
    return artifact_dir


def test_render_blog_html_missing_summary_raises(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    (tmp_path / "artifacts" / "Demo").mkdir(parents=True)

    with pytest.raises(CursorRenderError, match="summary.md"):
        render_blog_html("Demo", settings)


def test_render_blog_html_success_picks_new_html_file(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    artifact_dir = _make_summary(tmp_path)

    def fake_run(command, **kwargs):
        (artifact_dir / "summary.html").write_text("<section>ok</section>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    with patch("paper_wiki.publishing.cursor_render.subprocess.run", side_effect=fake_run) as mock_run:
        result = render_blog_html("Demo", settings, theme="摸鱼绿")

    assert result == artifact_dir / "summary.html"
    assert result.read_text(encoding="utf-8") == "<section>ok</section>"

    command = mock_run.call_args.args[0]
    assert command[0] == "agent"
    assert command[1:7] == ["-p", "--force", "--trust", "--workspace", str(tmp_path), "--output-format"]
    assert command[7] == "text"
    prompt_arg = command[8]
    assert "摸鱼绿" in prompt_arg
    assert str(artifact_dir / "summary.md") in prompt_arg


def test_render_blog_html_nonzero_exit_raises(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    _make_summary(tmp_path)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="boom")

    with patch("paper_wiki.publishing.cursor_render.subprocess.run", side_effect=fake_run):
        with pytest.raises(CursorRenderError, match="boom"):
            render_blog_html("Demo", settings)


def test_render_blog_html_timeout_raises(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    _make_summary(tmp_path)

    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout", 5.0))

    with patch("paper_wiki.publishing.cursor_render.subprocess.run", side_effect=fake_run):
        with pytest.raises(CursorRenderError, match="超时"):
            render_blog_html("Demo", settings)


def test_render_blog_html_missing_binary_raises(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    _make_summary(tmp_path)

    def fake_run(command, **kwargs):
        raise FileNotFoundError("agent not found")

    with patch("paper_wiki.publishing.cursor_render.subprocess.run", side_effect=fake_run):
        with pytest.raises(CursorRenderError, match="agent"):
            render_blog_html("Demo", settings)


def test_render_blog_html_no_new_file_raises(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    _make_summary(tmp_path)

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    with patch("paper_wiki.publishing.cursor_render.subprocess.run", side_effect=fake_run):
        with pytest.raises(CursorRenderError, match="未在"):
            render_blog_html("Demo", settings)


def test_render_blog_html_rejects_script_tag(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    artifact_dir = _make_summary(tmp_path)

    def fake_run(command, **kwargs):
        (artifact_dir / "summary.html").write_text("<script>alert(1)</script>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    with patch("paper_wiki.publishing.cursor_render.subprocess.run", side_effect=fake_run):
        with pytest.raises(HTMLValidationError):
            render_blog_html("Demo", settings)


def test_render_blog_html_skips_preview_wrapper_with_script(tmp_path: Path) -> None:
    """Regression test for a real-world observation: Cursor's agent sometimes writes
    both `{name}.html` (the clean WeChat-ready fragment) and a `{name}_预览.html`
    local-preview wrapper (a full <html> document with its own <script> toast helper)
    in the same run, with the preview file modified *last*. Picking "most recently
    changed" naively grabbed the preview file and failed validation on its <script>.
    """
    settings = _make_settings(tmp_path)
    artifact_dir = _make_summary(tmp_path)

    def fake_run(command, **kwargs):
        (artifact_dir / "summary_排版_摸鱼绿(moyu-green).html").write_text(
            "<section>clean fragment</section>", encoding="utf-8"
        )
        (artifact_dir / "summary_排版_摸鱼绿(moyu-green)_预览.html").write_text(
            "<!DOCTYPE html><html><body><script>console.log('toast')</script></body></html>",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    with patch("paper_wiki.publishing.cursor_render.subprocess.run", side_effect=fake_run):
        result = render_blog_html("Demo", settings)

    assert result.name == "summary_排版_摸鱼绿(moyu-green).html"
    assert result.read_text(encoding="utf-8") == "<section>clean fragment</section>"


def test_render_blog_html_picks_most_recently_changed_file(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    artifact_dir = _make_summary(tmp_path)
    (artifact_dir / "old.html").write_text("<section>stale</section>", encoding="utf-8")

    def fake_run(command, **kwargs):
        (artifact_dir / "new.html").write_text("<section>fresh</section>", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    with patch("paper_wiki.publishing.cursor_render.subprocess.run", side_effect=fake_run):
        result = render_blog_html("Demo", settings)

    assert result == artifact_dir / "new.html"
