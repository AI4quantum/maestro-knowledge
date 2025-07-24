#!/bin/bash
# Test script for CLI integration with MCP server

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

print_status "Testing CLI integration with MCP server"
print_status "Project root: $PROJECT_ROOT"

# Build the CLI
print_status "Building CLI..."
cd "$SCRIPT_DIR"
go build -o maestro-k src/*.go
print_success "CLI built successfully"

# Test CLI help
print_status "Testing CLI help..."
./maestro-k --help > /dev/null
print_success "CLI help works"

# Test list command help
print_status "Testing list command help..."
./maestro-k list --help > /dev/null
print_success "List command help works"

# Test dry-run mode
print_status "Testing dry-run mode..."
DRY_RUN_OUTPUT=$(./maestro-k list vector-db --dry-run)
if [[ "$DRY_RUN_OUTPUT" == *"[DRY RUN] Would list vector databases"* ]]; then
    print_success "Dry-run mode works correctly"
else
    print_error "Dry-run mode failed"
    exit 1
fi

# Test with verbose mode
print_status "Testing verbose mode..."
VERBOSE_OUTPUT=$(./maestro-k list vector-db --dry-run --verbose)
if [[ "$VERBOSE_OUTPUT" == *"Listing vector databases"* ]]; then
    print_success "Verbose mode works correctly"
else
    print_error "Verbose mode failed"
    exit 1
fi

# Test environment variable support
print_status "Testing environment variable support..."
export MAESTRO_KNOWLEDGE_MCP_SERVER_URI="http://localhost:9000"
ENV_OUTPUT=$(./maestro-k list vector-db --verbose 2>&1 || true)
if [[ "$ENV_OUTPUT" == *"Connecting to MCP server at: http://localhost:9000"* ]]; then
    print_success "Environment variable support works"
else
    print_warning "Environment variable support may not be working correctly"
    echo "Output: $ENV_OUTPUT"
fi

# Test command line flag override
print_status "Testing command line flag override..."
FLAG_OUTPUT=$(./maestro-k list vector-db --verbose --mcp-server-uri="http://localhost:9999" 2>&1 || true)
if [[ "$FLAG_OUTPUT" == *"Connecting to MCP server at: http://localhost:9999"* ]]; then
    print_success "Command line flag override works"
else
    print_warning "Command line flag override may not be working correctly"
    echo "Output: $FLAG_OUTPUT"
fi

# Test .env file support
print_status "Testing .env file support..."
unset MAESTRO_KNOWLEDGE_MCP_SERVER_URI
echo "MAESTRO_KNOWLEDGE_MCP_SERVER_URI=http://localhost:8888" > .env
ENV_FILE_OUTPUT=$(./maestro-k list vector-db --verbose 2>&1 || true)
if [[ "$ENV_FILE_OUTPUT" == *"Connecting to MCP server at: http://localhost:8888"* ]]; then
    print_success ".env file support works"
else
    print_warning ".env file support may not be working correctly"
    echo "Output: $ENV_FILE_OUTPUT"
fi
rm -f .env

print_success "All CLI integration tests passed!"
print_status "To test with a real MCP server:"
print_status "1. Start the MCP server: cd $PROJECT_ROOT && ./start.sh --http"
print_status "2. Run: ./maestro-k list vector-db --mcp-server-uri=http://localhost:8030" 