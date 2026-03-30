"""Service for internal RAG retrieval against Qdrant."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import logging

from backend.core.telemetry import log_timed_event, now_ms

from backend.core.config import settings
from backend.schemas.internal_rag_schema import (
    InternalRagChunkOut,
    InternalRagRetrieveRequest,
    InternalRagRetrieveResponse,
)


logger = logging.getLogger(__name__)


class RagRetrieveServiceError(RuntimeError):
    """Raised when retrieval from configured vector DB fails."""


@dataclass(frozen=True)
class QdrantRuntimeConfig:
    url: str
    api_key: str | None
    collection: str
    embedding_model: str

    @property
    def is_configured(self) -> bool:
        return bool(self.url and self.collection and self.embedding_model)


class QdrantVectorStore:
    """Qdrant wrapper with embedding and payload-filtered retrieval."""

    def __init__(self, config: QdrantRuntimeConfig):
        self.config = config
        self._client = None
        self._embedder = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            from qdrant_client import QdrantClient
        except ModuleNotFoundError as exc:
            raise RagRetrieveServiceError(
                "qdrant-client is not installed. Add `qdrant-client` to backend dependencies."
            ) from exc

        timeout_raw = os.getenv("QDRANT_TIMEOUT_SECONDS", "120").strip()
        try:
            timeout_seconds = max(10.0, float(timeout_raw))
        except ValueError:
            timeout_seconds = 120.0
        self._client = QdrantClient(url=self.config.url, api_key=self.config.api_key, timeout=timeout_seconds)
        return self._client

    def _ensure_embedder(self):
        if self._embedder is not None:
            return self._embedder
        try:
            from fastembed import TextEmbedding
        except ModuleNotFoundError as exc:
            raise RagRetrieveServiceError(
                "fastembed is not installed. Add `fastembed` to backend dependencies."
            ) from exc

        self._embedder = TextEmbedding(model_name=self.config.embedding_model)
        return self._embedder

    def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        embedder = self._ensure_embedder()
        vectors = list(embedder.embed(texts))
        return [vector.tolist() for vector in vectors]

    def embed_query(self, query: str) -> list[float]:
        vectors = self._embed_texts([query])
        if not vectors:
            raise RagRetrieveServiceError("Embedding model returned no vector for query")
        return vectors[0]

    def ensure_collection(self, vector_size: int) -> None:
        client = self._ensure_client()
        try:
            exists = client.collection_exists(self.config.collection)
        except Exception as exc:  # pragma: no cover - defensive wrapper for qdrant API variants
            raise RagRetrieveServiceError(f"Failed to check Qdrant collection: {exc}") from exc

        if exists:
            self._ensure_payload_indexes()
            return

        try:
            from qdrant_client.models import Distance, VectorParams

            client.create_collection(
                collection_name=self.config.collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            self._ensure_payload_indexes()
        except Exception as exc:
            raise RagRetrieveServiceError(f"Failed to create Qdrant collection: {exc}") from exc

    def _ensure_payload_indexes(self) -> None:
        client = self._ensure_client()
        try:
            from qdrant_client.models import PayloadSchemaType
        except Exception:
            return

        indexes = [
            ("curriculum_version_id", PayloadSchemaType.KEYWORD),
            ("subject", PayloadSchemaType.KEYWORD),
            ("sss_level", PayloadSchemaType.KEYWORD),
            ("term", PayloadSchemaType.INTEGER),
            ("topic_id", PayloadSchemaType.KEYWORD),
            ("approved", PayloadSchemaType.BOOL),
        ]
        for field_name, field_schema in indexes:
            try:
                client.create_payload_index(
                    collection_name=self.config.collection,
                    field_name=field_name,
                    field_schema=field_schema,
                    wait=True,
                )
            except Exception:
                # Index may already exist (or provider may not support explicit indexing); continue best-effort.
                continue

    def upsert_chunks(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        client = self._ensure_client()
        batch_size_raw = os.getenv("QDRANT_UPSERT_BATCH_SIZE", "96").strip()
        try:
            batch_size = max(1, int(batch_size_raw))
        except ValueError:
            batch_size = 96

        first_vector_size = None
        for start in range(0, len(rows), batch_size):
            batch_rows = rows[start : start + batch_size]
            vectors = self._embed_texts([str(row["text"]) for row in batch_rows])
            if not vectors:
                raise RagRetrieveServiceError("Embedding model returned no vectors for chunk batch")
            if first_vector_size is None:
                first_vector_size = len(vectors[0])
                self.ensure_collection(vector_size=first_vector_size)

            try:
                from qdrant_client.models import PointStruct

                points = [
                    PointStruct(
                        id=str(row["id"]),
                        vector=vectors[idx],
                        payload=row["payload"],
                    )
                    for idx, row in enumerate(batch_rows)
                ]
                client.upsert(collection_name=self.config.collection, points=points, wait=True)
            except Exception as exc:
                raise RagRetrieveServiceError(f"Failed to upsert chunks into Qdrant: {exc}") from exc

    def set_approval_flag(self, *, curriculum_version_id: UUID, approved: bool) -> None:
        client = self._ensure_client()
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            selector = Filter(
                must=[
                    FieldCondition(
                        key="curriculum_version_id",
                        match=MatchValue(value=str(curriculum_version_id)),
                    )
                ]
            )
            client.set_payload(
                collection_name=self.config.collection,
                payload={"approved": approved},
                points=selector,
                wait=True,
            )
        except Exception as exc:
            raise RagRetrieveServiceError(f"Failed to update approval payload in Qdrant: {exc}") from exc

    def health(self) -> dict[str, Any]:
        client = self._ensure_client()
        try:
            collections = client.get_collections()
            names = {item.name for item in collections.collections}
            return {
                "status": "ok",
                "collection_exists": self.config.collection in names,
            }
        except Exception as exc:
            return {"status": "error", "detail": str(exc)}

    @staticmethod
    def _scroll_points(result: Any) -> list[Any]:
        if isinstance(result, tuple):
            return list(result[0] or [])
        if hasattr(result, "points"):
            return list(getattr(result, "points") or [])
        return list(result or [])

    def topic_has_chunks(
        self,
        *,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID | str,
        approved_only: bool = True,
        curriculum_version_id: UUID | None = None,
    ) -> bool:
        if not self.config.is_configured:
            raise RagRetrieveServiceError("Qdrant configuration is missing (url/collection/embedding model)")

        client = self._ensure_client()
        try:
            from qdrant_client.models import FieldCondition, Filter, MatchValue

            must_conditions = [
                FieldCondition(key="subject", match=MatchValue(value=subject)),
                FieldCondition(key="sss_level", match=MatchValue(value=sss_level)),
                FieldCondition(key="term", match=MatchValue(value=term)),
                FieldCondition(key="topic_id", match=MatchValue(value=str(topic_id))),
            ]
            if approved_only:
                must_conditions.append(FieldCondition(key="approved", match=MatchValue(value=True)))
            if curriculum_version_id is not None:
                must_conditions.append(
                    FieldCondition(
                        key="curriculum_version_id",
                        match=MatchValue(value=str(curriculum_version_id)),
                    )
                )
            query_filter = Filter(must=must_conditions)

            try:
                result = client.scroll(
                    collection_name=self.config.collection,
                    scroll_filter=query_filter,
                    limit=1,
                    with_payload=False,
                    with_vectors=False,
                )
            except TypeError:
                result = client.scroll(
                    collection_name=self.config.collection,
                    filter=query_filter,
                    limit=1,
                    with_payload=False,
                    with_vectors=False,
                )
        except Exception as exc:
            raise RagRetrieveServiceError(f"Qdrant readiness check failed: {exc}") from exc

        return bool(self._scroll_points(result))

    def retrieve(self, payload: InternalRagRetrieveRequest) -> InternalRagRetrieveResponse:
        if not self.config.is_configured:
            raise RagRetrieveServiceError("Qdrant configuration is missing (url/collection/embedding model)")

        client = self._ensure_client()
        query_vector = self.embed_query(payload.query)

        try:
            from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

            must_conditions = [
                FieldCondition(key="subject", match=MatchValue(value=payload.subject)),
                FieldCondition(key="sss_level", match=MatchValue(value=payload.sss_level)),
                FieldCondition(key="term", match=MatchValue(value=payload.term)),
            ]
            if payload.approved_only:
                must_conditions.append(FieldCondition(key="approved", match=MatchValue(value=True)))
            if payload.curriculum_version_id is not None:
                must_conditions.append(
                    FieldCondition(
                        key="curriculum_version_id",
                        match=MatchValue(value=str(payload.curriculum_version_id)),
                    )
                )
            if payload.topic_ids:
                must_conditions.append(
                    FieldCondition(
                        key="topic_id",
                        match=MatchAny(any=[str(topic_id) for topic_id in payload.topic_ids]),
                    )
                )

            query_filter = Filter(must=must_conditions)
            if hasattr(client, "search"):
                result = client.search(
                    collection_name=self.config.collection,
                    query_vector=query_vector,
                    query_filter=query_filter,
                    limit=payload.top_k,
                    with_payload=True,
                )
            else:
                query_result = client.query_points(
                    collection_name=self.config.collection,
                    query=query_vector,
                    query_filter=query_filter,
                    limit=payload.top_k,
                    with_payload=True,
                )
                result = getattr(query_result, "points", query_result)
        except Exception as exc:
            raise RagRetrieveServiceError(f"Qdrant retrieval failed: {exc}") from exc

        chunks: list[InternalRagChunkOut] = []
        for item in result:
            metadata = dict(item.payload or {})
            chunks.append(
                InternalRagChunkOut(
                    chunk_id=str(metadata.get("chunk_id") or item.id),
                    source_id=str(metadata.get("source_id") or ""),
                    text=str(metadata.get("text") or ""),
                    score=float(item.score),
                    metadata=metadata,
                )
            )
        return InternalRagRetrieveResponse(chunks=chunks)


class RagRetrieveService:
    def __init__(self):
        self.store = QdrantVectorStore(
            QdrantRuntimeConfig(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key or None,
                collection=settings.qdrant_collection,
                embedding_model=settings.qdrant_embedding_model,
            )
        )

    def retrieve(self, payload: InternalRagRetrieveRequest) -> InternalRagRetrieveResponse:
        started_at = now_ms()
        topic_count = len(list(payload.topic_ids or []))
        try:
            response = self.store.retrieve(payload)
            log_timed_event(
                logger,
                "rag.retrieve",
                started_at,
                outcome="success",
                subject=payload.subject,
                sss_level=payload.sss_level,
                term=payload.term,
                top_k=payload.top_k,
                approved_only=payload.approved_only,
                topic_count=topic_count,
                curriculum_version_id=str(payload.curriculum_version_id) if payload.curriculum_version_id else None,
                chunk_count=len(response.chunks),
            )
            return response
        except RagRetrieveServiceError as exc:
            log_timed_event(
                logger,
                "rag.retrieve",
                started_at,
                log_level=logging.WARNING,
                outcome="error",
                subject=payload.subject,
                sss_level=payload.sss_level,
                term=payload.term,
                top_k=payload.top_k,
                approved_only=payload.approved_only,
                topic_count=topic_count,
                curriculum_version_id=str(payload.curriculum_version_id) if payload.curriculum_version_id else None,
                detail=str(exc),
            )
            raise
        except Exception as exc:
            log_timed_event(
                logger,
                "rag.retrieve",
                started_at,
                log_level=logging.WARNING,
                outcome="error",
                subject=payload.subject,
                sss_level=payload.sss_level,
                term=payload.term,
                top_k=payload.top_k,
                approved_only=payload.approved_only,
                topic_count=topic_count,
                curriculum_version_id=str(payload.curriculum_version_id) if payload.curriculum_version_id else None,
                detail=str(exc),
            )
            raise

    def topic_has_chunks(
        self,
        *,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID | str,
        approved_only: bool = True,
        curriculum_version_id: UUID | None = None,
    ) -> bool:
        return self.store.topic_has_chunks(
            subject=subject,
            sss_level=sss_level,
            term=term,
            topic_id=topic_id,
            approved_only=approved_only,
            curriculum_version_id=curriculum_version_id,
        )
