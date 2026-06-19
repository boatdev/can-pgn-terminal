"""
CAN bus listener — reads and decodes NMEA 2000 messages in a background thread.
"""

import asyncio
import logging
from typing import Any

from app.config import CAN_BITRATE, CAN_DEVICE
from app.resources import manufacturer_name
from app.stores import device_store, history_store, raw_store, value_cache

log = logging.getLogger(__name__)


def _nmea_field_value(field: Any) -> Any:
    """Get the effective value from an NMEA field, preferring raw_value when value is None."""
    if not hasattr(field, "raw_value"):
        return field.value
    # For LOOKUP/INDIRECT_LOOKUP fields and any field where value is None,
    # use raw_value to get the numeric code
    if field.value is None:
        return field.raw_value
    return field.value


def _describe_device_from_pgn(decoded: Any) -> tuple[str, str, str]:
    """Extract manufacturer, device class, and function from a decoded PGN.

    All data fields live inside decoded.fields (list of NMEA Field objects).
    """
    manufacturer = ""
    device_class = ""
    device_function = ""

    # Build lookup by field id/name (lowercase + underscore)
    field_values: dict[str, Any] = {}
    for field in getattr(decoded, "fields", []):
        if not _is_nmea_field(field):
            continue
        field_id = _safe_str(field.id).lower().replace(" ", "_")
        field_name = _safe_str(field.name).lower().replace(" ", "_") if field.name else ""
        fv = _nmea_field_value(field)
        for key in {field_id, field_name}:
            if key:
                field_values[key] = fv

    # Manufacturer Code — try all possible field name variations
    for name in ("manufacturercode", "manufacturer_code", "manufacturer_code_field"):
        if name in field_values:
            try:
                code = int(field_values[name])
                manufacturer = manufacturer_name(code)
            except (ValueError, TypeError):
                manufacturer = _safe_str(field_values[name])
            break

    # Device Class
    for name in ("deviceclass", "device_class", "deviceClass", "DeviceClass"):
        if name in field_values:
            device_class = _safe_str(field_values[name])
            break

    # Device Function (also try industry_group which holds industry category)
    for name in ("devicefunction", "device_function", "deviceFunction", "DeviceFunction",
                 "industrygroup", "industry_group", "industryGroup", "IndustryGroup"):
        if name in field_values:
            device_function = _safe_str(field_values[name])
            break

    return manufacturer, device_class, device_function


def _safe_str(value: Any) -> str:
    """Safely convert any value to a valid UTF-8 string.

    Replaces invalid byte sequences to prevent Pydantic serialization errors
    when NMEA 2000 field names or units contain non-UTF-8 data.
    """
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    if isinstance(value, str):
        # Re-encode to filter out lone surrogates and invalid sequences
        return value.encode('utf-8', errors='replace').decode('utf-8')
    return str(value)


def _extract_pgn60928_metadata(decoded: Any) -> dict:
    """Extract manufacturer, device class, and function from PGN 60928.

    All data fields live inside decoded.fields (list of NMEA Field objects).
    """
    result: dict = {}

    # Build lookup by field id/name (lowercase + underscore)
    field_values: dict[str, Any] = {}
    for field in getattr(decoded, "fields", []):
        if not _is_nmea_field(field):
            continue
        field_id = _safe_str(field.id).lower().replace(" ", "_")
        field_name = _safe_str(field.name).lower().replace(" ", "_") if field.name else ""
        fv = _nmea_field_value(field)
        for key in {field_id, field_name}:
            if key:
                field_values[key] = fv

    # Manufacturer — try all possible field name variations
    for name in ("manufacturercode", "manufacturer_code", "manufacturerCode", "ManufacturerCode",
                 "manufacturer_code_field"):
        if name in field_values:
            try:
                code = int(field_values[name])
                result["manufacturer"] = manufacturer_name(code)
            except (ValueError, TypeError):
                result["manufacturer"] = _safe_str(field_values[name])
            break

    # Device Class
    for name in ("deviceclass", "device_class", "deviceClass", "DeviceClass"):
        if name in field_values:
            result["device_class"] = _safe_str(field_values[name])
            break

    # Device Function
    for name in ("devicefunction", "device_function", "deviceFunction", "DeviceFunction",
                 "industrygroup", "industry_group", "industryGroup", "IndustryGroup"):
        if name in field_values:
            result["device_function"] = _safe_str(field_values[name])
            break

    # Remove empty string entries so store.update_metadata() preserves existing values
    return {k: v for k, v in result.items() if v}


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
                    "key": _safe_str(val.id),
                    "name": _safe_str(val.name) if val.name else _safe_str(val.id),
                    "value": _safe_str(val.value) if isinstance(val.value, bytes) else val.value,
                    "unit": _safe_str(val.unit_of_measurement) if val.unit_of_measurement else "",
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
                            "key": _safe_str(field.id),
                            "name": _safe_str(field.name) if field.name else _safe_str(field.id),
                            "value": _safe_str(field.value) if isinstance(field.value, bytes) else field.value,
                            "unit": _safe_str(field.unit_of_measurement) if field.unit_of_measurement else "",
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
                        "key": _safe_str(attr_name),
                        "name": _safe_str(val.name),
                        "value": _safe_str(val.value) if isinstance(val.value, bytes) else val.value,
                        "unit": _safe_str(val.unit_of_measurement) if hasattr(val, "unit_of_measurement") and val.unit_of_measurement else "",
                    })
                elif hasattr(val, "name"):
                    enriched.append({"key": _safe_str(attr_name), "name": _safe_str(val.name), "value": _safe_str(val), "unit": ""})
                elif hasattr(val, "__dict__"):
                    sub = {_safe_str(k): v if isinstance(v, (int, float, str, bool)) else _safe_str(v) for k, v in val.__dict__.items()}
                    enriched.append({"key": _safe_str(attr_name), "name": _safe_str(attr_name), "value": sub, "unit": ""})
                else:
                    enriched.append({"key": _safe_str(attr_name), "name": _safe_str(attr_name), "value": _safe_str(val), "unit": ""})
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

                # Log ALL PGNs with their decoded attributes and field values for debugging
                decoded_attrs = [a for a in dir(decoded) if not a.startswith("_")]
                if hasattr(decoded, "fields"):
                    field_summary = {f.id: (f.value, f.raw_value if hasattr(f, "raw_value") else None) for f in decoded.fields}
                else:
                    field_summary = {}
                log.info("PGN %d from src=%d, attrs=%s, fields=%s", pgn, source_id, decoded_attrs, field_summary)

                if pgn == 60928:
                    meta = _extract_pgn60928_metadata(decoded)
                    log.info("PGN 60928 metadata: %s", meta)
                    if meta:
                        device_store.upsert(
                            source_id=source_id,
                            pgn=pgn,
                            description="ISO Address Claim",
                            manufacturer=meta.get("manufacturer", ""),
                            device_class=meta.get("device_class", ""),
                            device_function=meta.get("device_function", ""),
                        )
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
                log.exception("Error decoding message")

    except Exception as e:
        err_msg = f"CAN bus unavailable: {e}"
        log.warning(err_msg)
        device_store.can_connected = False
        device_store.can_error = err_msg