"""Prerequisite lookups (MVP)."""

from __future__ import annotations
from typing import List
from ai_core.core_engine.knowledge_graph.neo4j_client import Neo4jClient


class PrereqService:
    def __init__(self, client: Neo4jClient):
        self.client = client

    def get_prerequisites_for_topic(self, *, topic_id: str) -> List[str]:
        """Return prerequisite concept IDs for a topic.

        Graph assumption:
        (:Topic {id})-[:COVERS]->(:Concept)
        (:Concept)-[:PREREQ_OF]->(:Concept)
        """
        # Optimized to remove the ghost 'PREREQUISITE_OF' label
        # to silence Neo4j schema warnings.
        cypher = """
        MATCH (t:Topic {id: $topic_id})-[:COVERS]->(c:Concept)
        MATCH (p:Concept)-[:PREREQ_OF*1..5]->(c)
        RETURN DISTINCT p.id AS prereq_id
        """
        recs = self.client.run(cypher, {"topic_id": topic_id})
        return [r["prereq_id"] for r in recs if r.get("prereq_id")]