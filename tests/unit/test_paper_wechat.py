from __future__ import annotations

import json
from pathlib import Path
import time
from unittest.mock import patch

from PIL import Image
import pytest

from paper_wiki.core import progress
from paper_wiki.core.config import Settings
from paper_wiki.ingestion.llm_client import LLMClient
from paper_wiki.publishing.markdown_renderer import render_markdown_for_wechat
from paper_wiki.publishing.math_render import latex_to_inline_html
from paper_wiki.publishing.paper_wechat import (
    adapt_article_for_wechat,
    cjk_char_count,
    lead_figure_caption,
    load_package,
    prepare_paper_wechat,
    publish_paper_wechat,
    strip_appendix,
    strip_formulas,
    update_package_fields,
)
from paper_wiki.publishing.wechat_limits import fit_wechat_length, wechat_length
from paper_wiki.web.services.job_manager import JobManager
from paper_wiki.web.services.progress_messages import ingest_step_specs

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

SUMMARY = r"""# Demo Paper: A Long Original Title

> 一句话导读：本文提出 **Demo** 方法。

## 为什么要关心这个问题

奖励 $R \in \{0,1\}$ 很稀疏，优势 $\hat{A}_i = \frac{r_i - \mu}{\sigma}$。

![方法整体框架](assets/figures/framework.png)

$$
\mathcal{J}(\theta) = \mathbb{E}\left[\sum_t A_t\right]
$$

## 我的判断

- 结论可靠。

## 科学发现范式

- 主要范式：P1

## 先前工作分析

English appendix.
"""


WECHAT_ARTICLE = """# Demo Paper

> **一句话导读**：本文提出 Demo 方法，不写公式也能读懂。

## 研究背景与问题

现有方法奖励稀疏，探索难学。

## 方法要点

作者把探索改成可学习的策略，整体流程见下图。

![方法整体框架](assets/figures/framework.png)

## 实验结果

在基准上 Hit@1 明显提升。

## 科学发现范式

- 主要范式：P1

## 先前工作分析

先前工作指出了奖励稀疏问题，本文据此改进。
"""


class FakeLLM(LLMClient):
    def __init__(
        self,
        payload: dict[str, str] | None = None,
        fail: bool = False,
        *,
        fail_article: bool = False,
        article: str | None = None,
    ) -> None:
        self.payload = payload or {"title": "Demo：一句话说清核心贡献", "digest": "现有方法奖励稀疏，本文用 Demo 解决。"}
        self.fail = fail
        self.fail_article = fail_article
        self.article = article or WECHAT_ARTICLE
        self.calls = 0

    def complete(self, system: str, user: str) -> str:
        self.calls += 1
        if "改写成适合直接发公众号的正文" in system or "不要任何公式" in system:
            if self.fail_article:
                raise RuntimeError("article rewrite failed")
            return self.article
        if self.fail:
            raise RuntimeError("upstream overloaded")
        return json.dumps(self.payload, ensure_ascii=False)


class FakeWeChatClient:
    def __init__(self) -> None:
        self.covers: list[Path] = []
        self.images: list[Path] = []
        self.drafts: list[dict[str, object]] = []

    def upload_permanent_image(self, path: Path) -> str:
        self.covers.append(path)
        return "thumb-id"

    def upload_article_image(self, path: Path) -> str:
        self.images.append(path)
        return f"https://mmbiz.example/{path.name}"

    def create_draft(self, **kwargs: object) -> dict[str, str]:
        self.drafts.append(kwargs)
        return {"media_id": "draft-id"}


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    artifact = tmp_path / "artifacts" / "demo"
    (artifact / "assets" / "figures").mkdir(parents=True)
    (artifact / "summary.md").write_text(SUMMARY, encoding="utf-8")
    Image.new("RGBA", (2400, 900), (10, 120, 90, 255)).save(artifact / "assets" / "figures" / "framework.png")
    return Settings().model_copy(
        update={
            "project_root": tmp_path,
            "artifacts_dir": tmp_path / "artifacts",
            "prompts_dir": PROMPTS_DIR,
            "wechat_appid": "appid",
            "wechat_secret": "secret",
            "wechat_author": "Paper-Wiki",
        }
    )


