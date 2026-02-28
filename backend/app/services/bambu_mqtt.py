import asyncio
import json
import logging
import ssl
import threading
from collections.abc import Callable

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class BambuMQTTService:
    def __init__(self):
        self._clients: dict[int, mqtt.Client] = {}
        self._serials: dict[int, str] = {}
        self._status_cache: dict[int, dict] = {}
        self._subscribers: dict[int, list[Callable]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.get_event_loop()
        return self._loop

    def _on_connect(self, client: mqtt.Client, userdata: dict, flags, rc, properties=None):
        printer_id = userdata["printer_id"]
        serial = userdata["serial"]
        if rc == 0:
            logger.info("MQTT connected to printer %d (serial=%s)", printer_id, serial)
            client.subscribe(f"device/{serial}/report")
        else:
            logger.error("MQTT connection failed for printer %d: rc=%d", printer_id, rc)

    def _on_message(self, client: mqtt.Client, userdata: dict, msg: mqtt.MQTTMessage):
        printer_id = userdata["printer_id"]
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("Invalid MQTT payload from printer %d", printer_id)
            return

        if "print" in payload:
            status_data = payload["print"]
        else:
            status_data = payload

        self._status_cache[printer_id] = status_data

        subscribers = self._subscribers.get(printer_id, [])
        for callback in subscribers:
            try:
                loop = self._get_loop()
                loop.call_soon_threadsafe(
                    asyncio.ensure_future,
                    callback(status_data),
                )
            except Exception:
                logger.exception("Error notifying subscriber for printer %d", printer_id)

    def _on_disconnect(self, client: mqtt.Client, userdata: dict, rc, properties=None):
        printer_id = userdata["printer_id"]
        if rc != 0:
            logger.warning("MQTT unexpected disconnect from printer %d: rc=%d", printer_id, rc)

    async def connect_printer(
        self, printer_id: int, ip: str, serial: str, access_code: str
    ):
        if printer_id in self._clients:
            await self.disconnect_printer(printer_id)

        self._loop = asyncio.get_event_loop()

        userdata = {"printer_id": printer_id, "serial": serial}
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"foundry-{printer_id}",
            userdata=userdata,
            protocol=mqtt.MQTTv311,
        )

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE
        client.tls_set_context(ssl_ctx)

        client.username_pw_set("bblp", access_code)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.on_disconnect = self._on_disconnect

        self._clients[printer_id] = client
        self._serials[printer_id] = serial

        def _connect_thread():
            try:
                client.connect(ip, port=8883, keepalive=60)
                client.loop_start()
            except Exception:
                logger.exception("Failed to connect MQTT to printer %d at %s", printer_id, ip)

        thread = threading.Thread(target=_connect_thread, daemon=True)
        thread.start()

        logger.info("MQTT connect initiated for printer %d at %s:8883", printer_id, ip)

    async def disconnect_printer(self, printer_id: int):
        client = self._clients.pop(printer_id, None)
        self._serials.pop(printer_id, None)
        self._status_cache.pop(printer_id, None)
        self._subscribers.pop(printer_id, None)
        if client:
            client.loop_stop()
            client.disconnect()
            logger.info("MQTT disconnected from printer %d", printer_id)

    def get_status(self, printer_id: int) -> dict | None:
        return self._status_cache.get(printer_id)

    async def send_print_command(self, printer_id: int, filename: str):
        client = self._clients.get(printer_id)
        serial = self._serials.get(printer_id)
        if not client or not serial:
            raise ValueError(f"Printer {printer_id} is not connected via MQTT")

        command = {
            "print": {
                "command": "project_file",
                "param": f"Metadata/plate_1.gcode",
                "subtask_name": filename,
                "url": f"ftp:///{filename}",
                "bed_type": "auto",
                "timelapse": False,
                "bed_leveling": True,
                "flow_cali": True,
                "vibration_cali": True,
                "layer_inspect": False,
                "use_ams": False,
            }
        }

        topic = f"device/{serial}/request"
        result = client.publish(topic, json.dumps(command))
        logger.info(
            "Sent print command for '%s' to printer %d (topic=%s, rc=%s)",
            filename, printer_id, topic, result.rc,
        )
        return result.rc == mqtt.MQTT_ERR_SUCCESS

    def add_subscriber(self, printer_id: int, callback: Callable):
        if printer_id not in self._subscribers:
            self._subscribers[printer_id] = []
        self._subscribers[printer_id].append(callback)

    def remove_subscriber(self, printer_id: int, callback: Callable):
        subs = self._subscribers.get(printer_id, [])
        if callback in subs:
            subs.remove(callback)


mqtt_service = BambuMQTTService()
