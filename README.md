# CAN PGN Terminal

A web-based real-time monitor for CAN bus PGN (Parameter Group Number) messages, primarily targeting marine N2K networks.

> **Disclaimer:** This project is not affiliated with or endorsed by the National Marine Electronics Association (NMEA). "NMEA 2000" is a trademark of NMEA.

## Features

- **Live CAN PGN monitoring** — connects to a CAN bus via slcan interface
- **Auto-detection** — discovers devices on the bus and shows PGN details
- **Decoded PGN values** — view parsed field values with units in real time
- **Raw message log** — inspect raw CAN frames with PGN expansion
- **Time-series history** — track field values over time (heading, wind, etc.)
- **Device cleanup** — devices are automatically removed from the registry when they disappear from the bus

## Quick Start

```bash
# Clone the repository
git clone git@github.com:boatdev/can-pgn-terminal.git
cd can-pgn-terminal

# Start with Docker (CAN device required)
docker compose up -d

# Open in browser
open http://localhost:8000
```

## Configuration

| Environment Variable   | Default   | Description                                 |
|------------------------|-----------|---------------------------------------------|
| `CAN_DEVICE`           | (none)    | slcan device path, e.g. `/dev/ttyACM0`      |
| `CAN_BITRATE`          | `250000`  | CAN bus bitrate                             |
| `RAW_BUFFER_SIZE`      | `500`     | Max raw messages kept in memory             |
| `MAX_HISTORY_SECONDS`  | `3600`    | History retention for time-series data (s)  |
| `DEVICE_TIMEOUT`       | `5`       | Seconds without message before removal      |
| `DEVICE_CLEANUP_INTERVAL` | `3`    | Cleanup check interval (s)                  |
| `HOST`                 | `0.0.0.0` | HTTP server bind address                    |
| `PORT`                 | `8000`    | HTTP server port                            |

## Project Structure

```
can-pgn-terminal/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py         # Environment-based configuration
│   │   ├── models.py         # Pydantic API models
│   │   ├── stores.py         # Thread-safe data stores
│   │   ├── can_listener.py   # CAN bus reader and PGN decoder
│   │   └── main.py           # FastAPI application and routes
│   ├── server.py             # Entry point
│   ├── requirements.txt
│   └── tests/
│       ├── __init__.py
│       ├── test_api.py       # FastAPI endpoint tests
│       ├── test_can_listener.py  # CAN decoder helper tests
│       ├── test_models.py    # Pydantic model tests
│       └── test_stores.py    # Data store tests
├── frontend/
│   ├── src/
│   │   ├── App.jsx           # React application
│   │   ├── App.css           # Dark marine theme
│   │   └── main.jsx          # React entry point
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── .dockerignore
├── .gitignore
├── docker-compose.yml
├── Dockerfile                # Multi-stage build
├── pyproject.toml
└── README.md
```

## API Endpoints

| Endpoint              | Description                               |
|-----------------------|-------------------------------------------|
| `GET /api/devices`    | List detected CAN bus devices             |
| `GET /api/values`     | Latest decoded PGN values per device      |
| `GET /api/raw-messages` | Raw CAN message buffer (with `?since=`) |
| `GET /api/history`    | Time-series data for a specific field     |
| `GET /api/health`     | Health check with CAN connection status   |

## Development

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"

# Run tests
pytest

# Start server (without CAN device — will show disconnected state)
python server.py
```

### Frontend

```bash
cd frontend
npm install

# Development server with API proxy to :8000
npm run dev
```

## License

MIT