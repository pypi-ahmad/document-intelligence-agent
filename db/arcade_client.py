"""Thin HTTP client for ArcadeDB (https://docs.arcadedb.com).

Talks to ArcadeDB's REST API directly (no official Python driver needed):
  - POST /api/v1/server            server-level commands (create database)
  - POST /api/v1/command/{db}      write / DDL / DML SQL
  - POST /api/v1/query/{db}        read-only SQL
  - GET  /api/v1/ready             liveness check

This client owns the whole knowledge-graph schema:
  Document -HAS_CHUNK-> Chunk -MENTIONS-> Entity -RELATES_TO-> Entity
  Entity -BELONGS_TO-> Community -PART_OF-> Community (hierarchical levels)
"""

from __future__ import annotations

import contextlib
from functools import lru_cache
from typing import Any

import requests

import config
from utils import new_id

_ALREADY_EXISTS_HINTS = ("already exists", "duplicate")


class ArcadeDBError(RuntimeError):
    pass


class ArcadeDBClient:
    def __init__(
        self,
        host: str = config.ARCADEDB_HOST,
        port: int = config.ARCADEDB_PORT,
        database: str = config.ARCADEDB_DATABASE,
        user: str = config.ARCADEDB_USER,
        password: str = config.ARCADEDB_PASSWORD,
    ) -> None:
        self.base_url = f"http://{host}:{port}"
        self.database = database
        self.session = requests.Session()
        self.session.auth = (user, password)

    # -- low-level HTTP -----------------------------------------------

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self.session.post(f"{self.base_url}{path}", json=payload, timeout=30)
        except requests.exceptions.ConnectionError as exc:
            raise ArcadeDBError(
                f"Cannot reach ArcadeDB at {self.base_url}. Is the server/Docker "
                "container running? See README.md / launch.cmd."
            ) from exc
        if resp.status_code >= 300:
            raise ArcadeDBError(f"ArcadeDB error ({resp.status_code}): {resp.text}")
        return resp.json() if resp.text else {}

    def command(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        body = {"language": "sql", "command": sql, "params": params or {}}
        return self._post(f"/api/v1/command/{self.database}", body).get("result", [])

    def query(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        body = {"language": "sql", "command": sql, "params": params or {}}
        return self._post(f"/api/v1/query/{self.database}", body).get("result", [])

    def command_ignoring_exists(self, sql: str) -> None:
        try:
            self.command(sql)
        except ArcadeDBError as exc:
            if not any(hint in str(exc).lower() for hint in _ALREADY_EXISTS_HINTS):
                raise

    def is_ready(self) -> bool:
        try:
            resp = self.session.get(f"{self.base_url}/api/v1/ready", timeout=5)
        except requests.exceptions.ConnectionError:
            return False
        return resp.status_code == 204

    # -- bootstrap -------------------------------------------------------

    def ensure_database(self) -> None:
        try:
            self._post("/api/v1/server", {"command": f"create database {self.database}"})
        except ArcadeDBError as exc:
            if not any(hint in str(exc).lower() for hint in _ALREADY_EXISTS_HINTS):
                raise

    def ensure_schema(self, embedding_dimensions: int) -> None:
        for stmt in (
            "CREATE VERTEX TYPE Document",
            "CREATE VERTEX TYPE Chunk",
            "CREATE VERTEX TYPE Entity",
            "CREATE VERTEX TYPE Community",
            "CREATE EDGE TYPE HAS_CHUNK",
            "CREATE EDGE TYPE MENTIONS",
            "CREATE EDGE TYPE RELATES_TO",
            "CREATE EDGE TYPE BELONGS_TO",
            "CREATE EDGE TYPE PART_OF",
            "CREATE PROPERTY Document.id STRING",
            "CREATE PROPERTY Chunk.id STRING",
            "CREATE PROPERTY Entity.id STRING",
            "CREATE PROPERTY Entity.name STRING",
            "CREATE PROPERTY Community.id STRING",
            "CREATE INDEX ON Document (id) UNIQUE",
            "CREATE INDEX ON Chunk (id) UNIQUE",
            "CREATE INDEX ON Entity (id) UNIQUE",
            "CREATE INDEX ON Community (id) UNIQUE",
            "CREATE INDEX ON Entity (name) NOTUNIQUE",
            "CREATE PROPERTY Chunk.embedding ARRAY_OF_FLOATS",
        ):
            self.command_ignoring_exists(stmt)

        self.command_ignoring_exists(
            "CREATE INDEX ON Chunk (embedding) LSM_VECTOR METADATA {"
            f"dimensions: {embedding_dimensions}, similarity: 'COSINE'}}"
        )

    # -- documents / chunks -----------------------------------------------

    def create_document(self, doc_id: str, name: str, path: str, num_pages: int) -> None:
        self.command(
            "INSERT INTO Document SET id = :id, name = :name, path = :path, "
            "num_pages = :num_pages, summary = ''",
            {"id": doc_id, "name": name, "path": path, "num_pages": num_pages},
        )

    def create_chunk(
        self,
        chunk_id: str,
        doc_id: str,
        doc_name: str,
        page: int,
        text: str,
        embedding: list[float],
    ) -> None:
        self.command(
            "INSERT INTO Chunk SET id = :id, doc_id = :doc_id, doc_name = :doc_name, "
            "page = :page, text = :text, embedding = :embedding",
            {
                "id": chunk_id,
                "doc_id": doc_id,
                "doc_name": doc_name,
                "page": page,
                "text": text,
                "embedding": embedding,
            },
        )
        self.command(
            "CREATE EDGE HAS_CHUNK FROM (SELECT FROM Document WHERE id = :doc_id) "
            "TO (SELECT FROM Chunk WHERE id = :chunk_id)",
            {"doc_id": doc_id, "chunk_id": chunk_id},
        )

    def set_document_summary(self, doc_id: str, summary: str) -> None:
        self.command(
            "UPDATE Document SET summary = :s WHERE id = :id", {"s": summary, "id": doc_id}
        )

    def list_documents(self) -> list[dict[str, Any]]:
        return self.query("SELECT id, name, num_pages, summary FROM Document ORDER BY name")

    def delete_document(self, doc_id: str) -> None:
        self.command("DELETE VERTEX FROM Chunk WHERE doc_id = :id", {"id": doc_id})
        self.command("DELETE VERTEX FROM Document WHERE id = :id", {"id": doc_id})
        # Entities that were only mentioned by this document's (now-deleted)
        # chunks are orphaned -- drop them so they don't linger in future
        # retrieval, communities, or stats.
        self.command("DELETE VERTEX FROM Entity WHERE in('MENTIONS').size() = 0")

    # -- entities / relations ----------------------------------------------

    def upsert_entity(self, name: str, type_: str, description: str) -> str:
        existing = self.query(
            "SELECT id, description FROM Entity WHERE name = :name AND type = :type LIMIT 1",
            {"name": name, "type": type_},
        )
        if existing:
            entity_id = existing[0]["id"]
            if description and len(description) > len(existing[0].get("description") or ""):
                self.command(
                    "UPDATE Entity SET description = :d WHERE id = :id",
                    {"d": description, "id": entity_id},
                )
            return entity_id

        entity_id = new_id("ent")
        self.command(
            "INSERT INTO Entity SET id = :id, name = :name, type = :type, "
            "description = :description",
            {"id": entity_id, "name": name, "type": type_, "description": description},
        )
        return entity_id

    def create_mention(self, chunk_id: str, entity_id: str) -> None:
        exists = self.query(
            "SELECT count(*) as n FROM MENTIONS WHERE out.id = :chunk_id AND in.id = :entity_id",
            {"chunk_id": chunk_id, "entity_id": entity_id},
        )
        if exists and exists[0]["n"] > 0:
            return
        self.command(
            "CREATE EDGE MENTIONS FROM (SELECT FROM Chunk WHERE id = :chunk_id) "
            "TO (SELECT FROM Entity WHERE id = :entity_id)",
            {"chunk_id": chunk_id, "entity_id": entity_id},
        )

    def create_relation(self, source_id: str, label: str, target_id: str, description: str) -> None:
        exists = self.query(
            "SELECT count(*) as n FROM RELATES_TO WHERE "
            "out.id = :s AND in.id = :t AND label = :label",
            {"s": source_id, "t": target_id, "label": label},
        )
        if exists and exists[0]["n"] > 0:
            return
        self.command(
            "CREATE EDGE RELATES_TO FROM (SELECT FROM Entity WHERE id = :s) "
            "TO (SELECT FROM Entity WHERE id = :t) SET label = :label, description = :description",
            {"s": source_id, "t": target_id, "label": label, "description": description},
        )

    def entities_by_name(self, names: list[str]) -> list[dict[str, Any]]:
        if not names:
            return []
        lowered = [n.lower() for n in names]
        return self.query(
            "SELECT id, name, type, description FROM Entity WHERE name.toLowerCase() IN :names",
            {"names": lowered},
        )

    def all_entities_and_relations(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Full entity/relation graph, for community detection."""
        entities = self.query("SELECT id, name, type FROM Entity")
        relations = self.query("SELECT out.id as source, in.id as target, label FROM RELATES_TO")
        return entities, relations

    def multi_hop_neighbors(
        self, entity_ids: list[str], hops: int
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """BFS outward along RELATES_TO for `hops` steps. Returns (entities, path_trace)."""
        if not entity_ids:
            return [], []
        visited: dict[str, dict[str, Any]] = {}
        frontier = list(entity_ids)
        trace: list[str] = []
        for hop in range(hops):
            if not frontier:
                break
            neighbors = self.query(
                "SELECT id, name, type FROM (SELECT expand(both('RELATES_TO')) "
                "FROM Entity WHERE id IN :ids)",
                {"ids": frontier},
            )
            new_frontier = []
            for ent in neighbors:
                if ent["id"] not in visited:
                    visited[ent["id"]] = ent
                    new_frontier.append(ent["id"])
            if new_frontier:
                names = ", ".join(visited[eid]["name"] for eid in new_frontier[:5])
                trace.append(
                    f"hop {hop + 1}: reached {len(new_frontier)} entities via RELATES_TO ({names})"
                )
            frontier = new_frontier
        return list(visited.values()), trace

    def chunks_mentioning_entities(
        self, entity_ids: list[str], doc_filter: list[str] | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not entity_ids:
            return []
        sql = (
            "SELECT id, doc_id, doc_name, page, text FROM "
            "(SELECT expand(in('MENTIONS')) FROM Entity WHERE id IN :ids)"
        )
        params: dict[str, Any] = {"ids": entity_ids}
        if doc_filter:
            sql += " WHERE doc_name IN :docs"
            params["docs"] = doc_filter
        sql += f" LIMIT {int(limit)}"
        return self.query(sql, params)

    def communities_for_entities(self, entity_ids: list[str]) -> list[dict[str, Any]]:
        if not entity_ids:
            return []
        return self.query(
            "SELECT id, level, summary FROM (SELECT expand(out('BELONGS_TO')) "
            "FROM Entity WHERE id IN :ids)",
            {"ids": entity_ids},
        )

    # -- communities / hierarchical summaries -----------------------------

    def create_community(
        self, community_id: str, level: int, summary: str, entity_ids: list[str]
    ) -> None:
        self.command(
            "INSERT INTO Community SET id = :id, level = :level, summary = :summary",
            {"id": community_id, "level": level, "summary": summary},
        )
        for entity_id in entity_ids:
            self.command(
                "CREATE EDGE BELONGS_TO FROM (SELECT FROM Entity WHERE id = :e) "
                "TO (SELECT FROM Community WHERE id = :c)",
                {"e": entity_id, "c": community_id},
            )

    def link_community_hierarchy(self, child_id: str, parent_id: str) -> None:
        self.command(
            "CREATE EDGE PART_OF FROM (SELECT FROM Community WHERE id = :child) "
            "TO (SELECT FROM Community WHERE id = :parent)",
            {"child": child_id, "parent": parent_id},
        )

    def list_communities(self, level: int | None = None) -> list[dict[str, Any]]:
        if level is None:
            return self.query("SELECT id, level, summary FROM Community ORDER BY level")
        return self.query(
            "SELECT id, level, summary FROM Community WHERE level = :level", {"level": level}
        )

    def clear_communities(self) -> None:
        self.command("DELETE VERTEX FROM Community")

    def set_corpus_summary(self, summary: str) -> None:
        existing = self.query("SELECT id FROM Community WHERE level = -1 LIMIT 1")
        if existing:
            self.command(
                "UPDATE Community SET summary = :s WHERE id = :id",
                {"s": summary, "id": existing[0]["id"]},
            )
            return
        self.command(
            "INSERT INTO Community SET id = :id, level = -1, summary = :s",
            {"id": new_id("corpus"), "s": summary},
        )

    def get_corpus_summary(self) -> str:
        rows = self.query("SELECT summary FROM Community WHERE level = -1 LIMIT 1")
        return rows[0]["summary"] if rows else ""

    # -- vector search -----------------------------------------------------

    def vector_search(self, vector: list[float], top_k: int) -> list[dict[str, Any]]:
        literal = "[" + ",".join(repr(float(v)) for v in vector) + "]"
        sql = (
            "SELECT id, doc_id, doc_name, page, text, distance FROM "
            f"(SELECT expand(vectorNeighbors('Chunk[embedding]', {literal}, {int(top_k)})))"
        )
        return self.query(sql)

    # -- stats / lifecycle ---------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        def count(type_name: str) -> int:
            rows = self.query(f"SELECT count(*) as n FROM {type_name}")
            return rows[0]["n"] if rows else 0

        return {
            "documents": count("Document"),
            "chunks": count("Chunk"),
            "entities": count("Entity"),
            "relations": count("RELATES_TO"),
            "communities": count("Community"),
        }

    def reset(self) -> None:
        with contextlib.suppress(ArcadeDBError):
            self._post("/api/v1/server", {"command": f"drop database {self.database}"})
        self.ensure_database()


@lru_cache(maxsize=1)
def get_client() -> ArcadeDBClient:
    return ArcadeDBClient()