def test_wechat_length_counts_like_the_editor() -> None:
    assert wechat_length("中文") == 2
    assert wechat_length("abcd") == 2
    trimmed = fit_wechat_length("测" * 40, 32)
    assert wechat_length(trimmed) <= 32
    assert trimmed.endswith("…")


def test_inline_math_converts_simple_and_defers_complex() -> None:
    html = latex_to_inline_html(r"e_t \in \mathcal{E}")
    assert html is not None and "<sub" in html and "∈" in html
    assert latex_to_inline_html(r"\frac{a}{b}") is None


def test_renderer_turns_math_into_text_and_images(tmp_path: Path) -> None:
    rendered = render_markdown_for_wechat(
        "# T\n\n## A\n\n值 $x_t$ 与 $\\frac{a}{b}$。\n\n$$\\sum_i x_i$$\n",
        asset_dir=tmp_path,
    )
    assert "$" not in rendered.html
    assert "PWMATH" not in rendered.html
    assert len(list((tmp_path / "formulas").glob("*.png"))) == 2
    assert "点赞" not in rendered.html


def test_strip_appendix_removes_knowledge_base_sections() -> None:
    stripped = strip_appendix(SUMMARY)
    assert "科学发现范式" not in stripped
    assert "English appendix" not in stripped
    assert "我的判断" in stripped


def _fake_cursor_render(markdown_path, settings, *, theme=None, preferred_name=None):
    """Deterministic stand-in for Cursor headless + gzh-design."""
    text = markdown_path.read_text(encoding="utf-8")
    parts = ['<section class="paper-wiki">']
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("![") and "](" in stripped:
            alt = stripped[2 : stripped.index("](")]
            src = stripped[stripped.index("](") + 2 : -1]
            parts.append(f'<p><img src="{src}" alt="{alt}"></p>')
        elif stripped.startswith("**标题**"):
            parts.append("<p><span>>标题<</span></p><p>" + stripped + "</p>")
        elif stripped:
            parts.append(f"<p>{stripped}</p>")
    parts.append("</section>")
    target = markdown_path.parent / (preferred_name or "article.html")
    target.write_text("\n".join(parts), encoding="utf-8")
    return target


def test_prepare_builds_package_with_llm_headline(settings: Settings) -> None:
    llm = FakeLLM()
    with patch("paper_wiki.publishing.paper_wechat.render_markdown_html", side_effect=_fake_cursor_render):
        package = prepare_paper_wechat(settings, "demo", llm=llm)

    out = settings.resolved_artifacts_dir() / "demo" / "wechat"
    assert llm.calls == 1  # headline only; body comes from summary.md
    assert package.title == "Demo：一句话说清核心贡献"
    assert package.image_count == 1
    assert package.formula_count == 0
    assert package.cover_figure == "images/01_framework.jpg"
    assert (out / "cover.jpg").stat().st_size > 1000
    assert (out / "article.md").is_file()
    image = out / "images" / "01_framework.jpg"
    assert image.stat().st_size < 1024 * 1024
    with Image.open(image) as img:
        assert img.width <= 1280
    html = (out / "article.html").read_text(encoding="utf-8")
    assert 'src="images/01_framework.jpg"' in html
    assert "科学发现范式" in html
    assert "$" not in (out / "article.md").read_text(encoding="utf-8")
    assert "**标题**" in (out / "article.md").read_text(encoding="utf-8")
    assert html.index("01_framework.jpg") < html.index(">标题<")
    # Lead figure is a copy; the method section still keeps its own figure.
    assert html.count("01_framework.jpg") == 2
    assert load_package(settings, "demo") == package


