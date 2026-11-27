# syntax=docker/dockerfile:1
FROM python:3.12-slim

# Security: run as non-root user
RUN groupadd -r botuser && useradd -r -g botuser botuser

WORKDIR /app

# Install dependencies first (layer cached independently of source changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create runtime data directory and set permissions
RUN mkdir -p /app/data && chown -R botuser:botuser /app

USER botuser

# Persistent storage for SQLite DB and logs
VOLUME ["/app/data"]

# Default port; override with WEB_PORT env var
EXPOSE 8443

# Health check: hit /health endpoint (returns {"status": "ok"} 200).
# DO NOT hit / — it has no route and returns 404, causing false failures.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=30s \
  CMD python -c "import urllib.request,ssl,os; urllib.request.urlopen(f\"https://127.0.0.1:{os.environ.get('WEB_PORT','8443')}/health\", timeout=5, context=ssl._create_unverified_context())" || exit 1

CMD ["python", "main.py"]
