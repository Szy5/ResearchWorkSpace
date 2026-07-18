from __future__ import annotations

from datetime import date, datetime, timezone
import logging
import math
from pathlib import Path

from paper_wiki.core.config import Settings, get_settings
from paper_wiki.discovery import search as search_facade
from paper_wiki.discovery.models import RecommendationSnapshot, RankedCandidate, SearchCandidate, ZoteroCorpusEntry

logger = logging.getLogger(__name__)


def run(
    max_papers: int | None = None,
    *,
    arxiv_query: str | None = None,
    settings: Settings | None = None,
) -> RecommendationSnapshot:
    """
    生成每日推荐

    Args:
        max_papers: 最大返回条数，默认读取 MAX_PAPER_NUM。
        arxiv_query: 覆盖 ARXIV_QUERY 候选池查询。
        settings: 配置对象，可选。
    """
    settings = settings or get_settings()
    max_papers = max_papers or settings.max_paper_num
    query = arxiv_query or settings.arxiv_query
    logger.info("开始生成每日推荐")
    # 1. 从 Zotero 获取文献库
    logger.info("正在获取 Zotero 口味语料")
    corpus = search_facade.zotero_corpus(settings=settings)
    # 2. 从 arXiv 获取候选论文
    logger.info("正在拉取 arXiv 候选池")
    candidates = search_facade.daily_candidates(query, max_results=max(settings.recommend_candidate_pool_size, max_papers), settings=settings)
    # 3. 对候选论文进行排序
    logger.info("正在计算相似度排序")
    ranked, degraded = _rerank(candidates, corpus, model_name=settings.recommend_embedding_model)
    # 4. 生成推荐快照
    snapshot = RecommendationSnapshot(
        date=date.today(),
        generated_at=datetime.now(timezone.utc),
        corpus_size=len(corpus),
        candidate_pool_size=len(candidates),
        candidates=ranked[:max_papers],
        degraded=degraded,
    )
    dated_path, _ = snapshot_paths(snapshot.date, settings)
    write_snapshot(snapshot, settings)
    logger.info("已写入推荐快照：%s", dated_path)
    logger.info("推荐生成完成：candidates=%d, degraded=%s", len(snapshot.candidates), degraded)
    return snapshot


def snapshot_paths(snapshot_date: date, settings: Settings) -> tuple[Path, Path]:
    """(dated_path, latest_path) for a recommendation snapshot on disk."""
    output_dir = settings.resolved_artifacts_dir() / ".recommendations"
    return output_dir / f"{snapshot_date.isoformat()}.json", output_dir / "latest.json"


def write_snapshot(snapshot: RecommendationSnapshot, settings: Settings) -> None:
    """(Re)write a snapshot to its dated and latest.json paths."""
    dated_path, latest_path = snapshot_paths(snapshot.date, settings)
    dated_path.parent.mkdir(parents=True, exist_ok=True)
    payload = snapshot.model_dump_json(indent=2)
    dated_path.write_text(payload, encoding="utf-8")
    latest_path.write_text(payload, encoding="utf-8")


def _rerank(
    candidates: list[SearchCandidate],
    corpus: list[ZoteroCorpusEntry],
    *,
    model_name: str = "avsolatorio/GIST-small-Embedding-v0",
) -> tuple[list[RankedCandidate], bool]:
    if not candidates:
        return [], False
    if not corpus:
        return [_ranked(candidate, 0.0, "") for candidate in candidates], True

    ordered_corpus = sorted(corpus, key=lambda entry: entry.date_added, reverse=True)
    weights = _time_decay_weights(len(ordered_corpus))
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(model_name)
        candidate_embeddings = model.encode([_candidate_text(candidate) for candidate in candidates])
        corpus_embeddings = model.encode([entry.abstract for entry in ordered_corpus])
        similarity = _cosine_similarity_matrix(candidate_embeddings, corpus_embeddings)
    except Exception as exc:
        logger.warning("sentence-transformers不可用，推荐排序降级：%s", exc)
        return [_ranked(candidate, 0.0, "") for candidate in candidates], True

    scored: list[RankedCandidate] = []
    for row_index, candidate in enumerate(candidates):
        sims = similarity[row_index]
        score = sum(sim * weight for sim, weight in zip(sims, weights)) * 10
        best_index = max(range(len(sims)), key=lambda index: sims[index]) if sims else 0
        reason = f'与 "{ordered_corpus[best_index].title}" 相似度{max(0.0, sims[best_index]) * 100:.0f}%'
        scored.append(_ranked(candidate, score, reason))
    return sorted(scored, key=lambda candidate: candidate.score or 0.0, reverse=True), False


def _time_decay_weights(size: int) -> list[float]:
    raw = [1 / (1 + math.log10(index + 1)) for index in range(size)]
    total = sum(raw) or 1.0
    return [value / total for value in raw]


def _cosine_similarity_matrix(left: object, right: object) -> list[list[float]]:
    try:
        import numpy as np

        left_array = np.asarray(left, dtype=float)
        right_array = np.asarray(right, dtype=float)
        left_norm = np.linalg.norm(left_array, axis=1, keepdims=True)
        right_norm = np.linalg.norm(right_array, axis=1, keepdims=True).T
        denom = np.maximum(left_norm * right_norm, 1e-12)
        return ((left_array @ right_array.T) / denom).tolist()
    except Exception:
        return _cosine_similarity_matrix_plain(left, right)


def _cosine_similarity_matrix_plain(left: object, right: object) -> list[list[float]]:
    left_rows = [list(map(float, row)) for row in left]  # type: ignore[arg-type]
    right_rows = [list(map(float, row)) for row in right]  # type: ignore[arg-type]
    result: list[list[float]] = []
    for left_row in left_rows:
        row: list[float] = []
        left_norm = math.sqrt(sum(value * value for value in left_row)) or 1.0
        for right_row in right_rows:
            right_norm = math.sqrt(sum(value * value for value in right_row)) or 1.0
            row.append(sum(a * b for a, b in zip(left_row, right_row)) / (left_norm * right_norm))
        result.append(row)
    return result


def _candidate_text(candidate: SearchCandidate) -> str:
    return candidate.abstract or candidate.title


def _ranked(candidate: SearchCandidate, score: float, reason: str) -> RankedCandidate:
    data = candidate.model_dump()
    data["score"] = float(score)
    data["reason"] = reason
    return RankedCandidate.model_validate(data)