def test_prepare_falls_back_when_llm_fails(settings: Settings) -> None:
    with patch("paper_wiki.publishing.paper_wechat.render_markdown_html", side_effect=_fake_cursor_render):
        package = prepare_paper_wechat(settings, "demo", llm=FakeLLM(fail=True))
    assert package.title.startswith("demo") or package.title.startswith("Demo")
    assert package.digest.startswith("本文提出")
    assert any("回退" in warning for warning in package.warnings)


def test_manual_title_skips_headline_llm_and_keeps_figure_cover(settings: Settings) -> None:
    llm = FakeLLM()
    with patch("paper_wiki.publishing.paper_wechat.render_markdown_html", side_effect=_fake_cursor_render):
        package = prepare_paper_wechat(settings, "demo", title="手动标题", digest="手动摘要", llm=llm)
    assert llm.calls == 0  # headline skipped; no article rewrite LLM
    assert package.cover_figure is not None
    cover = settings.resolved_artifacts_dir() / "demo" / "wechat" / "cover.jpg"
    before = cover.read_bytes()
    updated = update_package_fields(settings, "demo", title="另一个标题")
    assert updated.title == "另一个标题"
    # Method-figure covers ignore title edits.
    assert cover.read_bytes() == before


def test_prepare_skips_headline_llm_when_reusing(settings: Settings) -> None:
    first = FakeLLM()
    with patch("paper_wiki.publishing.paper_wechat.render_markdown_html", side_effect=_fake_cursor_render):
        prepare_paper_wechat(settings, "demo", title="手动标题", digest="手动摘要", llm=first)
        second = FakeLLM()
        prepare_paper_wechat(
            settings,
            "demo",
            title="手动标题",
            digest="手动摘要",
            regenerate_headline=False,
            llm=second,
        )
    assert second.calls == 0
    assert (settings.resolved_artifacts_dir() / "demo" / "wechat" / "article.md").is_file()


def test_publish_uploads_assets_and_records_draft(settings: Settings) -> None:
    with patch("paper_wiki.publishing.paper_wechat.render_markdown_html", side_effect=_fake_cursor_render):
        prepare_paper_wechat(settings, "demo", llm=FakeLLM())
    client = FakeWeChatClient()

    package = publish_paper_wechat(settings, "demo", client=client)  # type: ignore[arg-type]

    assert package.draft_media_id == "draft-id"
    assert client.covers[0].name == "cover.jpg"
    assert len(client.images) == 1 + package.formula_count
    draft = client.drafts[0]
    assert draft["title"] == "Demo：一句话说清核心贡献"
    assert draft["author"] == "Paper-Wiki"
    assert "https://mmbiz.example/01_framework.jpg" in str(draft["content"])


def _wait(manager: JobManager, job_id: str):
    for _ in range(200):
        job = manager.get(job_id)
        if job.status in {"succeeded", "failed"}:
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_job_manager_records_structured_steps() -> None:
    manager = JobManager()

    def task() -> str:
        progress.plan([progress.StepSpec("a", "第一步"), progress.StepSpec("b", "第二步", external="LLM")])
        with progress.step("a"):
            progress.detail("1/2")
        progress.skip("b", "不需要")
        return "ok"

    job = _wait(manager, manager.submit(slug="demo", target="test", task=task).job_id)
    assert [(step.key, step.status) for step in job.steps] == [("a", "succeeded"), ("b", "skipped")]
    assert job.steps[0].detail == "1/2"
    assert job.steps[1].external == "LLM"


def test_job_manager_marks_failed_step() -> None:
    manager = JobManager()

    def task() -> None:
        with progress.step("upload", "上传", external="微信 API"):
            raise RuntimeError("40164 ip not in whitelist")

    job = _wait(manager, manager.submit(slug="demo", target="test", task=task).job_id)
    assert job.status == "failed"
    assert job.steps[0].status == "failed"
    assert "40164" in (job.steps[0].detail or "")


