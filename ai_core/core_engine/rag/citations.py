"""Citation formatting for RAG chunks (MVP)."""

from __future__ import annotations
from typing import Any, Dict, List
from ai_core.core_engine.rag.retriever import RagChunk


def _snippet(text: str, max_len: int = 240) -> str:
    t = " ".join(text.split())
    return t[:max_len] + ("..." if len(t) > max_len else "")


def format_citations(chunks: List[RagChunk]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ch in chunks:
        out.append(
            {
                "source_id": ch.source_id,
                "chunk_id": ch.chunk_id,
                "snippet": _snippet(ch.text),
                "metadata": ch.metadata,
            }
        )
    return out
