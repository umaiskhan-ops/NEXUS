# Sovereign Agentic Mesh Node — Production Container
# Hardened non-root runtime environment for local swarm execution

FROM python:3.10-slim AS runtime

# Security: prevent Python from writing pyc files to disk and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

WORKDIR /app

# Install security updates and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy dependencies and source code
COPY . /app

# Optional security and hardware dependencies (fernet encryption, system metrics)
RUN pip install --no-cache-dir cryptography psutil || true

# Hardened non-root user execution
RUN useradd -u 10001 -m -s /bin/bash meshuser && \
    mkdir -p /app/data && \
    chown -R meshuser:meshuser /app

USER meshuser

EXPOSE 8443

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8443/healthz || exit 1

ENTRYPOINT ["python", "-m", "sovereign_mesh"]
CMD ["serve"]
