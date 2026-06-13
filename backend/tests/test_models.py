"""Tests for Pydantic models."""
# pylint: disable=import-error

from app.models import DevicesResponse, NMEADevice, RawMessage, RawMessagesResponse


def test_nmea_device_defaults():
    """NMEADevice should accept valid fields."""
    dev = NMEADevice(
        source_id=42,
        pgn=130306,
        description="Wind Sensor",
        manufacturer="Airmar",
        device_class="Sensor",
        device_function="Wind",
        first_seen=100.0,
        last_seen=200.0,
        message_count=5,
    )
    assert dev.source_id == 42
    assert dev.pgn == 130306
    assert dev.description == "Wind Sensor"


def test_devices_response_defaults():
    """DevicesResponse should have sensible defaults."""
    resp = DevicesResponse(devices=[], total=0, mode="live")
    assert resp.can_connected is False
    assert resp.can_error == ""


def test_raw_message_optional_pgn_fields():
    """RawMessage should accept pgn_fields as None."""
    msg = RawMessage(
        timestamp=100.0,
        source_id=42,
        pgn=130306,
        priority=2,
        raw_data="00 11 22 33",
        description="test",
        pgn_fields=None,
    )
    assert msg.pgn_fields is None


def test_raw_messages_response():
    """RawMessagesResponse should hold a list of RawMessage."""
    msgs = [
        RawMessage(
            timestamp=100.0, source_id=1, pgn=2, priority=3,
            raw_data="AA", description="",
        )
    ]
    resp = RawMessagesResponse(messages=msgs, total=1, mode="live")
    assert resp.total == 1
    assert len(resp.messages) == 1
