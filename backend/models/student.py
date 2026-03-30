import uuid
from sqlalchemy import String, Integer, ForeignKey, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from backend.core.database import Base


class StudentProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "student_profiles"

    # Links directly to users.id in auth domain
    student_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # "SSS1" | "SSS2" | "SSS3"
    sss_level: Mapped[str] = mapped_column(String(10), index=True, nullable=False)

    # 1 | 2 | 3
    active_term: Mapped[int] = mapped_column(Integer, index=True, nullable=False)

    # Relationships
    subjects: Mapped[list["StudentSubject"]] = relationship(
        "StudentSubject", back_populates="student_profile", cascade="all, delete-orphan"
    )
    preference: Mapped["LearningPreference"] = relationship(
        "LearningPreference", back_populates="student_profile", uselist=False, cascade="all, delete-orphan"
    )


class StudentSubject(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "student_subjects"
    __table_args__ = (
        UniqueConstraint("student_profile_id", "subject_id", name="uq_student_profile_subject"),
    )

    student_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False
    )
    subject_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )

    # Relationships
    student_profile: Mapped["StudentProfile"] = relationship("StudentProfile", back_populates="subjects")
    # subject relationship can be added if needed, but not required for now


class LearningPreference(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "learning_preferences"
    __table_args__ = (
        UniqueConstraint("student_profile_id", name="uq_student_profile_preference"),
    )

    student_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    # simple, standard, detailed
    explanation_depth: Mapped[str] = mapped_column(String(20), nullable=False, default="standard")

    # true/false
    examples_first: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # slow, normal, fast
    pace: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")

    # Relationship
    student_profile: Mapped["StudentProfile"] = relationship("StudentProfile", back_populates="preference")
