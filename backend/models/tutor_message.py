import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base
from backend.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class TutorMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tutor_messages"
    __table_args__ = (
        CheckConstraint("role IN ('student','assistant','system')", name="ck_tutor_messages_role"),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tutor_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    session: Mapped["TutorSession"] = relationship("TutorSession", back_populates="messages")
