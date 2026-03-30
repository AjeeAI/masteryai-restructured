"""Hard reset and reseed workflow for curriculum KB + graph diagnostics.

Usage (from repo root):
  python -m backend.scripts.reset_and_reseed_curriculum

Recommended first-run deterministic mode:
  python -m backend.scripts.reset_and_reseed_curriculum \
    --disable-llm \
    --disable-neo4j-sync \
    --seed-reset \
    --qdrant-batch-size 24 \
    --qdrant-timeout-seconds 240

Include demo learners only when needed:
  python -m backend.scripts.reset_and_reseed_curriculum --seed-demo-learners

Notes:
- This script is destructive for curriculum ingestion/version tables and vector chunks.
- It keeps core auth/profile tables intact.
- Use --full-db-reset to truncate all public application tables (except alembic_version).
- If Neo4j is offline, keep --disable-neo4j-sync enabled.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import text

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_CURRICULUM_ROOT = REPO_ROOT / "docs" / "Curriculum_in_json"
LEGACY_CURRICULUM_ROOT = REPO_ROOT / "docs" / "SSS_NOTES_2026"


def _default_source_root() -> str:
    if CANONICAL_CURRICULUM_ROOT.exists() and any(CANONICAL_CURRICULUM_ROOT.rglob("*.json")):
        return str(CANONICAL_CURRICULUM_ROOT)
    return str(LEGACY_CURRICULUM_ROOT)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset curriculum KB data and reseed end-to-end")
    parser.add_argument("--source-root", default=_default_source_root())
    parser.add_argument("--skip-json-validation", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--full-db-reset", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--seed-lessons", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed-reset", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed-demo-learners", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--disable-llm", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--disable-neo4j-sync", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--seed-neo4j", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--qdrant-batch-size", type=int, default=24)
    parser.add_argument("--qdrant-timeout-seconds", type=float, default=240.0)
    parser.add_argument("--keep-failed-versions", action=argparse.BooleanOptionalAction, default=False)
    return parser.parse_args()


def _configure_runtime(args: argparse.Namespace) -> None:
    os.environ["QDRANT_UPSERT_BATCH_SIZE"] = str(max(1, int(args.qdrant_batch_size)))
    os.environ["QDRANT_TIMEOUT_SECONDS"] = str(max(10.0, float(args.qdrant_timeout_seconds)))

    if args.disable_llm:
        os.environ["CURRICULUM_CONCEPT_USE_LLM"] = "false"
        os.environ["CURRICULUM_CONCEPT_EXTRACT_USE_LLM"] = "false"
        os.environ["CURRICULUM_PREREQ_USE_LLM"] = "false"
        print("  - LLM extraction/inference: disabled by flag")
    else:
        # LLM-first default for ingestion, while still allowing explicit env overrides.
        os.environ.setdefault("CURRICULUM_CONCEPT_USE_LLM", "true")
        os.environ.setdefault("CURRICULUM_CONCEPT_EXTRACT_USE_LLM", "true")
        os.environ.setdefault("CURRICULUM_PREREQ_USE_LLM", "true")
        print("  - LLM extraction/inference: enabled by default")

    if args.disable_neo4j_sync:
        os.environ["USE_NEO4J_GRAPH"] = "false"

    print(f"  - curriculum source root: {args.source_root}")


def _validate_canonical_json_if_present(args: argparse.Namespace) -> None:
    source_root = Path(args.source_root).expanduser().resolve()
    if args.skip_json_validation:
        return
    if not source_root.exists() or not source_root.is_dir():
        return
    if not any(source_root.rglob("*.json")):
        return

    print("[preflight] Validating canonical curriculum JSON...")
    from backend.scripts.validate_curriculum_json import validate_curriculum_json_root

    result = validate_curriculum_json_root(source_root)
    print(
        "  - validation summary: "
        f"files={result['file_count']}, errors={result['error_count']}, warnings={result['warning_count']}"
    )
    if result["warnings"]:
        warning_details = list(result.get("warning_details") or [])
        if warning_details:
            for item in warning_details[:10]:
                print(f"    warning: {item['file']}: {item['message']}")
                print(f"      suggestion: {item['suggestion']}")
            if len(warning_details) > 10:
                print(f"    ... {len(warning_details) - 10} more warning(s)")
        else:
            for entry in list(result["warnings"])[:10]:
                print(f"    warning: {entry}")
            if len(result["warnings"]) > 10:
                print(f"    ... {len(result['warnings']) - 10} more warning(s)")
    if result["errors"]:
        for entry in result["errors"]:
            print(f"    error: {entry}")
        raise RuntimeError("Canonical curriculum JSON validation failed. Fix errors or use --skip-json-validation.")


def _run_seed_lessons(args: argparse.Namespace) -> None:
    if not args.seed_lessons:
        return
    os.environ["SEED_RESET"] = "1" if args.seed_reset else "0"
    os.environ["SEED_INCLUDE_DEMO_LEARNERS"] = "1" if args.seed_demo_learners else "0"
    print("[1/7] Running lesson seed script...")
    from backend.scripts.seed_lessons import run as seed_lessons_run

    seed_lessons_run()


def _list_public_tables(db) -> list[str]:
    rows = db.execute(
        text(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY tablename
            """
        )
    ).fetchall()
    return [str(row[0]) for row in rows]


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _full_postgres_reset() -> None:
    print("[0/full] Truncating all application tables in Postgres...")
    from backend.core.database import SessionLocal

    db = SessionLocal()
    try:
        public_tables = _list_public_tables(db)
        truncate_tables = [name for name in public_tables if name != "alembic_version"]
        if not truncate_tables:
            print("  - no application tables found to truncate")
            return

        truncate_sql = (
            "TRUNCATE TABLE "
            + ", ".join(_quote_ident(name) for name in truncate_tables)
            + " RESTART IDENTITY CASCADE"
        )
        db.execute(text(truncate_sql))
        db.commit()
        print(f"  - truncated tables={len(truncate_tables)}")
    finally:
        db.close()


