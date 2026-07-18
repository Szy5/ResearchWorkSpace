from __future__ import annotations

import sys
import types

from paper_wiki.discovery.sources import zotero_source


def test_zotero_corpus_filters_empty_abstracts_and_ignored_collections(monkeypatch) -> None:
    class FakeZotero:
        def __init__(self, zotero_id: str, library_type: str, zotero_key: str) -> None:
            pass

        def collections(self) -> str:
            return "collections"

        def items(self, itemType: str) -> str:
            return "items"

        def everything(self, query: str) -> list[dict]:
            if query == "collections":
                return [
                    {"data": {"key": "ROOT", "name": "Root", "parentCollection": False}},
                    {"data": {"key": "IGNORE", "name": "Ignore", "parentCollection": "ROOT"}},
                ]
            return [
                {
                    "data": {
                        "title": "Useful",
                        "abstractNote": "Has abstract",
                        "dateAdded": "2024-01-01T00:00:00Z",
                        "collections": ["ROOT"],
                    }
                },
                {
                    "data": {
                        "title": "Ignored",
                        "abstractNote": "Has abstract",
                        "dateAdded": "2024-01-02T00:00:00Z",
                        "collections": ["IGNORE"],
                    }
                },
                {"data": {"title": "No abstract", "abstractNote": "", "collections": []}},
            ]

    pyzotero_module = types.ModuleType("pyzotero")
    zotero_module = types.ModuleType("pyzotero.zotero")
    zotero_module.Zotero = FakeZotero
    monkeypatch.setitem(sys.modules, "pyzotero", pyzotero_module)
    monkeypatch.setitem(sys.modules, "pyzotero.zotero", zotero_module)

    corpus = zotero_source.zotero_corpus("123", "key", ignore_pattern="Root/Ignore")

    assert [entry.title for entry in corpus] == ["Useful"]
    assert corpus[0].collections == ["Root"]
