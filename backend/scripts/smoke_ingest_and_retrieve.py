"""Smoke script: ingest curriculum, approve version, then retrieve approved chunks.

Usage:
  python -m backend.scripts.smoke_ingest_and_retrieve \
    --source_root docs/Curriculum_in_json \
    --subject math \
    --sss_level SSS1 \
    --term 1 \
    --query "Explain linear equations"
"""

from __future__ import annotations

import argparse
import sys
from uuid import UUID

from backend.core.database import SessionLocal
from backend.schemas.admin_curriculum_schema import (
    CurriculumUploadRequest,
    CurriculumVersionActionRequest,
)
from backend.schemas.internal_rag_schema import InternalRagRetrieveRequest
from backend.services.admin_curriculum_service import AdminCurriculumService
from backend.services.rag_retrieve_service import RagRetrieveService


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test curriculum ingest + approve + retrieve")
    parser.add_argument("--source_root", required=True)
    parser.add_argument("--subject", choices=["math", "english", "civic"], required=True)
    parser.add_argument("--sss_level", choices=["SSS1", "SSS2", "SSS3"], required=True)
    parser.add_argument("--term", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--version_name", default=None)
    parser.add_argument("--actor_user_id", default=None)
    parser.add_argument("--top_k", type=int, default=6)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    actor_user_id = UUID(args.actor_user_id) if args.actor_user_id else None

    db = SessionLocal()
    try:
        curriculum_service = AdminCurriculumService(db)
        upload_payload = CurriculumUploadRequest(
            subject=args.subject,
            sss_level=args.sss_level,
            term=args.term,
            source_root=args.source_root,
            version_name=args.version_name,
        )
        upload = curriculum_service.upload_curriculum(payload=upload_payload, actor_user_id=actor_user_id)
        print(f"Uploaded version_id={upload.version_id} job_id={upload.job_id} status={upload.status}")

        approve = curriculum_service.approve_version(
            version_id=upload.version_id,
            payload=CurriculumVersionActionRequest(actor_user_id=actor_user_id),
        )
        print(
            f"Approved version_id={approve.version_id} status={approve.status} affected_topics={approve.affected_topics}"
        )

        retrieve_service = RagRetrieveService()
        retrieve_payload = InternalRagRetrieveRequest(
            query=args.query,
            subject=args.subject,
            sss_level=args.sss_level,
            term=args.term,
            topic_ids=[],
            top_k=max(1, min(args.top_k, 20)),
            approved_only=True,
        )
        retrieved = retrieve_service.retrieve(retrieve_payload)
        print(f"Retrieved chunks={len(retrieved.chunks)}")

        for index, chunk in enumerate(retrieved.chunks, start=1):
            metadata = dict(chunk.metadata or {})
            snippet = (chunk.text or "").strip().replace("\n", " ")
            print(f"[{index}] score={chunk.score:.4f}")
            print(
                "    citation_topic_title={0} citation_source_id={1} "
                "citation_chunk_index={2} citation_concept_label={3}".format(
                    metadata.get("citation_topic_title"),
                    metadata.get("citation_source_id"),
                    metadata.get("citation_chunk_index"),
                    metadata.get("citation_concept_label"),
                )
            )
            print(f"    text={snippet[:200]}")

        print("\nNeo4j verification query:")
        print("MATCH (c:Concept) RETURN c.id, c.name LIMIT 10;")
        return 0
    except Exception as exc:
        print(f"Smoke script failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
