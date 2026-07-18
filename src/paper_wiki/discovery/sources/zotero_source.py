from __future__ import annotations

from datetime import datetime, timezone
import fnmatch
import logging
import re
from typing import Any

from paper_wiki.discovery.exceptions import ZoteroConfigError
from paper_wiki.discovery.models import ZoteroCorpusEntry

logger = logging.getLogger(__name__)


def zotero_corpus(
    zotero_id: str,
    zotero_key: str,
    *,
    library_type: str = "user",
    ignore_pattern: str | None = None,
) -> list[ZoteroCorpusEntry]:
    if not zotero_id or not zotero_key:
        raise ZoteroConfigError("ZOTERO_ID and ZOTERO_KEY are required for recommendations.")
    try:
        from pyzotero.zotero import Zotero
    except ImportError as exc:
        raise ZoteroConfigError("pyzotero is required for Zotero recommendations.") from exc

    library_id, normalized_library_type = _normalize_library(zotero_id, library_type)
    try:
        zotero = Zotero(library_id, normalized_library_type, zotero_key)
        collection_paths = _load_collection_paths(zotero)
        items = zotero.everything(zotero.items(itemType="-attachment"))
    except Exception as exc:
        raise ZoteroConfigError(f"Zotero API request failed: {exc}") from exc

    entries: list[ZoteroCorpusEntry] = []
    for item in items:
        data = item.get("data", {})
        if data.get("itemType") == "note":
            continue
        abstract = str(data.get("abstractNote") or "").strip()
        if not abstract:
            continue
        collections = [
            collection_paths.get(collection_key, collection_key)
            for collection_key in data.get("collections", [])
        ]
        if _ignored(collections, ignore_pattern):
            continue
        entries.append(
            ZoteroCorpusEntry(
                title=str(data.get("title") or "").strip(),
                abstract=abstract,
                date_added=_parse_zotero_datetime(str(data.get("dateAdded") or "")),
                collections=collections,
            )
        )
    return entries


def _normalize_library(zotero_id: str, library_type: str) -> tuple[str, str]:
    raw_id = zotero_id.strip()
    raw_type = (library_type or "user").strip().lower()
    lowered = raw_id.lower()
    normalized_type = "group" if "groups/" in lowered or raw_type in {"group", "groups"} else "user"
    numbers = re.findall(r"\d+", raw_id)
    if not numbers:
        raise ZoteroConfigError("ZOTERO_ID must contain a numeric Zotero library id.")
    return numbers[-1], normalized_type


def _load_collection_paths(zotero: Any) -> dict[str, str]:
    collections = zotero.everything(zotero.collections())
    raw: dict[str, dict[str, str]] = {}
    for collection in collections:
        data = collection.get("data", {})
        key = data.get("key")
        if not key:
            continue
        raw[key] = {
            "name": str(data.get("name") or key),
            "parent": str(data.get("parentCollection") or ""),
        }

    resolved: dict[str, str] = {}

    def resolve(key: str) -> str:
        if key in resolved:
            return resolved[key]
        node = raw.get(key)
        if not node:
            resolved[key] = key
            return key
        parent = node["parent"]
        resolved[key] = f"{resolve(parent)}/{node['name']}" if parent else node["name"]
        return resolved[key]

    for key in raw:
        resolve(key)
    return resolved


def _ignored(collections: list[str], ignore_pattern: str | None) -> bool:
    patterns = [
        line.strip()
        for line in (ignore_pattern or "").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not patterns:
        return False
    for collection in collections:
        for pattern in patterns:
            normalized = pattern.rstrip("/")
            if fnmatch.fnmatch(collection, normalized) or fnmatch.fnmatch(collection, f"{normalized}/*"):
                return True
    return False


def _parse_zotero_datetime(value: str) -> datetime:
    if not value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        logger.warning("无法解析Zotero dateAdded，使用当前时间：%s", value)
        return datetime.now(timezone.utc)
