import json
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_token
from app.database import get_session
from app.models.printer import Printer
from app.services.bambu_ftp import upload_file
from app.services.bambu_mqtt import mqtt_service

router = APIRouter(prefix="/api/printers", tags=["printers"], dependencies=[Depends(require_token)])

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage"
SLICED_DIR = STORAGE_DIR / "sliced"


class PrinterCreate(BaseModel):
    name: str
    brand: str = "Bambu Lab"
    model: str | None = None
    ip: str
    serial: str
    access_code: str
    nozzle_mm: float = 0.4
    bed_x_mm: int = 256
    bed_y_mm: int = 256
    capable_materials: list[str] = ["PLA"]
    enabled: bool = True


class PrinterUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    model: str | None = None
    ip: str | None = None
    serial: str | None = None
    access_code: str | None = None
    nozzle_mm: float | None = None
    bed_x_mm: int | None = None
    bed_y_mm: int | None = None
    capable_materials: list[str] | None = None
    enabled: bool | None = None


class PrintCommand(BaseModel):
    filename: str


@router.get("")
async def list_printers(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Printer).order_by(Printer.id))
    printers = result.scalars().all()
    out = []
    for p in printers:
        d = p.to_dict()
        d["live_status"] = mqtt_service.get_status(p.id)
        out.append(d)
    return out


@router.get("/{printer_id}")
async def get_printer(printer_id: int, session: AsyncSession = Depends(get_session)):
    printer = await session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")
    d = printer.to_dict()
    d["live_status"] = mqtt_service.get_status(printer.id)
    return d


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_printer(body: PrinterCreate, session: AsyncSession = Depends(get_session)):
    printer = Printer(
        name=body.name,
        brand=body.brand,
        model=body.model,
        ip=body.ip,
        serial=body.serial,
        access_code=body.access_code,
        nozzle_mm=body.nozzle_mm,
        bed_x_mm=body.bed_x_mm,
        bed_y_mm=body.bed_y_mm,
        capable_materials=json.dumps(body.capable_materials),
        enabled=body.enabled,
    )
    session.add(printer)
    await session.commit()
    await session.refresh(printer)

    if printer.enabled:
        await mqtt_service.connect_printer(
            printer.id, printer.ip, printer.serial, printer.access_code
        )

    return printer.to_dict()


@router.put("/{printer_id}")
async def update_printer(
    printer_id: int, body: PrinterUpdate, session: AsyncSession = Depends(get_session)
):
    printer = await session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    update_data = body.model_dump(exclude_unset=True)
    if "capable_materials" in update_data:
        update_data["capable_materials"] = json.dumps(update_data["capable_materials"])

    reconnect_needed = any(
        k in update_data for k in ("ip", "serial", "access_code", "enabled")
    )

    for key, value in update_data.items():
        setattr(printer, key, value)

    await session.commit()
    await session.refresh(printer)

    if reconnect_needed:
        await mqtt_service.disconnect_printer(printer.id)
        if printer.enabled:
            await mqtt_service.connect_printer(
                printer.id, printer.ip, printer.serial, printer.access_code
            )

    return printer.to_dict()


@router.delete("/{printer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_printer(printer_id: int, session: AsyncSession = Depends(get_session)):
    printer = await session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    await mqtt_service.disconnect_printer(printer.id)
    await session.delete(printer)
    await session.commit()


@router.post("/{printer_id}/upload")
async def upload_to_printer(
    printer_id: int,
    file: UploadFile,
    session: AsyncSession = Depends(get_session),
):
    printer = await session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    SLICED_DIR.mkdir(parents=True, exist_ok=True)
    local_path = SLICED_DIR / file.filename
    with open(local_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    success = await upload_file(
        ip=printer.ip,
        access_code=printer.access_code,
        local_path=str(local_path),
        remote_filename=file.filename,
    )

    if not success:
        raise HTTPException(status_code=502, detail="Failed to upload file to printer via FTPS")

    return {"status": "uploaded", "filename": file.filename}


@router.post("/{printer_id}/print")
async def start_print(
    printer_id: int,
    body: PrintCommand,
    session: AsyncSession = Depends(get_session),
):
    printer = await session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    success = await mqtt_service.send_print_command(printer.id, body.filename)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to send print command via MQTT")

    return {"status": "print_started", "filename": body.filename}


@router.get("/{printer_id}/status")
async def get_printer_status(printer_id: int, session: AsyncSession = Depends(get_session)):
    printer = await session.get(Printer, printer_id)
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found")

    status_data = mqtt_service.get_status(printer.id)
    return {
        "printer_id": printer.id,
        "connected": printer.id in mqtt_service._clients,
        "status": status_data,
    }
