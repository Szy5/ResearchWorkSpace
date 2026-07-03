from __future__ import annotations

import json
from pathlib import Path

from paper_wiki.graph.models import ApplyCheckpoint, GraphEvent, GraphState


class GraphStateStore:
    """维护本地图谱快照、增量事件日志和应用进度。"""

    def __init__(self, state_dir: Path, updates_dir: Path) -> None:
        self.state_dir = state_dir
        self.updates_dir = updates_dir
        self.papers_path = self.state_dir / "papers.json"
        self.relations_path = self.state_dir / "prior_work_relations.json"
        self.events_path = self.updates_dir / "graph_updates.jsonl"
        self.checkpoint_path = self.updates_dir / "checkpoint.json"

    def load_state(self) -> GraphState:
        if not self.papers_path.exists() and not self.relations_path.exists():
            return GraphState()
        papers = json.loads(self.papers_path.read_text(encoding="utf-8")) if self.papers_path.exists() else {}
        relations = json.loads(self.relations_path.read_text(encoding="utf-8")) if self.relations_path.exists() else {}
        return GraphState.model_validate({"papers": papers, "relations": relations})

    def save_state(self, state: GraphState) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.papers_path.write_text(
            json.dumps({key: value.model_dump(mode="json") for key, value in state.papers.items()}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self.relations_path.write_text(
            json.dumps(
                {key: value.model_dump(mode="json") for key, value in state.relations.items()},
                ensure_ascii=False,
                indent=2,
            ),
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
