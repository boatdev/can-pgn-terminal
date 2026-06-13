# ============================================================
# Stage 1 — Build React frontend
# ============================================================
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/index.html .
COPY frontend/vite.config.js .
COPY frontend/src ./src

RUN npm run build

# ============================================================
# Stage 2 — Python backend + serve static files
# ============================================================
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application package
COPY backend/app ./app
COPY backend/server.py .

# Copy built frontend from stage 1
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]