#!/bin/bash

# Maestro Knowledge CLI Build Script
# This script builds the maestro-k CLI binary from the cli directory

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "go.mod" ] || [ ! -d "src" ]; then
    print_error "This script must be run from the cli directory"
    exit 1
fi

# Check if Go is installed
if ! command -v go &> /dev/null; then
    print_error "Go is not installed. Please install Go 1.21 or later."
    exit 1
fi

# Check Go version
GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
REQUIRED_VERSION="1.21"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$GO_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    print_error "Go version $GO_VERSION is too old. Please install Go $REQUIRED_VERSION or later."
    exit 1
fi

print_status "Go version $GO_VERSION detected"

print_status "Building maestro-k CLI..."

# Download dependencies
print_status "Downloading dependencies..."
go mod download

# Build the binary
print_status "Compiling binary..."
go build -ldflags="-s -w" -o ../maestro-k ./src

# Check if build was successful
if [ $? -eq 0 ]; then
    print_status "Build successful! Binary created at: $(pwd)/../maestro-k"
    
    # Make the binary executable
    chmod +x ../maestro-k
    
    # Show binary info
    print_status "Binary information:"
    ls -lh ../maestro-k
    
    # Test the binary
    print_status "Testing binary..."
    if ../maestro-k --version &> /dev/null; then
        print_status "Binary test successful!"
        print_status "You can now use: ./maestro-k --help"
    else
        print_warning "Binary test failed, but build completed"
    fi
else
    print_error "Build failed!"
    exit 1
fi

print_status "Build process completed successfully!" 