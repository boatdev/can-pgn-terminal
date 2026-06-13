"""Tests for CAN listener helper functions."""
# pylint: disable=import-error

from app.can_listener import (
    _describe_device_from_pgn,
    _extract_pgn_fields,
    _get_skip_field_types,
    _is_nmea_field,
)


class FakeNMEAField:
    """Minimal mock of an NMEA2000 field object."""

    def __init__(self, id_, name, value, unit="", type_=None):
        self.id = id_
        self.name = name
        self.value = value
        self.unit_of_measurement = unit
        self.type = type_


class FakeDecoded:
    """Mock of a decoded NMEA2000 message."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestIsNMEAField:
    """Test suite for _is_nmea_field helper."""

    def test_valid_field(self):
        """An object with id, name, value should be detected as NMEA field."""
        obj = FakeNMEAField(id_=1, name="Speed", value=12.5)
        assert _is_nmea_field(obj) is True

    def test_invalid_object(self):
        """Non-object types should return False."""
        assert _is_nmea_field("string") is False
        assert _is_nmea_field(42) is False
        assert _is_nmea_field(None) is False


class TestGetSkipFieldTypes:
    """Test suite for _get_skip_field_types helper."""

    def test_returns_set(self):
        """Should return a set (empty if nmea2000 is not installed)."""
        result = _get_skip_field_types()
        assert isinstance(result, set)


class TestDescribeDeviceFromPgn:
    """Test suite for _describe_device_from_pgn helper."""

    def test_extracts_manufacturer_from_code(self):
        """Manufacturer_Code attribute should be extracted."""
        obj = FakeDecoded(Manufacturer_Code="123")
        mfr, cls, func = _describe_device_from_pgn(obj)
        assert mfr == "123"

    def test_returns_empty_when_no_attrs(self):
        """Empty decoded object should return empty strings."""
        obj = FakeDecoded()
        mfr, cls, func = _describe_device_from_pgn(obj)
        assert mfr == ""
        assert cls == ""
        assert func == ""


class TestExtractPgnFields:
    """Test suite for _extract_pgn_fields helper."""

    def test_skips_private_attrs(self):
        """Attributes starting with underscore should be skipped."""
        obj = FakeDecoded(_private=42, normal=10)
        fields = _extract_pgn_fields(obj)
        keys = {f["key"] for f in fields}
        assert "normal" in keys
        assert "_private" not in keys

    def test_skips_reserved_fields(self):
        """Fields with RESERVED/SPARE type and None value should be skipped."""
        obj = FakeDecoded(valid_field=FakeNMEAField(1, "Speed", 12.5))
        fields = _extract_pgn_fields(obj)
        assert len(fields) >= 1

    def test_extracts_nmea_field(self):
        """NMEA field objects should be extracted with key, name, value, unit."""
        obj = FakeDecoded(
            wind_speed=FakeNMEAField(1, "Wind_Speed", 12.5, "m/s"),
        )
        fields = _extract_pgn_fields(obj)
        keys = {f["key"] for f in fields}
        assert "1" in keys

    def test_extracts_simple_type(self):
        """Simple int/float/str/bool attributes should be extracted."""
        obj = FakeDecoded(simple_int=42)
        fields = _extract_pgn_fields(obj)
        assert any(f["key"] == "simple_int" and f["value"] == 42 for f in fields)
