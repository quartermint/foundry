from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Printer(Base):
    __tablename__ = "printers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    brand: Mapped[str] = mapped_column(String(64), default="Bambu Lab")
    model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    ip: Mapped[str] = mapped_column(String(45), nullable=False)
    serial: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    access_code: Mapped[str] = mapped_column(String(16), nullable=False)
    nozzle_mm: Mapped[float] = mapped_column(Float, default=0.4)
    bed_x_mm: Mapped[int] = mapped_column(Integer, default=256)
    bed_y_mm: Mapped[int] = mapped_column(Integer, default=256)
    capable_materials: Mapped[str] = mapped_column(Text, default='["PLA"]')
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "brand": self.brand,
            "model": self.model,
            "ip": self.ip,
            "serial": self.serial,
            "nozzle_mm": self.nozzle_mm,
            "bed_x_mm": self.bed_x_mm,
            "bed_y_mm": self.bed_y_mm,
            "capable_materials": self.capable_materials,
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
