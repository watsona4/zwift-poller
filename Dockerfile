FROM python:3.12-slim

WORKDIR /app

# Copy source and install
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip install --no-cache-dir .

# Create data directory for token storage
RUN mkdir -p /data

# Run as non-root user
RUN useradd -r -s /bin/false appuser && \
    chown -R appuser:appuser /app /data
USER appuser

# Default command
CMD ["python", "-m", "zwift_poller"]