def _clear_curriculum_tables() -> None:
    print("[2/7] Clearing curriculum ingestion tables...")
    from backend.core.database import SessionLocal

    db = SessionLocal()
    try:
        deleted_maps = db.execute(text("DELETE FROM curriculum_topic_maps")).rowcount
        deleted_jobs = db.execute(text("DELETE FROM curriculum_ingestion_jobs")).rowcount
        deleted_versions = db.execute(text("DELETE FROM curriculum_versions")).rowcount
        reset_topics = db.execute(text("UPDATE topics SET curriculum_version_id = NULL, is_approved = TRUE")).rowcount
        db.commit()
        print(
            "  - postgres rows: "
            f"topic_maps={max(deleted_maps or 0, 0)}, "
            f"ingestion_jobs={max(deleted_jobs or 0, 0)}, "
            f"versions={max(deleted_versions or 0, 0)}, "
            f"topics_reset={max(reset_topics or 0, 0)}"
        )
    finally:
        db.close()


def _clear_qdrant_collection() -> None:
    print("[3/7] Resetting Qdrant collection...")
    from backend.core.config import settings

    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=float(os.getenv("QDRANT_TIMEOUT_SECONDS", "240")),
        )
        if client.collection_exists(settings.qdrant_collection):
            client.delete_collection(collection_name=settings.qdrant_collection)
            print(f"  - deleted collection: {settings.qdrant_collection}")
        else:
            print(f"  - collection not present: {settings.qdrant_collection}")
    except Exception as exc:
        print(f"  - warning: could not reset Qdrant collection ({exc})")


def _bulk_ingest_and_approve(source_root: str) -> tuple[int, int, list[str]]:
    print("[4/7] Bulk ingesting curriculum scopes...")
    from backend.core.database import SessionLocal
    from backend.schemas.admin_curriculum_schema import CurriculumBulkIngestRequest, CurriculumVersionActionRequest
    from backend.services.admin_curriculum_service import AdminCurriculumService

    db = SessionLocal()
    failed_messages: list[str] = []
    approved_count = 0
    discovered_scopes = 0
    try:
        service = AdminCurriculumService(db)
        bulk = service.ingest_all_from_source_root(
            payload=CurriculumBulkIngestRequest(source_root=source_root)
        )
        discovered_scopes = bulk.discovered_scopes
        print(
            f"  - scopes discovered={bulk.discovered_scopes}, "
            f"success={bulk.succeeded_scopes}, failed={bulk.failed_scopes}"
        )

        seen_failures: set[str] = set()
        for item in bulk.results:
            if item.status == "failed":
                message = (item.message or "").strip() or "Scope ingestion failed without a detailed error message."
                record = f"{item.subject} {item.sss_level} term {item.term}: {message}"
                if record in seen_failures:
                    continue
                seen_failures.add(record)
                failed_messages.append(record)

        print("[5/7] Approving ingested versions...")
        for version_id in bulk.approve_ready_version_ids:
            service.approve_version(
                version_id=version_id,
                payload=CurriculumVersionActionRequest(actor_user_id=None),
            )
            approved_count += 1
        print(f"  - approved versions={approved_count}")
    finally:
        db.close()

    return discovered_scopes, approved_count, failed_messages


