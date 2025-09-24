#!/bin/bash
# Start the email CSV extractor with Docker Compose

set -e

echo "🚀 Starting Email CSV Extractor with Docker Compose"

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found. Creating from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "📝 Please edit .env file with your actual configuration before running again."
        exit 1
    else
        echo "❌ .env.example not found. Please create .env file with required configuration."
        exit 1
    fi
fi

# Build and start the containers
echo "🔨 Building and starting containers..."
docker-compose up --build -d

# Show status
echo "📊 Container status:"
docker-compose ps

# Show logs
echo "📋 Recent logs:"
docker-compose logs --tail=20 email-csv-extractor

echo ""
echo "✅ Email CSV Extractor is now running!"
echo ""
echo "📖 Useful commands:"
echo "  View logs:    docker-compose logs -f email-csv-extractor"
echo "  Stop:         docker-compose down"
echo "  Restart:      docker-compose restart email-csv-extractor"
echo "  Health check: docker-compose exec email-csv-extractor uv run email-csv-extractor validate-config"