from __future__ import annotations

from datetime import date, datetime
import logging
import re
import shutil
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

import requests

from paper_wiki.core.config import Settings, get_settings
from paper_wiki.discovery.exceptions import ArxivAPIError, MainTexNotFoundError, SlugAlreadyExistsError
from paper_wiki.discovery.models import FetchResult, SearchCandidate
from paper_wiki.discovery.rate_limit import ArxivThrottle

logger = logging.getLogger(__name__)

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
ARXIV_NS = {"arxiv": "http://arxiv.org/schemas/atom"}
INPUT_PATTERN = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")
VERSION_SUFFIX = re.compile(r"v\d+$")


def search_by_query(
    query: str,
    start_year: int,
    end_year: int,
    max_results: int = 10,
    *,
    settings: Settings | None = None,
) -> list[SearchCandidate]:
    """
    根据关键词检索 arxiv 论文。

    Args:
        query: 关键词。
        start_year: 起始年份。
        end_year: 结束年份。
        max_results: 最大返回条数，默认 10。
        settings: 配置对象，可选。

    """
    settings = settings or get_settings()
    logger.info("开始检索：query=%s", query)
    _throttle(settings).acquire()
    submitted = f"submittedDate:[{start_year}01010000 TO {end_year}12312359]"
    search_query = f"all:{query} AND {submitted}"
    try:
        response = requests.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": search_query,
                "start": 0,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
            timeout=settings.fetch_download_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ArxivAPIError(f"arXiv search failed: {exc}") from exc
    return _parse_atom_candidates(response.text)[:max_results]


def daily_candidates(
    category_query: str,
    max_results: int = 200,
    *,
    settings: Settings | None = None,
) -> list[SearchCandidate]:
    """
    优先走arXiv RSS 失败后fallback到export API


    """
    settings = settings or get_settings()
    logger.info("开始拉取每日候选：query=%s", category_query)
    _throttle(settings).acquire()
    url = f"https://rss.arxiv.org/atom/{quote(category_query, safe='+.')}"
    try:
        response = requests.get(url, timeout=settings.fetch_download_timeout_seconds)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("arXiv每日RSS失败，退化为export API近期排序：%s", exc)
        return _daily_candidates_from_api(category_query, max_results=max_results, settings=settings)
    candidates = _parse_atom_candidates(response.text, daily_only=True)
    return candidates[:max_results]


def _daily_candidates_from_api(
    category_query: str,
    *,
    max_results: int,
    settings: Settings,
) -> list[SearchCandidate]:
    """
    根据分类查询 arxiv 每日候选论文。

    Args:
        category_query: 分类查询。
        max_results: 最大返回条数，默认 200。
        settings: 配置对象，可选。
    """
    categories = [part.strip() for part in category_query.split("+") if part.strip()]
    search_query = " OR ".join(f"cat:{category}" for category in categories) or f"all:{category_query}"
    _throttle(settings).acquire()
    try:
        response = requests.get(
            "https://export.arxiv.org/api/query",
            params={
                "search_query": search_query,
                "start": 0,
                "max_results": max_results,
                "sortBy": "submittedDate",
                "sortOrder": "descending",
            },
            timeout=settings.fetch_download_timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as api_exc:
        raise ArxivAPIError(f"arXiv daily RSS and API fallback failed: {api_exc}") from api_exc
    return _parse_atom_candidates(response.text)[:max_results]


def fetch(
    arxiv_id: str,
    *,
    settings: Settings | None = None,
    overwrite: bool = False,
) -> FetchResult:
    """
    下载 arxiv 论文源码并提取主文件。

    Args:
        arxiv_id: arXiv ID，例如 2401.12345。
        settings: 配置对象，可选。
        overwrite: 是否覆盖已有 raw/{slug}/ 目录，默认 False。

    Returns:
        FetchResult: 包含 slug、raw_dir、entry_file、has_pdf、source_file_count 的 FetchResult 对象。
    """
    settings = settings or get_settings()
    normalized_id = normalize_arxiv_id(arxiv_id)
    slug = slug_for_arxiv_id(normalized_id)
    raw_dir = settings.resolved_raw_dir() / slug
    if raw_dir.exists() and not overwrite:
        raise SlugAlreadyExistsError(f"{raw_dir} already exists. Use overwrite=True or --overwrite.")

    logger.info("开始拉取：arxiv_id=%s", normalized_id)
    with tempfile.TemporaryDirectory(prefix="paper-wiki-arxiv-") as tmp_name:
        tmp_dir = Path(tmp_name)
        source_dir = tmp_dir / "source"
        source_dir.mkdir()
        _download_source_archive(normalized_id, tmp_dir / "source.tar", settings)
        _extract_source(tmp_dir / "source.tar", source_dir)
        entry = find_main_tex(source_dir)
        if raw_dir.exists():
            shutil.rmtree(raw_dir)
        raw_dir.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, raw_dir)
        logger.info("已找到主文件，正在下载 PDF")
        has_pdf = _download_pdf(normalized_id, raw_dir / "paper.pdf", settings)
    source_file_count = len([path for path in raw_dir.rglob("*") if path.is_file()])
    return FetchResult(
        slug=slug,
        raw_dir=raw_dir,
        entry_file=str(entry.relative_to(source_dir)),
        has_pdf=has_pdf,
        source_file_count=source_file_count,
    )


