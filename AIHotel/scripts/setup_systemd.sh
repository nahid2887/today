#!/bin/bash
# Setup script for hotel-sync systemd timer
# This installs and enables the daily sync service

set -e

echo "================================================"
echo "Hotel Sync - Systemd Timer Setup"
echo "================================================"

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    echo "⚠️  This script needs sudo privileges to install systemd files."
    echo "Please run with: sudo ./scripts/setup_systemd.sh"
    exit 1
fi

# Get the actual user (not root when using sudo)
ACTUAL_USER=${SUDO_USER:-$USER}
PROJECT_DIR="/home/$ACTUAL_USER/Downloads/AIHotel"

echo ""
echo "Configuration:"
echo "  User: $ACTUAL_USER"
echo "  Project Directory: $PROJECT_DIR"
echo ""

# Verify project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "✗ Error: Project directory not found: $PROJECT_DIR"
    exit 1
fi

# Verify .venv exists
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "✗ Error: Virtual environment not found. Please run setup.sh first."
    exit 1
fi

# Verify sync script exists
if [ ! -f "$PROJECT_DIR/scripts/sync_hotels.py" ]; then
    echo "✗ Error: Sync script not found: $PROJECT_DIR/scripts/sync_hotels.py"
    exit 1
fi

# Copy systemd files to system directory
echo "[1/5] Copying systemd service file..."
cp "$PROJECT_DIR/systemd/hotel-sync.service" /etc/systemd/system/
echo "✓ Copied hotel-sync.service"

echo "[2/5] Copying systemd timer file..."
cp "$PROJECT_DIR/systemd/hotel-sync.timer" /etc/systemd/system/
echo "✓ Copied hotel-sync.timer"

# Reload systemd daemon
echo "[3/5] Reloading systemd daemon..."
systemctl daemon-reload
echo "✓ Systemd daemon reloaded"

# Enable the timer (but don't start yet)
echo "[4/5] Enabling hotel-sync timer..."
systemctl enable hotel-sync.timer
echo "✓ Timer enabled (will start on boot)"

# Start the timer
echo "[5/5] Starting hotel-sync timer..."
systemctl start hotel-sync.timer
echo "✓ Timer started"

echo ""
echo "================================================"
echo "✓ Setup Complete!"
echo "================================================"
echo ""
echo "The hotel sync service is now configured to run daily at 2:00 AM."
echo ""
echo "Useful commands:"
echo "  • Check timer status:     systemctl status hotel-sync.timer"
echo "  • View next run time:     systemctl list-timers hotel-sync.timer"
echo "  • Run sync manually:      sudo systemctl start hotel-sync.service"
echo "  • View recent logs:       journalctl -u hotel-sync.service -n 50"
echo "  • Follow logs live:       journalctl -u hotel-sync.service -f"
echo "  • Disable timer:          sudo systemctl disable hotel-sync.timer"
echo "  • Stop timer:             sudo systemctl stop hotel-sync.timer"
echo ""
echo "Log files:"
echo "  • Systemd journal:        journalctl -u hotel-sync.service"
echo "  • Application log:        /var/log/hotel-sync.log"
echo "  • (or fallback):          $PROJECT_DIR/logs/hotel-sync.log"
echo ""
echo "================================================"
echo ""
echo "Would you like to run a test sync now? (y/n)"
read -r response
if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo ""
    echo "Running test sync..."
    systemctl start hotel-sync.service
    echo ""
    echo "Waiting for sync to complete..."
    sleep 3
    echo ""
    echo "Recent logs:"
    journalctl -u hotel-sync.service -n 20 --no-pager
fi

echo ""
echo "Setup complete! 🎉"
