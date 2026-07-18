from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from paper_wiki.graph.models import ApplyCheckpoint, GraphEvent, GraphState


class GraphStateStore:
    """维护本地图谱快照、增量事件日志和应用进度。"""

    def __init__(self, state_dir: Path, updates_dir: Path) -> None:
        self.state_dir = state_dir
        self.updates_dir = updates_dir
        self.papers_path = self.state_dir / "papers.json"
        self.relations_path = self.state_dir / "prior_work_relations.json"
        self.authors_path = self.state_dir / "authors.json"
        self.patterns_path = self.state_dir / "patterns.json"
        self.authorships_path = self.state_dir / "authorships.json"
        self.pattern_classifications_path = self.state_dir / "pattern_classifications.json"
        self.events_path = self.updates_dir / "graph_updates.jsonl"
        self.checkpoint_path = self.updates_dir / "checkpoint.json"

    def load_state(self) -> GraphState:
        state_paths = (
            self.papers_path,
            self.relations_path,
            self.authors_path,
            self.patterns_path,
            self.authorships_path,
            self.pattern_classifications_path,
        )
        if not any(path.exists() for path in state_paths):
            return GraphState()
        return GraphState.model_validate(
            {
                "papers": self._read_json(self.papers_path),
                "relations": self._read_json(self.relations_path),
                "authors": self._read_json(self.authors_path),
                "patterns": self._read_json(self.patterns_path),
                "authorships": self._read_json(self.authorships_path),
                "pattern_classifications": self._read_json(self.pattern_classifications_path),
            }
        )

    def save_state(self, state: GraphState) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._write_json(self.papers_path, state.papers)
        self._write_json(self.relations_path, state.relations)
        self._write_json(self.authors_path, state.authors)
        self._write_json(self.patterns_path, state.patterns)
        self._write_json(self.authorships_path, state.authorships)
        self._write_json(self.pattern_classifications_path, state.pattern_classifications)

    def _read_json(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def _write_json(self, path: Path, values: dict[str, BaseModel]) -> None:
        path.write_text(
            json.dumps({key: value.model_dump(mode="json") for key, value in values.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def append_events(self, events: list[GraphEvent]) -> None:
        if not events:
            return
        self.updates_dir.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")

    def load_events(self) -> list[str]:
        if not self.events_path.exists():
            return []
        return self.events_path.read_text(encoding="utf-8").splitlines()

    def load_checkpoint(self) -> ApplyCheckpoint:
        if not self.checkpoint_path.exists():
            return ApplyCheckpoint()
        return ApplyCheckpoint.model_validate_json(self.checkpoint_path.read_text(encoding="utf-8"))

    def save_checkpoint(self, checkpoint: ApplyCheckpoint) -> None:
        self.updates_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_path.write_text(checkpoint.model_dump_json(indent=2), encoding="utf-8")
