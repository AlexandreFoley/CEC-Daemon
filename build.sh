#!/bin/bash
# Build script for CECDaemon
# Runs configuration and build steps only (no installation)

set -e  # Exit on any error

echo "🔨 Building CECDaemon..."
echo "Build directory: ./build"
echo

# Run the installer in build-only mode with ./build as build directory
python3 service_install.py --build-only --build-dir ./build

echo
echo "✅ Build completed successfully!"
echo "📁 Build artifacts are in: ./build"
echo "📄 Configuration saved to: ./build/install_config.json"
echo
echo "To install, run: ./install.sh"
