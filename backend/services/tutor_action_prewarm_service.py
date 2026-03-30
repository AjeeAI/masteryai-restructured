from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from backend.core.config import settings
from backend.schemas.tutor_schema import TutorDrillIn, TutorPrereqBridgeIn, TutorRecapIn
from backend.services.tutor_action_cache import TutorActionCacheKey, get_cached_action, set_cached_action
from backend.services.tutor_orchestration_service import TutorOrchestrationService, TutorProviderUnavailableError

logger = logging.getLogger(__name__)


class TutorActionPrewarmService:
    @staticmethod
    def _run_coro(coro) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
            return
        loop.create_task(coro)

    @classmethod
    def prewarm(
        cls,
        *,
        student_id: UUID,
        session_id: UUID,
        subject: str,
        sss_level: str,
        term: int,
        topic_id: UUID,
        actions: list[str] | None = None,
    ) -> None:
        if not settings.tutor_action_prewarm_enabled:
            return
        actions = actions or ["recap", "prereq-bridge", "drill-easy"]
        service = TutorOrchestrationService()

        async def _run() -> None:
            for action in actions:
                try:
                    if action == "recap":
                        key = TutorActionCacheKey(action_id="recap", session_id=session_id, topic_id=topic_id)
                        if get_cached_action(key):
                            continue
                        payload = TutorRecapIn(
                            student_id=student_id,
                            session_id=session_id,
                            subject=subject,
                            sss_level=sss_level,
                            term=int(term),
                            topic_id=topic_id,
                        )
                        response = await service.recap(payload)
                        set_cached_action(key, response)
                    elif action == "prereq-bridge":
                        key = TutorActionCacheKey(action_id="prereq-bridge", session_id=session_id, topic_id=topic_id)
                        if get_cached_action(key):
                            continue
                        payload = TutorPrereqBridgeIn(
                            student_id=student_id,
                            session_id=session_id,
                            subject=subject,
                            sss_level=sss_level,
                            term=int(term),
                            topic_id=topic_id,
                        )
                        response = await service.prereq_bridge(payload)
                        set_cached_action(key, response)
                    elif action == "drill-easy":
                        key = TutorActionCacheKey(
                            action_id="drill",
                            session_id=session_id,
                            topic_id=topic_id,
                            difficulty="easy",
                        )
                        if get_cached_action(key):
                            continue
                        payload = TutorDrillIn(
                            student_id=student_id,
                            session_id=session_id,
                            subject=subject,
                            sss_level=sss_level,
                            term=int(term),
                            topic_id=topic_id,
                            difficulty="easy",
                        )
                        response = await service.drill(payload)
                        set_cached_action(key, response)
                except TutorProviderUnavailableError as exc:
                    logger.warning("tutor.action.prewarm_unavailable action=%s detail=%s", action, exc)
                except Exception as exc:  # pragma: no cover - best effort prewarm
                    logger.warning("tutor.action.prewarm_failed action=%s detail=%s", action, exc)

        cls._run_coro(_run())
