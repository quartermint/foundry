from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DiscoveryResult(Base):
    __tablename__ = "discovery_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_platform: Mapped[str] = mapped_column(String(64), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_type: Mapped[str] = mapped_column(String(16), default="stl")
    has_bambu_profile: Mapped[bool] = mapped_column(Boolean, default=False)
    downloads: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    search_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "source_url": self.source_url,
            "source_platform": self.source_platform,
            "thumbnail_url": self.thumbnail_url,
            "file_type": self.file_type,
            "has_bambu_profile": self.has_bambu_profile,
            "downloads": self.downloads,
            "likes": self.likes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
