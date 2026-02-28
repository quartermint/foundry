from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    queue_item_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("queue_items.id", ondelete="CASCADE"), nullable=False
    )
    printer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("printers.id", ondelete="CASCADE"), nullable=False
    )
    outcome: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    filament_used_g: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    settings_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "queue_item_id": self.queue_item_id,
            "printer_id": self.printer_id,
            "outcome": self.outcome,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "filament_used_g": self.filament_used_g,
            "settings_snapshot": self.settings_snapshot,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
