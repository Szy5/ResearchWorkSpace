from __future__ import annotations

from bs4 import BeautifulSoup

from paper_wiki.publishing.html_processor import validate_wechat_html
from paper_wiki.publishing.markdown_renderer import paper_info_card, render_markdown_for_wechat


def test_markdown_renderer_creates_wechat_compatible_fragment() -> None:
    rendered = render_markdown_for_wechat(
        """
# Demo Article

Intro with **important text** and `inline_code`.

## First Part

> A useful quote.

![Demo image](demo.png)

```python
print("hello")
```

## Second Part

1. One
2. Two
""".strip()
    )

    validate_wechat_html(rendered.html)
    soup = BeautifulSoup(rendered.html, "html.parser")
    assert rendered.title == "Demo Article"
    assert soup.find("html") is None
    assert soup.find("script") is None
    assert soup.find(attrs={"class": True}) is None
    assert soup.find("img", src="demo.png") is not None
    assert "PART" not in rendered.html
    assert soup.find("ol") is not None
    assert "print" in rendered.html
    assert all(not text.strip() for text in soup.find_all(string=True) if text.parent and text.parent.name not in {"span"})


def test_markdown_renderer_drops_unsafe_raw_html() -> None:
    rendered = render_markdown_for_wechat(
        "# Safe\n\n<script>alert(1)</script>\n\n![unsafe](../secret.png)\n\nText"
    )
    assert "script" not in rendered.html.lower()
    assert "alert" not in rendered.html.lower()
    assert "secret.png" not in rendered.html


def test_markdown_renderer_nests_two_space_lists_and_strips_heading_numbers() -> None:
    rendered = render_markdown_for_wechat(
        "# T\n\n## 1. 问题背景\n\n- 外层\n  - 内层 A\n  - 内层 B\n- 外层二\n\n## 2025 年的新基准\n\n正文"
    )
    soup = BeautifulSoup(rendered.html, "html.parser")
    outer = soup.find("ul")
    assert outer is not None
    assert len(outer.find_all("li", recursive=False)) == 2
    assert outer.find("ul") is not None
    assert "1. 问题背景" not in rendered.html
    assert "问题背景" in rendered.html
    assert "2025 年的新基准" in rendered.html
    assert "•" not in rendered.html


def test_paper_info_card_lists_authors_and_affiliations() -> None:
    html = paper_info_card(
        title="Harness-G",
        authors=["Yanning Hou", "Haoyuan Chen"],
        affiliations=["National University of Defense Technology", "Peking University"],
        arxiv_id="2607.27652",
    )
    text = BeautifulSoup(html, "html.parser").get_text("\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    assert lines[:4] == ["标题", "Harness-G", "作者", "Yanning Hou, Haoyuan Chen"]
    assert lines[4:7] == ["单位", "1. National University of Defense Technology", "2. Peking University"]
    assert "·" not in html


def test_markdown_renderer_keeps_image_followed_by_caption_line() -> None:
    html = render_markdown_for_wechat("正文。\n\n![](images/01_model.jpg)\n*图：KG-Agent 概览。*\n\n下一段。").html

    assert 'src="images/01_model.jpg"' in html
    assert "KG-Agent 概览" in html
    assert html.index("01_model.jpg") < html.index("KG-Agent 概览")
