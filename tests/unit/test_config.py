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

    assert (root / "docs").exists()
    assert (root / "KnowledgeBase").exists() or (root / "src" / "paper_wiki").exists()


def test_default_data_dirs_live_under_knowledge_base(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings()

    kb = settings.resolved_knowledge_base_dir()
    assert kb == (settings.project_root / "KnowledgeBase").resolve()
    assert settings.resolved_raw_dir() == (kb / "raw").resolve()
    assert settings.resolved_artifacts_dir() == (kb / "artifacts").resolve()
    assert settings.resolved_graph_state_dir() == (kb / "graph_state").resolve()
    assert settings.resolved_graph_updates_dir() == (kb / "graph_updates").resolve()
    assert settings.resolved_prompts_dir() == (settings.project_root / "prompts").resolve()
