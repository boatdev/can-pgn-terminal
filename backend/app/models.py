"""
Pydantic models for NMEA 2000 Web Terminal API.
"""

from typing import Optional

from pydantic import BaseModel  # pylint: disable=import-error,no-name-in-module


class NMEADevice(BaseModel):
    """Represents a detected NMEA 2000 device on the CAN bus."""

    source_id: int
    pgn: int
    description: str
    manufacturer: str
    device_class: str
    device_function: str
    first_seen: float
    last_seen: float
    message_count: int


class DevicesResponse(BaseModel):
    """Response model for the /api/devices endpoint."""

    devices: list[NMEADevice]
    total: int
    mode: str
    can_connected: bool = False
    can_error: str = ""


class RawMessage(BaseModel):
    """A raw CAN message with optional decoded PGN fields."""

    timestamp: float
    source_id: int
    pgn: int
    priority: int
    raw_data: str
    description: str
    pgn_fields: Optional[list] = None


class RawMessagesResponse(BaseModel):
    """Response model for the /api/raw-messages endpoint."""

    messages: list[RawMessage]
    total: int
    mode: str
