# ─── Stage 1: dependency builder ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install into a prefix so Stage 2 can COPY only the installed packages
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ─── Stage 2: lean runtime image ──────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Runtime system packages (nc for wait-for-it health checks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Application source — exclude venv, .env, caches via .dockerignore
COPY . .

# Non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --retries=5 --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').raise_for_status()" \
    || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
