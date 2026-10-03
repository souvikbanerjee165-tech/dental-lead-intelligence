# Production Multi-Stage Dockerfile for Google Cloud Run / Compute Engine
FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app

# Install minimal OS dependencies for network & certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browser binaries and system libraries
RUN playwright install chromium --with-deps || true

# Copy application codebase
COPY . .

# Ensure storage directory exists
RUN mkdir -p /app/output

EXPOSE 8000

# Healthcheck for zero-downtime rolling deploys
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/api/health || exit 1

# Start FastAPI application
CMD uvicorn app:app --host 0.0.0.0 --port ${PORT}
