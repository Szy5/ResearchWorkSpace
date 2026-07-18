from __future__ import annotations

from paper_wiki.web.services.progress_messages import FALLBACK_MESSAGE, translate_progress


def test_translate_progress_maps_known_messages() -> None:
    assert translate_progress("开始生成每日推荐") == "🔍 正在生成今日推荐..."
    assert translate_progress("开始拉取：arxiv_id=2401.12345") == "📥 正在下载论文源码..."
    assert translate_progress("步骤 1/3：生成 summary.md") == "📝 正在生成精读摘要..."
    assert translate_progress("步骤 2/3：生成 prior_works.json") == "🔗 正在分析前序工作..."
    assert translate_progress("步骤 3/3：生成 sci_pattern.json") == "🏷️ 正在识别科学范式..."
    assert translate_progress("Layer1 语义产物生成完成：slug=demo") == "✅ 生成完成"


def test_translate_progress_keeps_candidate_summary_counter() -> None:
    assert translate_progress("正在为候选生成摘要 (4/15)") == "📝 正在为候选生成摘要 (4/15)..."


def test_translate_progress_falls_back_for_unknown_messages() -> None:
    assert translate_progress("some unrelated internal log line") == FALLBACK_MESSAGE
