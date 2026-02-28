import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import settings
from app.database import get_session, init_db
from app.models.printer import Printer
from app.routers import printers, ws, queue, history, discovery, knowledge, generate, plate
from app.services.bambu_mqtt import mqtt_service
from app.jobs.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Foundry backend starting up")
    await init_db()
    logger.info("Database initialized")

    # Connect MQTT for all enabled printers
    from app.database import async_session_factory

    async with async_session_factory() as session:
        result = await session.execute(
            select(Printer).where(Printer.enabled == True)  # noqa: E712
        )
        printers_list = result.scalars().all()
        for p in printers_list:
            try:
                await mqtt_service.connect_printer(p.id, p.ip, p.serial, p.access_code)
            except Exception:
                logger.exception("Failed to connect MQTT for printer %d", p.id)

    # Start background jobs
    start_scheduler()

    logger.info("Startup complete")
    yield

    # Shutdown
    logger.info("Foundry backend shutting down")
    stop_scheduler()
    for printer_id in list(mqtt_service._clients.keys()):
        await mqtt_service.disconnect_printer(printer_id)
    logger.info("All MQTT connections closed")


app = FastAPI(title="Foundry", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(printers.router)
app.include_router(ws.router)
app.include_router(queue.router)
app.include_router(history.router)
app.include_router(discovery.router)
app.include_router(knowledge.router)
app.include_router(generate.router)
app.include_router(plate.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Mount frontend static files in production
frontend_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
