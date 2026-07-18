from __future__ import annotations

from pathlib import Path

import pytest

from paper_wiki.publishing.artifact_html import resolve_artifact_html
from paper_wiki.publishing.exceptions import ArtifactHTMLNotFoundError, ArtifactPathError, HTMLValidationError
from paper_wiki.publishing.html_processor import replace_local_images, validate_wechat_html
from paper_wiki.publishing.models import WeChatDraftOptions
from paper_wiki.publishing.wechat_client import WeChatClient
from paper_wiki.publishing.wechat_publisher import publish_artifact_html_to_wechat


class FakeSettings:
    def __init__(self, root: Path) -> None:
        self.project_root = root
        self.wechat_appid = "appid"
        self.wechat_secret = "secret"
        self.wechat_author = "Paper-Wiki"
        self.wechat_cover_path = None
        self.wechat_thumb_media_id = None
        self.wechat_request_timeout_seconds = 3.0

    def resolved_artifacts_dir(self) -> Path:
        return self.project_root / "artifacts"


class FakeWeChatClient:
    def __init__(self) -> None:
        self.cover_paths: list[Path] = []
        self.article_image_paths: list[Path] = []
        self.drafts: list[dict[str, str | None]] = []

    def upload_permanent_image(self, image_path: Path) -> str:
        self.cover_paths.append(image_path)
        return "cover-media-id"

    def upload_article_image(self, image_path: Path) -> str:
        self.article_image_paths.append(image_path)
        return f"https://mmbiz.example/{image_path.name}"

    def create_draft(
        self,
        *,
        title: str,
        content: str,
        thumb_media_id: str,
        author: str | None = None,
        digest: str | None = None,
    ) -> dict[str, str]:
        self.drafts.append(
            {
                "title": title,
                "content": content,
                "thumb_media_id": thumb_media_id,
                "author": author,
                "digest": digest,
            }
        )
        return {"media_id": "draft-media-id"}


class FakeResponse:
    status_code = 200

    def __init__(self, payload: dict[str, str]) -> None:
        self.payload = payload

    def json(self) -> dict[str, str]:
        return self.payload


class RecordingSession:
    def __init__(self) -> None:
        self.posts: list[dict[str, object]] = []

    def get(self, *args: object, **kwargs: object) -> FakeResponse:
        return FakeResponse({"access_token": "token"})

    def post(self, *args: object, **kwargs: object) -> FakeResponse:
        self.posts.append({"args": args, "kwargs": kwargs})
        return FakeResponse({"media_id": "draft-media-id"})


def test_resolve_artifact_html_reads_file(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "GraphWalker"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "article.html").write_text("<section>ok</section>", encoding="utf-8")

    artifact = resolve_artifact_html(tmp_path / "artifacts", "GraphWalker", "article.html")

    assert artifact.slug == "GraphWalker"
    assert artifact.relative_html_path == "article.html"
    assert artifact.content == "<section>ok</section>"


def test_resolve_artifact_html_rejects_missing_file(tmp_path: Path) -> None:
    (tmp_path / "artifacts" / "GraphWalker").mkdir(parents=True)

    with pytest.raises(ArtifactHTMLNotFoundError):
        resolve_artifact_html(tmp_path / "artifacts", "GraphWalker", "missing.html")


def test_resolve_artifact_html_rejects_path_escape(tmp_path: Path) -> None:
    (tmp_path / "artifacts" / "GraphWalker").mkdir(parents=True)

    with pytest.raises(ArtifactPathError):
        resolve_artifact_html(tmp_path / "artifacts", "GraphWalker", "../outside.html")


def test_replace_local_images_uploads_and_rewrites_src(tmp_path: Path) -> None:
    html_file = tmp_path / "article.html"
    image_path = tmp_path / "figures" / "demo.jpg"
    image_path.parent.mkdir()
    image_path.write_bytes(b"fake image")
    html_file.write_text(
        '<section><img src="figures/demo.jpg"><img src="https://example.com/remote.jpg"></section>',
        encoding="utf-8",
    )
    uploads: list[Path] = []

    processed = replace_local_images(
        html_file.read_text(encoding="utf-8"),
        html_file=html_file,
        upload_image=lambda path: uploads.append(path) or "https://mmbiz.example/demo.jpg",
    )

    assert uploads == [image_path.resolve()]
    assert processed.uploaded_image_count == 1
    assert 'src="https://mmbiz.example/demo.jpg"' in processed.content
    assert 'src="https://example.com/remote.jpg"' in processed.content


def test_validate_wechat_html_rejects_script() -> None:
    with pytest.raises(HTMLValidationError):
        validate_wechat_html("<section>ok</section><script>alert(1)</script>")


def test_publish_artifact_html_to_wechat_uses_env_settings_and_creates_draft(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts" / "GraphWalker"
    figures_dir = artifact_dir / "figures"
    figures_dir.mkdir(parents=True)
    (artifact_dir / "article.html").write_text('<section><img src="figures/demo.jpg"></section>', encoding="utf-8")
    (figures_dir / "demo.jpg").write_bytes(b"article image")
    (figures_dir / "cover.jpg").write_bytes(b"cover image")
    client = FakeWeChatClient()

    result = publish_artifact_html_to_wechat(
        FakeSettings(tmp_path),
        WeChatDraftOptions(
            slug="GraphWalker",
            html_path="article.html",
            title="GraphWalker 论文精读",
            cover_path=Path("figures/cover.jpg"),
            save_rendered=True,
        ),
        client=client,  # type: ignore[arg-type]
    )

    assert result.media_id == "draft-media-id"
    assert result.thumb_media_id == "cover-media-id"
    assert result.uploaded_image_count == 1
    assert result.rendered_html_path is not None
    assert result.rendered_html_path.exists()
    assert client.cover_paths == [(figures_dir / "cover.jpg").resolve()]
    assert client.article_image_paths == [(figures_dir / "demo.jpg").resolve()]
    assert client.drafts[0]["title"] == "GraphWalker 论文精读"
    assert client.drafts[0]["author"] == "Paper-Wiki"
    assert "https://mmbiz.example/demo.jpg" in str(client.drafts[0]["content"])


def test_wechat_create_draft_sends_utf8_json_without_ascii_escaping() -> None:
    session = RecordingSession()
    client = WeChatClient("appid", "secret", session=session)  # type: ignore[arg-type]

    client.create_draft(
        title="GraphWalker 论文精读",
        content="<section>中文正文</section>",
        thumb_media_id="thumb",
        author="作者",
        digest="摘要",
    )

    assert len(session.posts) == 1
    kwargs = session.posts[0]["kwargs"]
    data = kwargs["data"]
    assert isinstance(data, bytes)
    assert b"\\u4e2d" not in data
    decoded = data.decode("utf-8")
    assert "中文正文" in decoded
    assert "GraphWalker 论文精读" in decoded
    assert kwargs["headers"] == {"Content-Type": "application/json; charset=utf-8"}
