"""
Application configuration from environment variables.
"""

import os


def int_from_env(name: str, default: int) -> int:
    """Parse integer from environment variable with fallback."""
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


# CAN bus settings
CAN_DEVICE: str = os.environ.get("CAN_DEVICE", "").strip()
CAN_BITRATE: int = int_from_env("CAN_BITRATE", 250000)

# Raw message buffer size
RAW_BUFFER_SIZE: int = int_from_env("RAW_BUFFER_SIZE", 500)

# History store retention
MAX_HISTORY_SECONDS: int = int_from_env("MAX_HISTORY_SECONDS", 3600)

# Device stale detection
DEVICE_TIMEOUT_SECONDS: int = int_from_env("DEVICE_TIMEOUT", 5)
DEVICE_CLEANUP_INTERVAL: int = int_from_env("DEVICE_CLEANUP_INTERVAL", 3)

# Server
HOST: str = os.environ.get("HOST", "0.0.0.0")
PORT: int = int_from_env("PORT", 8000)
