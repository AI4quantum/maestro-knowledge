#!/bin/bash

# CLI Test Runner Script
# This script runs the Go tests for the maestro-k CLI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_header() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "tests/main_test.go" ]; then
    print_error "This script must be run from the cli directory"
    exit 1
fi

# Check if Go is installed
if ! command -v go &> /dev/null; then
    print_error "Go is not installed. Please install Go 1.21 or later."
    exit 1
fi

print_header "Running maestro-k CLI tests..."

# Run all tests with verbose output
print_status "Running tests with verbose output..."
go test -v ./...

# Run tests with coverage
print_status "Running tests with coverage..."
go test -cover ./...

# Run tests with race detection
print_status "Running tests with race detection..."
go test -race ./...

# Run specific test files if they exist
if [ -f "tests/main_test.go" ]; then
    print_status "Running main tests..."
    go test -v tests/main_test.go tests/validate_test.go
fi

print_status "All CLI tests completed successfully!" 