"""Neo4j driver wrapper (MVP)."""

from __future__ import annotations
from neo4j import GraphDatabase
from typing import Any, Dict, List, Optional


class Neo4jClient:
    def __init__(self, uri: str, user: str, password: str):
        self._driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def run(self, cypher: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        params = params or {}
        with self._driver.session() as session:
            res = session.run(cypher, params)
            return [r.data() for r in res]