def test_ingest_steps_advance_from_pipeline_logs() -> None:
    import logging

    manager = JobManager()
    logger = logging.getLogger("paper_wiki.ingestion.pipeline")

    def task() -> None:
        logger.info("构建 Layer1 通用 assets：demo")
        logger.info("步骤：生成 summary.md")

    job = _wait(manager, manager.submit(slug="demo", target="ingest", task=task, steps=ingest_step_specs(["summary"])).job_id)
    statuses = {step.key: step.status for step in job.steps}
    assert statuses == {"assets": "succeeded", "summary": "succeeded", "merge": "skipped"}


def test_latex_people_extraction_handles_multiline_authors_and_affiliations() -> None:
    import paper_wiki.assets  # noqa: F401  (import order avoids a parser/assets cycle)
    from paper_wiki.ingestion.latex_parser import LaTeXParser

    text = r"""
\author{
Yanning Hou\equalcontrib,
Haoyuan Chen\equalcontrib,
Sihang Zhou\corresponding,\\
Xiaoshu Chen
}
\affiliations{
National University of Defense Technology\\
Changsha, China
}
"""
    parser = LaTeXParser()
    assert parser._extract_authors(text) == ["Yanning Hou", "Haoyuan Chen", "Sihang Zhou", "Xiaoshu Chen"]
    assert parser._extract_affiliations(text) == ["National University of Defense Technology"]

    inline = r"""
\author{\textbf{Jinhao Jiang\textsuperscript{1}, Kun Zhou\textsuperscript{2}}\\
\textsuperscript{1}Gaoling School of Artificial Intelligence, Renmin University of China\\
\texttt{a@b.cn}}
"""
    assert parser._extract_authors(inline) == ["Jinhao Jiang", "Kun Zhou"]
    assert parser._extract_affiliations(inline) == ["Gaoling School of Artificial Intelligence, Renmin University of China"]


def test_wechat_ip_whitelist_error_names_current_ip() -> None:
    from paper_wiki.publishing.exceptions import WeChatAPIError

    error = WeChatAPIError(40164, "invalid ip 106.39.130.54 ipv6 ::ffff:106.39.130.54, not in whitelist")
    assert "106.39.130.54" in str(error)
    assert "WECHAT_PROXY" in str(error)


def test_lead_figure_caption_keeps_body_figure() -> None:
    article = (
        "# T\n\n如图 1 与图 2 所示。\n\n![图 1：问题诊断](images/02_diag.jpg)\n\n"
        "![图 2：整体框架](images/01_framework.jpg)\n\n下一段，见图 3。\n\n![图 3：主结果](images/03_res.jpg)\n"
    )

    caption = lead_figure_caption(article, "images/01_framework.jpg")

    assert caption == "图 2：整体框架"
    assert "![图 2：整体框架](images/01_framework.jpg)" in article
    assert "如图 1 与图 2 所示。" in article


def test_lead_figure_caption_handles_old_caption_line() -> None:
    article = "正文。\n\n![](images/01_model.jpg)\n*图：KG-Agent 概览。*\n\n下一段。\n"

    assert lead_figure_caption(article, "images/01_model.jpg") == "KG-Agent 概览。"
    assert "![](images/01_model.jpg)" in article
    assert "*图：KG-Agent 概览。*" in article



def test_strip_formulas_removes_latex() -> None:
    text = "奖励 $R_S$ 与\n\n$$\\mathcal{J}(\\theta)$$\n\n结束。"
    cleaned = strip_formulas(text)
    assert "$" not in cleaned
    assert "R_S" in cleaned
    assert "结束" in cleaned


def test_adapt_article_for_wechat_strips_formulas(settings: Settings) -> None:
    llm = FakeLLM(article="# T\n\n值 $x_t$ 很大。\n\n![图](assets/figures/framework.png)\n")
    out = adapt_article_for_wechat(settings, llm, article=SUMMARY, title="Demo")
    assert "$" not in out
    assert "framework.png" in out
    assert cjk_char_count(out) >= 1
