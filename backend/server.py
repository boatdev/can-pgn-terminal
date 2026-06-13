"""
NMEA 2000 Web Terminal — Application Entry Point.

Run with:
    python server.py

Or via uvicorn directly:
    uvicorn app.main:app --host 0.0.0.0 --port 8000
"""

import uvicorn  # pylint: disable=import-error
from app.config import HOST, PORT

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=False)
