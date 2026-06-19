"""
Static resource data — NMEA 2000 lookup tables.
"""

# Manufacturer Code → Name mapping (NMEA 2000 standard)
MANUFACTURER_NAMES: dict[int, str] = {
    2: "Simrad",
    3: "Lowrance",
    4: "B&G",
    5: "Navico",
    6: "Raymarine",
    7: "Furuno",
    8: "Garmin",
    9: "Maretron",
    10: "Airmar",
    11: "Standard Horizon",
    39: "Actisense",
    88: "Yacht Devices",
    144: "Digital Yacht",
    145: "KVH",
    146: "Airmar",
    275: "Naviop",
    1853: "Simrad (Navico)",
    1855: "Lowrance (Navico)",
    1857: "B&G (Navico)",
    1870: "Navico",
    2053: "Yacht Devices",
}


def manufacturer_name(code: int) -> str:
    """Return human-readable manufacturer name for a given NMEA 2000 code."""
    return MANUFACTURER_NAMES.get(code, f"MFG {code}")