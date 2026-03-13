# ============================================
# Cloudboosta Voice Agent — Production Build
# Multi-stage: frontend (Vite) + backend (FastAPI)
# ============================================

# Stage 1: Build frontend
FROM node:18-slim AS frontend-build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --production=false
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + frontend static files
FROM python:3.13-slim

WORKDIR /app

# Install dependencies first (cache layer)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Copy frontend build output
COPY --from=frontend-build /app/dist ./static

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
