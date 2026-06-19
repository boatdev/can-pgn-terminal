"""
FastAPI application for NMEA 2000 Web Terminal.

Provides REST API endpoints to query detected NMEA 2000 devices,
raw CAN messages, decoded PGN values, and time-series history.
"""

import logging
import math
import threading
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI  # pylint: disable=import-error
from fastapi.middleware.cors import CORSMiddleware  # pylint: disable=import-error
from fastapi.staticfiles import StaticFiles  # pylint: disable=import-error

from app.can_listener import can_listener_loop
from app.config import (
    CAN_DEVICE,
    DEVICE_CLEANUP_INTERVAL,
    DEVICE_TIMEOUT_SECONDS,
)
from app.models import DevicesResponse, RawMessagesResponse
from app.stores import device_store, history_store, raw_store, value_cache

# Configure logging to show INFO messages from our app
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
log = logging.getLogger(__name__)


def _device_cleanup_loop() -> None:
    """Background thread that periodically removes stale devices."""
    log.info(
        "Device cleanup loop started (timeout=%ds, interval=%ds)",
        DEVICE_TIMEOUT_SECONDS, DEVICE_CLEANUP_INTERVAL,
    )
    while True:
        time.sleep(DEVICE_CLEANUP_INTERVAL)
        try:
            device_store.cleanup_stale(DEVICE_TIMEOUT_SECONDS)
        except Exception:
            log.debug("Error in device cleanup", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background threads on application startup."""
    # Start CAN bus listener
    t = threading.Thread(target=can_listener_loop, daemon=True)
    t.start()
    log.info("CAN listener started (device=%s)", CAN_DEVICE or "none")

    # Start device cleanup thread
    cleanup = threading.Thread(target=_device_cleanup_loop, daemon=True)
    cleanup.start()
    log.info("Device cleanup thread started")

    yield


app = FastAPI(title="NMEA 2000 Web Terminal", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/devices", response_model=DevicesResponse)
async def get_devices() -> DevicesResponse:
    """Return all detected NMEA 2000 devices."""
    device_store.cleanup_stale(DEVICE_TIMEOUT_SECONDS)
    devices = device_store.list_devices()
    return DevicesResponse(
        devices=devices,
        total=len(devices),
        mode="live",
        can_connected=device_store.can_connected,
        can_error=device_store.can_error,
    )


@app.get("/api/health")
async def health() -> dict:
    """Health check endpoint."""
    return {
        "status": "ok",
        "mode": "live",
        "can_connected": device_store.can_connected,
        "can_error": device_store.can_error,
    }


@app.get("/api/values")
async def get_values() -> list[dict]:
    """Return cached decoded PGN values."""
    return [v for v in value_cache.get_all() if v.get("pgn") != 60928]


@app.get("/api/history")
async def get_history(
    source_id: int,
    pgn: int,
    field_key: str,
    window: int = 300,
) -> list[dict]:
    """Return time-series history for a specific PGN field.

    Args:
        source_id: Device source address.
        pgn: Parameter Group Number.
        field_key: Field identifier (e.g. "Wind_Speed", "Heading").
        window: Time window in seconds (default 300 = 5 min).
    """
    return history_store.get_history(source_id, pgn, field_key, window_seconds=window)


@app.get("/api/raw-messages", response_model=RawMessagesResponse)
async def get_raw_messages(since: Optional[float] = None) -> RawMessagesResponse:
    """Return raw CAN message buffer.

    Args:
        since: Optional epoch timestamp — return only newer messages.
    """
    messages = [m for m in raw_store.get_messages(since=since) if m.pgn != 60928]
    return RawMessagesResponse(
        messages=messages,
        total=len(messages),
        mode="live",
    )


# Serve static frontend files
import os  # noqa: E402

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
FRONTEND_DIR = os.path.normpath(FRONTEND_DIR)
if os.path.isdir(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="static")
    log.info("Serving static files from %s", FRONTEND_DIR)
else:
    log.warning("Frontend dist directory not found at %s", FRONTEND_DIR)