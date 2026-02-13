FROM python:3.11-slim
WORKDIR /app

# Copy project definition and source
COPY pyproject.toml .
COPY src_v2/ src_v2/

# Install dependencies and the project itself
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .

# Set the new entrypoint (The "Night Watchman" cron loop)
CMD ["python", "-m", "src_v2.entrypoints.cron_runner"]
