from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Tip(Base):
    __tablename__ = "tips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # reddit, youtube, manual
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    materials: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    printer_models: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "content": self.content,
            "tags": self.tags,
            "materials": self.materials,
            "printer_models": self.printer_models,
            "upvotes": self.upvotes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
