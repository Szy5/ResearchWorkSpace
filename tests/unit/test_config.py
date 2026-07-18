from pathlib import Path

from paper_wiki.core.config import Settings, find_project_root


def test_settings_loads_dotenv_regardless_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WECHAT_COVER_PATH", raising=False)

    settings = Settings()

    assert settings.wechat_cover_path == Path("static/wechat_default_cover.png")


def test_find_project_root_falls_back_when_cwd_has_no_markers(tmp_path):
    empty_dir = tmp_path / "somewhere" / "unrelated"
    empty_dir.mkdir(parents=True)

    root = find_project_root(start=empty_dir)

    assert (root / "raw").exists()
    assert (root / "docs").exists()
