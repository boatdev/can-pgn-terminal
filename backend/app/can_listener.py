"""
CAN bus listener — reads and decodes NMEA 2000 messages in a background thread.
"""

import asyncio
import logging
from typing import Any

from app.config import CAN_BITRATE, CAN_DEVICE
from app.stores import device_store, history_store, raw_store, value_cache

log = logging.getLogger(__name__)


def _describe_device_from_pgn(decoded: Any) -> tuple[str, str, str]:
    """Extract manufacturer, device class, and function from a decoded PGN."""
    manufacturer = ""
    device_class = ""
    device_function = ""

    attrs = dir(decoded) if hasattr(decoded, "__dict__") else []

    # Manufacturer Code
    for name in ("Manufacturer_Code", "manufacturer_code", "manufacturerCode"):
        if name in attrs:
            val = getattr(decoded, name, None)
            if val is not None:
                manufacturer = str(val)
            break

    # Device Class
    for name in ("Device_Class", "device_class", "deviceClass"):
        if name in attrs:
            val = getattr(decoded, name, None)
            if val is not None:
                device_class = str(val)
            break

    # Device Function
    for name in ("Device_Function", "device_function", "deviceFunction", "Industry_Group"):
        if name in attrs:
            val = getattr(decoded, name, None)
            if val is not None:
                device_function = str(val)
            break

    return manufacturer, device_class, device_function


def _is_nmea_field(obj: Any) -> bool:
    """Check if an object looks like an NMEA2000 field (has id, name, value)."""
    return hasattr(obj, "id") and hasattr(obj, "name") and hasattr(obj, "value")


def _get_skip_field_types() -> set:
    """Return field types to skip (reserved/spare)."""
    try:
        from nmea2000 import FieldTypes  # type: ignore[import-untyped]  # pylint: disable=import-error  # noqa: I001
        return {FieldTypes.RESERVED, FieldTypes.SPARE}
    except ImportError:
        return set()


def _extract_pgn_fields(decoded: Any) -> list[dict]:
    """Extract public fields from a decoded PGN message."""
    skip = {
        "PGN", "description", "timestamp", "data", "arbitration_id",
        "destination", "source", "id", "priority", "raw_can_data",
        "source_iso_name", "ttl", "pgn",
    }
    enriched: list[dict] = []
    skip_field_types = _get_skip_field_types()

    for attr_name in dir(decoded):
        if attr_name.startswith("_") or attr_name in skip:
            continue
        try:
            val = getattr(decoded, attr_name, None)
            if val is None or callable(val):
                continue

            if _is_nmea_field(val):
                if hasattr(val, "type") and val.type in skip_field_types:
                    continue
                if val.value is None:
                    continue
                enriched.append({
                    "key": str(val.id),
                    "name": str(val.name) if val.name else str(val.id),
                    "value": val.value,
                    "unit": str(val.unit_of_measurement) if val.unit_of_measurement else "",  # noqa: E501
                })
            elif isinstance(val, (int, float, str, bool)):
                enriched.append({"key": attr_name, "name": attr_name, "value": val, "unit": ""})
            elif isinstance(val, (list, tuple)):
                if val and _is_nmea_field(val[0]):
                    for field in val:
                        if not _is_nmea_field(field):
                            continue
                        if hasattr(field, "type") and field.type in skip_field_types:
                            continue
                        if field.value is None:
                            continue
                        enriched.append({
                            "key": str(field.id),
                            "name": str(field.name) if field.name else str(field.id),
                            "value": field.value,
                            "unit": str(field.unit_of_measurement) if field.unit_of_measurement else "",  # noqa: E501
                        })
                else:
                    try:
                        enriched.append({
                            "key": attr_name,
                            "name": attr_name,
                            "value": [str(v) for v in val],
                            "unit": "",
                        })
                    except Exception:
                        enriched.append({
                            "key": attr_name,
                            "name": attr_name,
                            "value": str(val),
                            "unit": "",
                        })
            else:
                # Complex objects — attempt best-effort serialisation
                if hasattr(val, "name") and hasattr(val, "value"):
                    enriched.append({
                        "key": attr_name,
                        "name": str(val.name),
                        "value": val.value,
                        "unit": str(val.unit_of_measurement) if hasattr(val, "unit_of_measurement") and val.unit_of_measurement else "",  # noqa: E501
                    })
                elif hasattr(val, "name"):
                    enriched.append({"key": attr_name, "name": str(val.name), "value": str(val), "unit": ""})  # noqa: E501
                elif hasattr(val, "__dict__"):
                    sub = {k: v if isinstance(v, (int, float, str, bool)) else str(v) for k, v in val.__dict__.items()}  # noqa: E501
                    enriched.append({"key": attr_name, "name": attr_name, "value": sub, "unit": ""})  # noqa: E501
                else:
                    enriched.append({"key": attr_name, "name": attr_name, "value": str(val), "unit": ""})  # noqa: E501
        except Exception:
            continue

    return enriched


def can_listener_loop() -> None:
    """Background thread that reads CAN bus messages and updates stores.

    Runs forever. If the CAN device is unavailable, sets error flags and exits.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    if not CAN_DEVICE:
        msg = "CAN_DEVICE is not set. Unable to connect to CAN bus."
        log.warning(msg)
        device_store.can_connected = False
        device_store.can_error = msg
        return

    try:
        import can  # type: ignore[import-untyped]  # pylint: disable=import-error  # noqa: I001
        from nmea2000 import NMEA2000Decoder  # type: ignore[import-untyped]  # pylint: disable=import-error  # noqa: I001

        log.info(
            "Connecting to CAN bus: interface=slcan, channel=%s, bitrate=%d",
            CAN_DEVICE, CAN_BITRATE,
        )
        bus = can.interface.Bus(interface="slcan", channel=CAN_DEVICE, bitrate=CAN_BITRATE)
        decoder = NMEA2000Decoder()
        device_store.can_connected = True
        device_store.can_error = ""
        log.info("CAN bus connected — live mode")

        for msg in bus:
            try:
                decoded = decoder.decode(msg)
                source_id = msg.arbitration_id & 0xFF
                pgn = decoded.PGN if hasattr(decoded, "PGN") else 0

                # Skip ISO Address Claim (internal)
                if pgn == 60928:
                    continue

                description = decoded.description if hasattr(decoded, "description") else ""
                manufacturer, device_class, device_function = _describe_device_from_pgn(decoded)

                device_store.upsert(
                    source_id, pgn, description, manufacturer, device_class, device_function,
                )

                priority = (msg.arbitration_id >> 26) & 0x7
                raw_data = " ".join(f"{b:02X}" for b in msg.data)
                pgn_fields = _extract_pgn_fields(decoded) if decoded else []

                if pgn_fields:
                    value_cache.set(source_id, pgn, pgn_fields)
                    history_store.add(source_id, pgn, pgn_fields)

                raw_store.add(
                    timestamp=msg.timestamp,
                    source_id=source_id,
                    pgn=pgn,
                    priority=priority,
                    raw_data=raw_data,
                    description=description,
                    pgn_fields=pgn_fields,
                )
            except Exception:
                log.debug("Error decoding message", exc_info=True)

    except Exception as e:
        err_msg = f"CAN bus unavailable: {e}"
        log.warning(err_msg)
        device_store.can_connected = False
        device_store.can_error = err_msg
