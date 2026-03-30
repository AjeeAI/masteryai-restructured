from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import UUIDPrimaryKeyMixin, TimestampMixin
from backend.core.database import Base

class Subject(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "subjects"

    # "math" | "english" | "civic"
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)