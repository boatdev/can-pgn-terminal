"""
Thread-safe data stores for devices, raw messages, and PGN values.
"""

import logging
import threading
import time
from typing import Optional

from app.config import MAX_HISTORY_SECONDS, RAW_BUFFER_SIZE
from app.models import NMEADevice, RawMessage

log = logging.getLogger(__name__)


class DeviceStore:
    """Thread-safe storage for detected NMEA 2000 devices.

    Devices are keyed by their CAN source address.
    Stale devices (no messages within timeout) are automatically cleaned up.
    """

    # PGN 60928 (ISO Address Claim) is internal and excluded from listings.
    _HIDDEN_PGNS: set[int] = {60928}

    def __init__(self) -> None:
        self._devices: dict[int, NMEADevice] = {}
        self._lock = threading.Lock()

        # Connection status
        self._can_connected: bool = False
        self._can_error: str = ""

    def upsert(
        self,
        source_id: int,
        pgn: int,
        description: str,
        manufacturer: str = "",
        device_class: str = "",
        device_function: str = "",
    ) -> None:
        """Register or update a device from a received CAN message."""
        now = time.time()
        with self._lock:
            if source_id in self._devices:
                dev = self._devices[source_id]
                dev.pgn = pgn
                dev.description = description
                dev.last_seen = now
                dev.message_count += 1
                if manufacturer:
                    dev.manufacturer = manufacturer
                if device_class:
                    dev.device_class = device_class
                if device_function:
                    dev.device_function = device_function
            else:
                self._devices[source_id] = NMEADevice(
                    source_id=source_id,
                    pgn=pgn,
                    description=description,
                    manufacturer=manufacturer,
                    device_class=device_class,
                    device_function=device_function,
                    first_seen=now,
                    last_seen=now,
                    message_count=1,
                )

    def list_devices(self) -> list[NMEADevice]:
        """Return all devices, excluding hidden PGNs, sorted by source_id."""
        with self._lock:
            return sorted(
                (d for d in self._devices.values() if d.pgn not in self._HIDDEN_PGNS),
                key=lambda d: d.source_id,
            )

    def cleanup_stale(self, timeout: float) -> list[int]:
        """Remove devices that haven't sent a message within `timeout` seconds.

        Returns a list of removed source_ids.
        """
        now = time.time()
        stale_ids: list[int] = []
        with self._lock:
            to_remove = [
                sid
                for sid, dev in self._devices.items()
                if now - dev.last_seen > timeout
            ]
            for sid in to_remove:
                del self._devices[sid]
                stale_ids.append(sid)
        if stale_ids:
            log.info("Cleaned %d stale device(s): %s", len(stale_ids), stale_ids)
        return stale_ids

    @property
    def can_connected(self) -> bool:
        return self._can_connected

    @can_connected.setter
    def can_connected(self, value: bool) -> None:
        self._can_connected = value

    @property
    def can_error(self) -> str:
        return self._can_error

    @can_error.setter
    def can_error(self, value: str) -> None:
        self._can_error = value


class ValueCache:
    """Cache of the latest decoded PGN field values per (source_id, pgn)."""

    def __init__(self) -> None:
        self._cache: dict[tuple[int, int], dict] = {}
        self._lock = threading.Lock()

    def set(self, source_id: int, pgn: int, fields: dict) -> None:
        """Store the latest fields for a given device and PGN."""
        with self._lock:
            self._cache[(source_id, pgn)] = fields

    def get(self, source_id: int, pgn: int) -> dict | None:
        """Retrieve cached fields for a given device and PGN."""
        with self._lock:
            return self._cache.get((source_id, pgn))

    def get_all(self) -> list[dict]:
        """Return all cached values as a flat list."""
        result: list[dict] = []
        with self._lock:
            for (source_id, pgn), fields in self._cache.items():
                result.append({
                    "source_id": source_id,
                    "pgn": pgn,
                    "fields": fields,
                })
        return result


class HistoryStore:
    """Time-series storage for PGN field values (used for charts)."""

    def __init__(self, max_age: int = MAX_HISTORY_SECONDS) -> None:
        self._data: dict[tuple[int, int, str], list[dict]] = {}
        self._lock = threading.Lock()
        self._max_age = max_age

    def add(self, source_id: int, pgn: int, fields: list[dict]) -> None:
        """Append current values for each field."""
        now = time.time()
        cutoff = now - self._max_age
        with self._lock:
            for f in fields:
                key = (source_id, pgn, f["key"])
                if key not in self._data:
                    self._data[key] = []
                self._data[key].append({"timestamp": now, "value": f["value"]})
                self._data[key] = [p for p in self._data[key] if p["timestamp"] >= cutoff]

    def get_history(
        self,
        source_id: int,
        pgn: int,
        field_key: str,
        window_seconds: int = 300,
    ) -> list[dict]:
        """Return history for a specific field within a time window."""
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            key = (source_id, pgn, field_key)
            raw = list(self._data.get(key, []))
        return [p for p in raw if p["timestamp"] >= cutoff]


class RawMessageStore:
    """Ring buffer for raw CAN messages."""

    def __init__(self, max_size: int = RAW_BUFFER_SIZE) -> None:
        self._messages: list[RawMessage] = []
        self._lock = threading.Lock()
        self._max_size = max_size

    def add(
        self,
        timestamp: float,
        source_id: int,
        pgn: int,
        priority: int,
        raw_data: str,
        description: str = "",
        pgn_fields: Optional[list] = None,
    ) -> None:
        """Append a raw message, trimming oldest if buffer full."""
        msg = RawMessage(
            timestamp=timestamp,
            source_id=source_id,
            pgn=pgn,
            priority=priority,
            raw_data=raw_data,
            description=description,
            pgn_fields=pgn_fields,
        )
        with self._lock:
            self._messages.append(msg)
            while len(self._messages) > self._max_size:
                self._messages.pop(0)

    def get_messages(self, since: Optional[float] = None) -> list[RawMessage]:
        """Return messages, optionally filtered by minimum timestamp."""
        with self._lock:
            msgs = list(self._messages)
        if since is not None:
            msgs = [m for m in msgs if m.timestamp >= since]
        return msgs


# Singleton instances
device_store = DeviceStore()
value_cache = ValueCache()
history_store = HistoryStore()
raw_store = RawMessageStore()