def normalize_arxiv_id(arxiv_id: str) -> str:
    value = arxiv_id.strip()
    value = value.removeprefix("https://arxiv.org/abs/").removeprefix("http://arxiv.org/abs/")
    value = value.removeprefix("arXiv:").removeprefix("arxiv:")
    # The daily announcement RSS feed (rss.arxiv.org/atom/...) identifies entries with an
    # OAI-style id ("oai:arXiv.org:2607.10562") instead of the export API's abs URL.
    value = value.removeprefix("oai:arXiv.org:").removeprefix("oai:arxiv.org:")
    return VERSION_SUFFIX.sub("", value)


def slug_for_arxiv_id(arxiv_id: str) -> str:
    return normalize_arxiv_id(arxiv_id).replace("/", "-")


def find_main_tex(source_dir: Path) -> Path:
    tex_files = [path for path in source_dir.rglob("*.tex") if path.is_file()]
    if not tex_files:
        raise MainTexNotFoundError(f"No .tex file found in source archive: {source_dir}")

    bbl_files = [path for path in source_dir.rglob("*.bbl") if path.is_file()]
    if len(bbl_files) == 1:
        matching_tex = bbl_files[0].with_suffix(".tex")
        if matching_tex.exists():
            return matching_tex

    document_files = [
        path for path in tex_files if r"\begin{document}" in path.read_text(encoding="utf-8", errors="ignore")
    ]
    if document_files:
        return max(document_files, key=lambda path: path.stat().st_size)

    logger.error("fetch() 主文件识别失败，候选tex文件：%s", [str(path.relative_to(source_dir)) for path in tex_files])
    raise MainTexNotFoundError(f"No main tex file found in source archive: {source_dir}")


def _download_source_archive(arxiv_id: str, destination: Path, settings: Settings) -> None:
    _throttle(settings).acquire()
    try:
        with requests.get(
            f"https://arxiv.org/e-print/{arxiv_id}",
            timeout=settings.fetch_download_timeout_seconds,
            stream=True,
        ) as response:
            response.raise_for_status()
            with destination.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        file.write(chunk)
    except requests.RequestException as exc:
        raise ArxivAPIError(f"arXiv source download failed: {exc}") from exc


def _download_pdf(arxiv_id: str, destination: Path, settings: Settings) -> bool:
    _throttle(settings).acquire()
    try:
        with requests.get(
            f"https://arxiv.org/pdf/{arxiv_id}",
            timeout=settings.fetch_download_timeout_seconds,
            stream=True,
        ) as response:
            response.raise_for_status()
            with destination.open("wb") as file:
                for chunk in response.iter_content(chunk_size=1024 * 128):
                    if chunk:
                        file.write(chunk)
        return True
    except requests.RequestException as exc:
        logger.warning("PDF下载失败，继续保留源码：arxiv_id=%s, error=%s", arxiv_id, exc)
        return False


def _extract_source(archive_path: Path, destination: Path) -> None:
    if tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                target = (destination / member.name).resolve()
                if not target.is_relative_to(destination.resolve()):
                    raise ArxivAPIError(f"Unsafe arXiv archive member: {member.name}")
            archive.extractall(destination, filter="data")
        return

    text = archive_path.read_bytes()
    target = destination / "main.tex"
    target.write_bytes(text)


def _parse_atom_candidates(payload: str, *, daily_only: bool = False) -> list[SearchCandidate]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ArxivAPIError(f"arXiv XML parse failed: {exc}") from exc
    candidates: list[SearchCandidate] = []
    for entry in root.findall("atom:entry", ATOM_NS):
        announce_type = _entry_text(entry, "arxiv:announce_type", ARXIV_NS)
        if daily_only and announce_type and announce_type != "new":
            continue
        title = _clean_text(_entry_text(entry, "atom:title", ATOM_NS))
        abstract = _clean_text(_entry_text(entry, "atom:summary", ATOM_NS))
        updated = _parse_datetime(_entry_text(entry, "atom:published", ATOM_NS)) or _parse_datetime(
            _entry_text(entry, "atom:updated", ATOM_NS)
        )
        arxiv_id = normalize_arxiv_id((_entry_text(entry, "atom:id", ATOM_NS).rsplit("/", 1)[-1]))
        venue = _category_term(entry)
        candidates.append(
            SearchCandidate(
                title=title,
                authors=[
                    _clean_text(author.findtext("atom:name", default="", namespaces=ATOM_NS))
                    for author in entry.findall("atom:author", ATOM_NS)
                    if _clean_text(author.findtext("atom:name", default="", namespaces=ATOM_NS))
                ],
                year=updated.year if updated else None,
                abstract=abstract,
                url=f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else _entry_text(entry, "atom:id", ATOM_NS),
                venue=venue,
                arxiv_id=arxiv_id,
                publication_date=updated.date() if updated else None,
                source="arxiv",
            )
        )
    return candidates


def _entry_text(entry: ET.Element, path: str, namespaces: dict[str, str]) -> str:
    return entry.findtext(path, default="", namespaces=namespaces)


def _category_term(entry: ET.Element) -> str:
    category = entry.find("atom:category", ATOM_NS)
    return category.attrib.get("term", "") if category is not None else ""


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(value[:10]), datetime.min.time())
        except ValueError:
            return None


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _throttle(settings: Settings) -> ArxivThrottle:
    return ArxivThrottle(settings.arxiv_min_interval)
