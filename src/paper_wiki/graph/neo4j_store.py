from __future__ import annotations

import json
from typing import cast

from neo4j import GraphDatabase

from paper_wiki.core.config import Settings
from paper_wiki.graph.models import (
    DeletePriorWorkRelationEvent,
    GraphEvent,
    UpsertPaperEvent,
    UpsertPriorWorkRelationEvent,
)


ALLOWED_RELATION_TYPES = {
    "BASELINE",
    "INSPIRATION",
    "GAP_IDENTIFICATION",
    "FOUNDATION",
    "EXTENSION",
    "RELATED_PROBLEM",
}


class Neo4jGraphStore:
    """把 graph update events 幂等写入 Neo4j。"""

    def __init__(self, settings: Settings) -> None:
        if not settings.neo4j_uri or not settings.neo4j_username or not settings.neo4j_password:
            raise ValueError("NEO4J_URI, NEO4J_USERNAME and NEO4J_PASSWORD must be configured in .env")
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_username, settings.neo4j_password),
        )
        self.database = settings.neo4j_database

    def close(self) -> None:
        self.driver.close()

    def ensure_schema(self) -> None:
        statements = [
            "CREATE CONSTRAINT paper_key_unique IF NOT EXISTS FOR (p:Paper) REQUIRE p.paper_key IS UNIQUE",
            "CREATE INDEX paper_slug_index IF NOT EXISTS FOR (p:Paper) ON (p.slug)",
            "CREATE INDEX paper_year_index IF NOT EXISTS FOR (p:Paper) ON (p.year)",
            "CREATE INDEX paper_pattern_index IF NOT EXISTS FOR (p:Paper) ON (p.primary_pattern_id)",
        ]
        with self.driver.session(database=self.database) as session:
            for statement in statements:
                session.run(statement).consume()

    def clear_graph(self) -> None:
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (p:Paper) DETACH DELETE p").consume()

    def apply_event(self, event: GraphEvent) -> None:
        if isinstance(event, UpsertPaperEvent):
            self._upsert_paper(event)
            return
        if isinstance(event, UpsertPriorWorkRelationEvent):
            self._upsert_relation(event)
            return
        if isinstance(event, DeletePriorWorkRelationEvent):
            self._delete_relation(event)
            return
        raise TypeError(f"Unsupported graph event: {type(event)!r}")

    def fetch_paper_snapshot(self, paper_key: str) -> dict | None:
        with self.driver.session(database=self.database) as session:
            record = session.run(
                "MATCH (p:Paper {paper_key: $paper_key}) RETURN properties(p) AS paper",
                paper_key=paper_key,
            ).single()
        return cast(dict | None, record["paper"] if record else None)

    def fetch_outgoing_relations(self, source_slug: str) -> list[dict]:
        query = """
        MATCH (source:Paper {slug: $source_slug})-[r]->(target:Paper)
        WHERE type(r) IN $relation_types
        RETURN type(r) AS relation_type, source.paper_key AS source_paper_key,
               target.paper_key AS target_paper_key, properties(r) AS payload
        ORDER BY relation_type, target.paper_key
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, source_slug=source_slug, relation_types=sorted(ALLOWED_RELATION_TYPES))
            return [record.data() for record in result]

    def _upsert_paper(self, event: UpsertPaperEvent) -> None:
        payload = _neo4j_properties(event.payload.model_dump(mode="json"))
        query = """
        MERGE (p:Paper {paper_key: $paper_key})
        SET p += $payload
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, paper_key=event.paper_key, payload=payload).consume()

    def _upsert_relation(self, event: UpsertPriorWorkRelationEvent) -> None:
        relation_type = _validated_relation_type(event.relation_type)
        query = f"""
        MATCH (source:Paper {{paper_key: $source_paper_key}})
        MATCH (target:Paper {{paper_key: $target_paper_key}})
        MERGE (source)-[r:{relation_type}]->(target)
        """
        with self.driver.session(database=self.database) as session:
            session.run(
                query,
                source_paper_key=event.source_paper_key,
                target_paper_key=event.target_paper_key,
            ).consume()

    def _delete_relation(self, event: DeletePriorWorkRelationEvent) -> None:
        relation_type = _validated_relation_type(event.relation_type)
        query = f"""
        MATCH (source:Paper {{paper_key: $source_paper_key}})-[r:{relation_type}]->(target:Paper {{paper_key: $target_paper_key}})
        DELETE r
        """
        with self.driver.session(database=self.database) as session:
            session.run(
                query,
                source_paper_key=event.source_paper_key,
                target_paper_key=event.target_paper_key,
            ).consume()


def load_graph_event(line: str) -> GraphEvent:
    data = json.loads(line)
    op = data.get("op")
    if op == "upsert_paper":
        return UpsertPaperEvent.model_validate(data)
    if op == "upsert_prior_work_relation":
        return UpsertPriorWorkRelationEvent.model_validate(data)
    if op == "delete_prior_work_relation":
        return DeletePriorWorkRelationEvent.model_validate(data)
    raise ValueError(f"Unknown graph event op: {op}")


def _validated_relation_type(relation_type: str) -> str:
    if relation_type not in ALLOWED_RELATION_TYPES:
        raise ValueError(f"Unsupported relation type: {relation_type}")
    return relation_type


def _neo4j_properties(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if value is not None}
