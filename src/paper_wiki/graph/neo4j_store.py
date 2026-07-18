from __future__ import annotations

import json
from typing import cast

from neo4j import GraphDatabase

from paper_wiki.core.config import Settings
from paper_wiki.graph.models import (
    DeleteAuthorshipEvent,
    DeletePatternClassificationEvent,
    DeletePriorWorkRelationEvent,
    GraphEvent,
    UpsertAuthorEvent,
    UpsertAuthorshipEvent,
    UpsertPaperEvent,
    UpsertPatternClassificationEvent,
    UpsertPatternEvent,
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

ALLOWED_CLASSIFICATION_ROLES = {"primary", "secondary"}


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
            "CREATE CONSTRAINT author_key_unique IF NOT EXISTS FOR (a:Author) REQUIRE a.author_key IS UNIQUE",
            "CREATE CONSTRAINT pattern_id_unique IF NOT EXISTS FOR (pt:Pattern) REQUIRE pt.pattern_id IS UNIQUE",
            "CREATE INDEX paper_slug_index IF NOT EXISTS FOR (p:Paper) ON (p.slug)",
            "CREATE INDEX paper_year_index IF NOT EXISTS FOR (p:Paper) ON (p.year)",
        ]
        with self.driver.session(database=self.database) as session:
            for statement in statements:
                session.run(statement).consume()

    def clear_graph(self) -> None:
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) WHERE n:Paper OR n:Author OR n:Pattern DETACH DELETE n").consume()

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
        if isinstance(event, UpsertAuthorEvent):
            self._upsert_author(event)
            return
        if isinstance(event, UpsertPatternEvent):
            self._upsert_pattern(event)
            return
        if isinstance(event, UpsertAuthorshipEvent):
            self._upsert_authorship(event)
            return
        if isinstance(event, DeleteAuthorshipEvent):
            self._delete_authorship(event)
            return
        if isinstance(event, UpsertPatternClassificationEvent):
            self._upsert_pattern_classification(event)
            return
        if isinstance(event, DeletePatternClassificationEvent):
            self._delete_pattern_classification(event)
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

    def _upsert_author(self, event: UpsertAuthorEvent) -> None:
        payload = _neo4j_properties(event.payload.model_dump(mode="json"))
        query = """
        MERGE (a:Author {author_key: $author_key})
        SET a += $payload
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, author_key=event.author_key, payload=payload).consume()

    def _upsert_pattern(self, event: UpsertPatternEvent) -> None:
        payload = _neo4j_properties(event.payload.model_dump(mode="json"))
        query = """
        MERGE (pt:Pattern {pattern_id: $pattern_id})
        SET pt += $payload
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, pattern_id=event.pattern_id, payload=payload).consume()

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

    def _upsert_authorship(self, event: UpsertAuthorshipEvent) -> None:
        query = """
        MATCH (a:Author {author_key: $author_key})
        MATCH (p:Paper {paper_key: $paper_key})
        MERGE (a)-[r:AUTHORED]->(p)
        SET r.author_order = $author_order
        """
        with self.driver.session(database=self.database) as session:
            session.run(
                query,
                author_key=event.author_key,
                paper_key=event.paper_key,
                author_order=event.payload.author_order,
            ).consume()

    def _delete_authorship(self, event: DeleteAuthorshipEvent) -> None:
        query = """
        MATCH (a:Author {author_key: $author_key})-[r:AUTHORED]->(p:Paper {paper_key: $paper_key})
        DELETE r
        """
        with self.driver.session(database=self.database) as session:
            session.run(
                query,
                author_key=event.author_key,
                paper_key=event.paper_key,
            ).consume()

    def _upsert_pattern_classification(self, event: UpsertPatternClassificationEvent) -> None:
        role = _validated_classification_role(event.role)
        query = """
        MATCH (p:Paper {paper_key: $paper_key})
        MATCH (pt:Pattern {pattern_id: $pattern_id})
        MERGE (p)-[r:CLASSIFIED_AS {role: $role}]->(pt)
        SET r.confidence = $confidence
        """
        with self.driver.session(database=self.database) as session:
            session.run(
                query,
                paper_key=event.paper_key,
                pattern_id=event.pattern_id,
                role=role,
                confidence=event.payload.confidence,
            ).consume()

    def _delete_pattern_classification(self, event: DeletePatternClassificationEvent) -> None:
        role = _validated_classification_role(event.role)
        query = """
        MATCH (p:Paper {paper_key: $paper_key})-[r:CLASSIFIED_AS {role: $role}]->(pt:Pattern {pattern_id: $pattern_id})
        DELETE r
        """
        with self.driver.session(database=self.database) as session:
            session.run(
                query,
                paper_key=event.paper_key,
                pattern_id=event.pattern_id,
                role=role,
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
    if op == "upsert_author":
        return UpsertAuthorEvent.model_validate(data)
    if op == "upsert_pattern":
        return UpsertPatternEvent.model_validate(data)
    if op == "upsert_authorship":
        return UpsertAuthorshipEvent.model_validate(data)
    if op == "delete_authorship":
        return DeleteAuthorshipEvent.model_validate(data)
    if op == "upsert_pattern_classification":
        return UpsertPatternClassificationEvent.model_validate(data)
    if op == "delete_pattern_classification":
        return DeletePatternClassificationEvent.model_validate(data)
    raise ValueError(f"Unknown graph event op: {op}")


def _validated_relation_type(relation_type: str) -> str:
    if relation_type not in ALLOWED_RELATION_TYPES:
        raise ValueError(f"Unsupported relation type: {relation_type}")
    return relation_type


def _validated_classification_role(role: str) -> str:
    if role not in ALLOWED_CLASSIFICATION_ROLES:
        raise ValueError(f"Unsupported classification role: {role}")
    return role


def _neo4j_properties(payload: dict) -> dict:
    return {key: value for key, value in payload.items() if value is not None}
