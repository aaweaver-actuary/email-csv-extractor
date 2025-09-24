#!/bin/bash
# Set up the email CSV extractor to start automatically when the computer starts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "🔧 Setting up Email CSV Extractor for automatic startup"

# Create systemd service file for user session
SERVICE_FILE="$HOME/.config/systemd/user/email-csv-extractor.service"

# Create systemd user directory if it doesn't exist
mkdir -p "$HOME/.config/systemd/user"

# Create the service file
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Email CSV Extractor
Requires=docker.service
After=docker.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=300
Restart=on-failure
RestartSec=30

[Install]
WantedBy=default.target
EOF

# Reload systemd and enable the service
systemctl --user daemon-reload
systemctl --user enable email-csv-extractor.service

# Enable lingering so the service starts without login
sudo loginctl enable-linger $USER

echo "✅ Email CSV Extractor is now configured to start automatically!"
echo ""
echo "📖 Useful systemd commands:"
echo "  Start:   systemctl --user start email-csv-extractor"
echo "  Stop:    systemctl --user stop email-csv-extractor"
echo "  Status:  systemctl --user status email-csv-extractor"
echo "  Disable: systemctl --user disable email-csv-extractor"
echo ""
echo "🔄 The service will now start automatically when your computer boots."
echo "   To start it now, run: systemctl --user start email-csv-extractor"