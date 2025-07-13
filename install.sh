#!/bin/bash
# Install script for CECDaemon
# Runs installation step only using pre-built artifacts

set -e  # Exit on any error

BUILD_DIR="./build"
CONFIG_FILE="$BUILD_DIR/install_config.json"

echo "📦 Installing CECDaemon..."
echo "Using build directory: $BUILD_DIR"
echo "Using config file: $CONFIG_FILE"
echo

# Check if build directory and config file exist
if [ ! -d "$BUILD_DIR" ]; then
    echo "❌ Error: Build directory not found: $BUILD_DIR"
    echo "   Run ./build.sh first to build CECDaemon"
    exit 1
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Configuration file not found: $CONFIG_FILE"
    echo "   Run ./build.sh first to generate the configuration"
    exit 1
fi

echo "🔒 This step requires elevated privileges for system installation..."
echo

# Run the installer in install-only mode
sudo python3 service_install.py --install-only --config-file "$CONFIG_FILE"

echo
echo "✅ Installation completed successfully!"
echo "🔧 CECDaemon service has been installed and started"
echo
echo "Useful commands:"
echo "  sudo systemctl status cecdaemon    # Check service status"
echo "  sudo systemctl stop cecdaemon     # Stop the service"
echo "  sudo systemctl start cecdaemon    # Start the service"
echo "  sudo systemctl restart cecdaemon  # Restart the service"
echo "  sudo journalctl -u cecdaemon -f   # View live logs"
