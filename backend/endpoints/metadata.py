"""Metadata endpoints used by frontend setup dropdowns."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.database import get_db
from backend.models.subject import Subject

router = APIRouter(prefix="/metadata", tags=["Metadata"])

SUPPORTED_SUBJECTS = ["math", "english", "civic"]
SUPPORTED_LEVELS = ["SSS1", "SSS2", "SSS3"]
SUPPORTED_TERMS = [1, 2, 3]


@router.get("/subjects")
def list_subjects(db: Session = Depends(get_db)):
    """Return supported subjects, preferring currently seeded DB values.

    This keeps dropdown contracts stable while reflecting available curriculum.
    """
    rows = db.execute(select(Subject.slug)).all()
    db_subjects = {slug for (slug,) in rows}

    # Keep contract stable for frontend dropdowns, while honoring seeded DB values when present.
    subjects = [slug for slug in SUPPORTED_SUBJECTS if slug in db_subjects] or SUPPORTED_SUBJECTS
    return {"subjects": subjects}


@router.get("/levels")
def list_levels():
    """Return static supported SSS levels and term values."""
    return {"levels": SUPPORTED_LEVELS, "terms": SUPPORTED_TERMS}
