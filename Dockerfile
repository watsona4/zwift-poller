FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source
COPY src/ src/

# Create data directory for token storage
RUN mkdir -p /data

# Run as non-root user
RUN useradd -r -s /bin/false appuser && \
    chown -R appuser:appuser /app /data
USER appuser

# Default command
CMD ["python", "-m", "zwift_poller"]
