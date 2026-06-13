"""Tests for thread-safe data stores."""
# pylint: disable=import-error

from app.stores import DeviceStore, HistoryStore, RawMessageStore, ValueCache


class TestDeviceStore:
    """Test suite for DeviceStore."""

    def test_upsert_new_device(self):
        """Upsert should register a new device with message_count = 1."""
        store = DeviceStore()
        store.upsert(source_id=10, pgn=130306, description="Wind")
        devices = store.list_devices()
        assert len(devices) == 1
        assert devices[0].source_id == 10
        assert devices[0].message_count == 1

    def test_upsert_existing_increments_count(self):
        """Upsert on an existing device should increment message_count."""
        store = DeviceStore()
        store.upsert(source_id=10, pgn=130306, description="Wind")
        store.upsert(source_id=10, pgn=130306, description="Wind")
        devices = store.list_devices()
        assert len(devices) == 1
        assert devices[0].message_count == 2

    def test_hidden_pgn_excluded(self):
        """PGN 60928 (ISO Address Claim) should be hidden from listings."""
        store = DeviceStore()
        store.upsert(source_id=1, pgn=60928, description="Address Claim")
        store.upsert(source_id=2, pgn=130306, description="Wind")
        devices = store.list_devices()
        assert len(devices) == 1
        assert devices[0].source_id == 2

    def test_cleanup_stale(self):
        """Devices with zero timeout should be removed immediately."""
        store = DeviceStore()
        store.upsert(source_id=10, pgn=130306, description="Wind")
        removed = store.cleanup_stale(timeout=0)
        assert 10 in removed
        assert store.list_devices() == []

    def test_cleanup_fresh_device_not_removed(self):
        """Fresh devices should not be removed with a large timeout."""
        store = DeviceStore()
        store.upsert(source_id=10, pgn=130306, description="Wind")
        removed = store.cleanup_stale(timeout=9999)
        assert removed == []
        assert len(store.list_devices()) == 1

    def test_can_connection_status(self):
        """CAN connection status flags should be settable and readable."""
        store = DeviceStore()
        assert store.can_connected is False
        store.can_connected = True
        assert store.can_connected is True
        store.can_error = "test error"
        assert store.can_error == "test error"


class TestValueCache:
    """Test suite for ValueCache."""

    def test_set_and_get(self):
        """Set should store fields and get should retrieve them."""
        cache = ValueCache()
        fields = [{"key": "Wind_Speed", "value": 12.5}]
        cache.set(source_id=10, pgn=130306, fields=fields)
        result = cache.get(source_id=10, pgn=130306)
        assert result == fields

    def test_get_missing_returns_none(self):
        """Getting a non-existent key should return None."""
        cache = ValueCache()
        assert cache.get(source_id=99, pgn=999) is None

    def test_get_all(self):
        """Get_all should return all cached entries."""
        cache = ValueCache()
        cache.set(source_id=10, pgn=130306, fields=[{"key": "A", "value": 1}])
        cache.set(source_id=20, pgn=130310, fields=[{"key": "B", "value": 2}])
        all_vals = cache.get_all()
        assert len(all_vals) == 2


class TestHistoryStore:
    """Test suite for HistoryStore."""

    def test_add_and_get_history(self):
        """Added records should be retrievable within the time window."""
        store = HistoryStore(max_age=60)
        fields = [{"key": "Wind_Speed", "value": 10.0}]
        store.add(source_id=10, pgn=130306, fields=fields)
        history = store.get_history(source_id=10, pgn=130306,
                                    field_key="Wind_Speed",
                                    window_seconds=60)
        assert len(history) == 1
        assert history[0]["value"] == 10.0

    def test_expired_history_removed(self):
        """Records outside the max_age window should be purged."""
        store = HistoryStore(max_age=0)
        fields = [{"key": "X", "value": 1}]
        store.add(source_id=10, pgn=130306, fields=fields)
        history = store.get_history(source_id=10, pgn=130306,
                                    field_key="X",
                                    window_seconds=0)
        assert history == []


class TestRawMessageStore:
    """Test suite for RawMessageStore."""

    def test_add_and_get_messages(self):
        """Added messages should be retrievable."""
        store = RawMessageStore(max_size=10)
        store.add(timestamp=100.0, source_id=1, pgn=130306, priority=2, raw_data="AA BB")
        msgs = store.get_messages()
        assert len(msgs) == 1
        assert msgs[0].pgn == 130306

    def test_ring_buffer_trim(self):
        """Buffer should drop oldest messages when it exceeds max_size."""
        store = RawMessageStore(max_size=3)
        for i in range(5):
            store.add(timestamp=float(i), source_id=i, pgn=100 + i, priority=2, raw_data="FF")
        msgs = store.get_messages()
        assert len(msgs) == 3
        assert msgs[0].source_id == 2

    def test_get_messages_since(self):
        """get_messages with since= should filter by timestamp."""
        store = RawMessageStore(max_size=10)
        for i in range(5):
            store.add(timestamp=float(i * 10), source_id=i, pgn=100 + i, priority=2, raw_data="FF")
        msgs = store.get_messages(since=25.0)
        assert len(msgs) == 2
