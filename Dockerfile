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

CMD ["python", "main.py"]
