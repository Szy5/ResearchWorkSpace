from pathlib import Path

from PIL import Image

from paper_wiki.publishing.cover_generator import COVER_HEIGHT, COVER_WIDTH, cover_from_figure, generate_wechat_cover


def test_cover_from_figure_fills_wechat_aspect(tmp_path: Path) -> None:
    source = tmp_path / "method.png"
    Image.new("RGB", (1200, 800), (20, 80, 40)).save(source)
    out = tmp_path / "cover.jpg"

    written = cover_from_figure(source, out)

    assert written == out
    with Image.open(out) as img:
        assert img.size == (COVER_WIDTH, COVER_HEIGHT)


def test_generate_wechat_cover_uses_figure_only_when_available(tmp_path: Path) -> None:
    source = tmp_path / "framework.jpg"
    Image.new("RGB", (1600, 900), (180, 40, 40)).save(source)
    out = tmp_path / "cover.jpg"

    generate_wechat_cover("会被忽略的标题", out, figure_path=source)

    with Image.open(out) as img:
        assert img.size == (COVER_WIDTH, COVER_HEIGHT)
        # Full-bleed figure cover should keep the source figure's dominant color.
        r, g, b = img.getpixel((COVER_WIDTH // 2, COVER_HEIGHT // 2))
        assert r > 150 and g < 80 and b < 80
