"""System health endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.services.system_health_service import SystemHealthService
from backend.services.demo_validation_service import DemoValidationService
from backend.core.database import get_db

router = APIRouter(prefix="/system", tags=["System"])

_health_service = SystemHealthService()


@router.get("/health")
def health():
    """Return deep health checks across core dependencies.

    Checks include active connectivity for Postgres, Redis, Neo4j, and Qdrant.
    LLM/API readiness is also reported based on configured ai-core/LLM settings.
    """
    return _health_service.snapshot()


@router.get("/demo")
def demo_readiness(db: Session = Depends(get_db)):
    """Return demo readiness validation for the configured demo scope."""
    return DemoValidationService(db).snapshot()
