# Sovereign Agentic Mesh Node — Production Container
# Hardened non-root runtime environment for local swarm execution

FROM python:3.12-slim AS runtime

# Security: prevent Python from writing pyc files to disk and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data

WORKDIR /app

# Install security updates and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install pinned mandatory security and hardware dependencies (fail-closed)
COPY requirements.txt pyproject.toml /app/
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy only application package source (secrets/data excluded via .dockerignore and explicit path)
COPY sovereign_mesh /app/sovereign_mesh

# Hardened non-root user execution
RUN useradd -u 10001 -m -s /bin/bash meshuser && \
    mkdir -p /app/data && \
    chmod 700 /app/data && \
    chown -R meshuser:meshuser /app

USER meshuser

EXPOSE 8443

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8443/healthz || exit 1

ENTRYPOINT ["python", "-m", "sovereign_mesh"]
CMD ["serve"]
