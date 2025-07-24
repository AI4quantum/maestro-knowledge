#!/bin/bash
# Example usage script for the Maestro Knowledge CLI

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

print_status "Maestro Knowledge CLI Example Usage"
print_status "==================================="

# Check if CLI is built
if [ ! -f "$SCRIPT_DIR/maestro-k" ]; then
    print_status "Building CLI..."
    cd "$SCRIPT_DIR"
    go build -o maestro-k src/*.go
    print_success "CLI built successfully"
fi

# Check if MCP server is running
print_status "Checking MCP server status..."
cd "$PROJECT_ROOT"
if ./stop.sh status > /dev/null 2>&1; then
    print_success "MCP server is running"
else
    print_warning "MCP server is not running"
    print_status "Starting MCP server..."
    ./start.sh --http &
    sleep 5
    print_success "MCP server started"
fi

# Get the server port from the status
SERVER_PORT=$(./stop.sh status 2>/dev/null | grep -o "http://[^[:space:]]*" | grep -o ":[0-9]*" | head -1 | sed 's/://')
if [ -z "$SERVER_PORT" ]; then
    SERVER_PORT="8030"  # Default port
fi

print_status "Using MCP server port: $SERVER_PORT"

# Go back to CLI directory
cd "$SCRIPT_DIR"

print_status ""
print_status "Example 1: Basic list command"
print_status "============================="
./maestro-k list vector-db --mcp-server-uri="http://localhost:$SERVER_PORT"

print_status ""
print_status "Example 2: List with verbose output"
print_status "==================================="
./maestro-k list vector-db --mcp-server-uri="http://localhost:$SERVER_PORT" --verbose

print_status ""
print_status "Example 3: Using environment variable"
print_status "====================================="
export MAESTRO_KNOWLEDGE_MCP_SERVER_URI="http://localhost:$SERVER_PORT"
./maestro-k list vector-db

print_status ""
print_status "Example 4: Using .env file"
print_status "=========================="
echo "MAESTRO_KNOWLEDGE_MCP_SERVER_URI=http://localhost:$SERVER_PORT" > .env
./maestro-k list vector-db
rm -f .env

print_status ""
print_status "Example 5: Dry-run mode"
print_status "======================="
./maestro-k list vector-db --dry-run

print_status ""
print_status "Example 6: Silent mode"
print_status "======================"
./maestro-k list vector-db --mcp-server-uri="http://localhost:$SERVER_PORT" --silent

print_status ""
print_success "All examples completed successfully!"
print_status ""
print_status "To stop the MCP server:"
print_status "cd $PROJECT_ROOT && ./stop.sh" 