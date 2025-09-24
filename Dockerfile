# Use Python 3.11 slim image for better performance
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Create app user for security
RUN useradd --create-home --shell /bin/bash app

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

# Create necessary directories
RUN mkdir -p /app/data /app/logs /tmp/email-csv-extractor && \
    chown -R app:app /app /tmp/email-csv-extractor

# Copy application code
COPY --chown=app:app . .

# Switch to app user
USER app

# Install application in editable mode
RUN uv pip install -e .

# Expose health check port (if needed)
EXPOSE 8080

# Create startup script
RUN cat > /app/start.sh << 'EOF'
#!/bin/bash
set -e

echo "🚀 Starting Email CSV Extractor..."
echo "📧 Mailbox: ${EMAIL_MAILBOX_ADDRESS:-not-configured}"
echo "📁 SharePoint Team: ${SHAREPOINT_TEAM_ID:-not-configured}"
echo "🔍 Log Level: ${LOG_LEVEL:-INFO}"

# Run health check first
echo "🔍 Running health check..."
uv run email-csv-extractor validate-config

# Start the application
echo "▶️  Starting continuous monitoring..."
exec uv run email-csv-extractor run
EOF

RUN chmod +x /app/start.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD uv run python -c "import sys; sys.exit(0)" || exit 1

# Default command
CMD ["/app/start.sh"]