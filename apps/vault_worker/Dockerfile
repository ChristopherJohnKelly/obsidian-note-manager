FROM python:3.12-slim

# GitPython shells out to the git binary for vault repo operations
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Build context is the REPO ROOT (worker imports apps.* and packages.*):
#   docker build -f apps/vault_worker/Dockerfile .
COPY apps/vault_worker apps/vault_worker
COPY packages packages
RUN pip install --no-cache-dir -r apps/vault_worker/requirements.txt

CMD ["python3", "-m", "apps.vault_worker.worker"]