def _cleanup_failed_versions(*, keep_failed_versions: bool) -> None:
    if keep_failed_versions:
        print("[6/7] Keeping failed versions for audit (skip cleanup).")
        return

    print("[6/7] Removing non-published and duplicate published versions...")
    from backend.core.config import settings
    from backend.core.database import SessionLocal

    db = SessionLocal()
    try:
        non_published_rows = db.execute(
            text("SELECT id::text FROM curriculum_versions WHERE status <> 'published'")
        ).fetchall()
        non_published_ids = [row[0] for row in non_published_rows]

        published_rows = db.execute(
            text(
                """
                SELECT id::text, subject, sss_level, term, updated_at
                FROM curriculum_versions
                WHERE status = 'published'
                ORDER BY subject, sss_level, term, updated_at DESC
                """
            )
        ).fetchall()
    finally:
        db.close()

    duplicate_published_ids: list[str] = []
    seen_scope: set[tuple[str, str, int]] = set()
    for version_id, subject, sss_level, term, _ in published_rows:
        scope = (str(subject), str(sss_level), int(term))
        if scope in seen_scope:
            duplicate_published_ids.append(str(version_id))
        else:
            seen_scope.add(scope)

    to_remove = list(dict.fromkeys(non_published_ids + duplicate_published_ids))
    if not to_remove:
        print("  - no stale versions found")
        return

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=float(os.getenv("QDRANT_TIMEOUT_SECONDS", "240")),
        )
        for version_id in to_remove:
            selector = Filter(
                must=[FieldCondition(key="curriculum_version_id", match=MatchValue(value=version_id))]
            )
            client.delete(collection_name=settings.qdrant_collection, points_selector=selector, wait=True)
    except Exception as exc:
        print(f"  - warning: could not remove stale Qdrant points ({exc})")

    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM curriculum_versions WHERE id::text = ANY(:ids)"), {"ids": to_remove})
        db.commit()
        print(f"  - removed stale version rows={len(to_remove)}")
    finally:
        db.close()


def _maybe_seed_neo4j(*, seed_neo4j: bool) -> None:
    if not seed_neo4j:
        print("[7/7] Neo4j reseed skipped.")
        return

    print("[7/7] Seeding Neo4j graph from Postgres...")
    try:
        from backend.scripts.seed_neo4j_graph import run as seed_neo4j_run

        seed_neo4j_run()
    except Exception as exc:
        print(f"  - warning: Neo4j seed failed ({exc})")


def _print_final_summary() -> None:
    from backend.core.config import settings
    from backend.core.database import SessionLocal

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                """
                SELECT subject, sss_level, term, status, count(*)
                FROM curriculum_versions
                GROUP BY subject, sss_level, term, status
                ORDER BY subject, sss_level, term, status
                """
            )
        ).fetchall()
        print("Final version status by scope:")
        for row in rows:
            print(f"  - {row[0]} {row[1]} term {row[2]} [{row[3]}] x{row[4]}")

        public_tables = set(_list_public_tables(db))

        def _count(name: str) -> int | None:
            if name not in public_tables:
                return None
            result = db.execute(text(f"SELECT count(*) FROM {_quote_ident(name)}")).scalar()
            return int(result or 0)

        tracked_tables = [
            "subjects",
            "topics",
            "lessons",
            "lesson_blocks",
            "personalized_lessons",
            "curriculum_versions",
            "curriculum_topic_maps",
            "curriculum_ingestion_jobs",
            "users",
            "student_profiles",
            "learning_preferences",
            "activity_logs",
            "tutor_sessions",
            "tutor_messages",
            "quizzes",
            "quiz_questions",
            "quiz_attempts",
        ]
        print("Postgres table counts:")
        for table_name in tracked_tables:
            value = _count(table_name)
            if value is not None:
                print(f"  - {table_name}={value}")
    finally:
        db.close()

    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
            timeout=float(os.getenv("QDRANT_TIMEOUT_SECONDS", "240")),
        )
        info = client.get_collection(settings.qdrant_collection)
        print(f"Qdrant points_count={info.points_count} (collection={settings.qdrant_collection})")
    except Exception as exc:
        print(f"Qdrant summary warning: {exc}")


def main() -> int:
    args = _parse_args()
    _configure_runtime(args)

    try:
        _validate_canonical_json_if_present(args)
        if args.full_db_reset:
            _full_postgres_reset()
        _run_seed_lessons(args)
        _clear_curriculum_tables()
        _clear_qdrant_collection()
        discovered_scopes, approved_count, failed_messages = _bulk_ingest_and_approve(args.source_root)
        _cleanup_failed_versions(keep_failed_versions=args.keep_failed_versions)
        _maybe_seed_neo4j(seed_neo4j=args.seed_neo4j)
        _print_final_summary()
    except Exception as exc:
        print(f"Reset/reseed failed: {exc}", file=sys.stderr)
        return 1

    if failed_messages:
        print("Ingestion failures encountered:")
        for message in failed_messages:
            print(f"  - {message}")
        print(
            "Completed with partial failures. "
            "Re-run for remaining scopes or increase Qdrant timeout/batch tuning."
        )
    else:
        print(
            f"Reset/reseed completed successfully. "
            f"discovered_scopes={discovered_scopes}, approved_versions={approved_count}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
