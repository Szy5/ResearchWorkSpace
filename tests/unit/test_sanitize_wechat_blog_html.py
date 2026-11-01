from __future__ import annotations

from paper_wiki.publishing.html_processor import sanitize_wechat_blog_html


TOC = """
<section style="max-width:677px;margin:0 auto;">
<section style="margin:0 20px 32px;">
  <section style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;">
    <p><span leaf="">📦 3 Highlights + More</span></p>
    <p><span leaf="">👉 滑动</span></p>
  </section>
  <section style="overflow-x:scroll;-webkit-overflow-scrolling:touch;white-space:nowrap;padding-bottom:8px;">
    <section style="display:inline-block;width:110px;">
      <p><span leaf="">PART 01</span></p>
      <p><span leaf="">三句话看懂</span></p>
    </section>
  </section>
</section>
<section style="margin-top:16px;margin-bottom:32px;padding:0 20px;">
  <section style="display:flex;align-items:center;gap:16px;margin-bottom:24px;">
    <section style="text-align:center;flex-shrink:0;">
      <p><span leaf="">01</span></p>
      <p><span leaf="">PART</span></p>
    </section>
    <section>
      <p><span leaf="">三句话看懂</span></p>
      <p><span leaf="">SNAPSHOT · THREE LINES</span></p>
    </section>
  </section>
  <p><span leaf="">正文段落。</span></p>
</section>
</section>
"""


def test_sanitize_removes_highlights_slider_and_simplifies_part_titles() -> None:
    html = sanitize_wechat_blog_html(TOC)
    assert "Highlights + More" not in html
    assert "👉 滑动" not in html
    assert "overflow-x:scroll" not in html
    assert "PART" not in html
    assert "SNAPSHOT" not in html
    assert "01" in html
    assert "三句话看懂" in html
    assert "正文段落" in html
    assert 'font-size:22px;font-weight:900;color:#059669' in html


def test_sanitize_keeps_plain_html() -> None:
    raw = '<section><p><span leaf="">你好</span></p></section>'
    assert "你好" in sanitize_wechat_blog_html(raw)
