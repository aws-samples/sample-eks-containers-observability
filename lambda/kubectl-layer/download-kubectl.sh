#!/bin/bash
# Script to download kubectl binary during deployment

set -e

KUBECTL_VERSION="v1.28.0"
ARCH=$(uname -m)
OS=$(uname | tr '[:upper:]' '[:lower:]')

# Map architecture
if [ "$ARCH" == "x86_64" ]; then
    ARCH="amd64"
elif [ "$ARCH" == "aarch64" ]; then
    ARCH="arm64"
fi

# Create bin directory if it doesn't exist
mkdir -p bin

# Download kubectl
echo "Downloading kubectl $KUBECTL_VERSION for $OS/$ARCH..."
curl -L -o bin/kubectl "https://dl.k8s.io/release/$KUBECTL_VERSION/bin/$OS/$ARCH/kubectl"

# Make kubectl executable
chmod +x bin/kubectl

echo "kubectl $KUBECTL_VERSION downloaded successfully to bin/kubectl"