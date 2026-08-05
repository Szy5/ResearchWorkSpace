from __future__ import annotations

from bs4 import BeautifulSoup

from paper_wiki.publishing.html_processor import validate_wechat_html
from paper_wiki.publishing.markdown_renderer import render_markdown_for_wechat


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
    assert "PART 01" in rendered.html
    assert "print" in rendered.html
    assert all(not text.strip() for text in soup.find_all(string=True) if text.parent and text.parent.name not in {"span"})


def test_markdown_renderer_drops_unsafe_raw_html() -> None:
    rendered = render_markdown_for_wechat(
        "# Safe\n\n<script>alert(1)</script>\n\n![unsafe](../secret.png)\n\nText"
    )
    assert "script" not in rendered.html.lower()
    assert "alert" not in rendered.html.lower()
    assert "secret.png" not in rendered.html
