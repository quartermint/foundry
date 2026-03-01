from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QueueItem(Base):
    __tablename__ = "queue_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_platform: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    model_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sliced_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending_approval")
    printer_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("printers.id", ondelete="SET NULL"), nullable=True
    )
    material: Mapped[str] = mapped_column(String(32), default="PLA")
    filament_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    print_time_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    plate_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    generation_backend: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_platform": self.source_platform,
            "model_path": self.model_path,
            "sliced_path": self.sliced_path,
            "thumbnail_path": self.thumbnail_path,
            "status": self.status,
            "printer_id": self.printer_id,
            "material": self.material,
            "filament_g": self.filament_g,
            "print_time_min": self.print_time_min,
            "plate_id": self.plate_id,
            "generation_backend": self.generation_backend,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
