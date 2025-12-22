#!/usr/bin/env bash
set -euo pipefail

# Install the systemd service file and enable it.
SERVICE_SRC="$(dirname "$0")/../systemd/market-collector.service"
SERVICE_DEST="/etc/systemd/system/market-collector.service"

if [[ $EUID -ne 0 ]]; then
  echo "install_systemd.sh must be run as root (sudo)"
  exit 1
fi

echo "Installing systemd unit to $SERVICE_DEST"
cp "$SERVICE_SRC" "$SERVICE_DEST"
systemctl daemon-reload
systemctl enable market-collector.service
echo "Service installed. Start with: systemctl start market-collector.service"
