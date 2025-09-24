#!/bin/bash
# Stop the email CSV extractor

set -e

echo "🛑 Stopping Email CSV Extractor..."

# Stop and remove containers
docker-compose down

echo "✅ Email CSV Extractor stopped."
echo ""
echo "💡 To start again, run: ./scripts/start.sh"