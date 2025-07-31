#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 dr.max

# Maestro Knowledge MCP Server Start Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$SCRIPT_DIR/mcp_server.pid"
LOG_FILE="$SCRIPT_DIR/mcp_server.log"
PYTHON_MODULE="src.maestro_mcp.server"
DEFAULT_HOST="localhost"
DEFAULT_PORT="8030"

# Function to print colored output
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

print_info() {
    echo -e "${PURPLE}[INFO]${NC} $1"
}

# Check if server is already running
check_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0  # Server is running
        else
            # PID file exists but process is dead
            rm -f "$PID_FILE"
            return 1
        fi
    fi
    return 1  # Server is not running
}

# Parse command line arguments
parse_args() {
    MODE="http"
    HOST="$DEFAULT_HOST"
    PORT="$DEFAULT_PORT"
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --http)
                MODE="http"
                shift
                ;;
            --host)
                HOST="$2"
                shift 2
                ;;
            --port)
                PORT="$2"
                shift 2
                ;;
            --stdio)
                MODE="stdio"
                shift
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

# Show help information
show_help() {
    echo "Maestro Knowledge MCP Server Start Script"
    echo "=========================================="
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --http              Start HTTP server (default)"
    echo "  --stdio             Start stdio server"
    echo "  --host HOST         HTTP server host (default: localhost)"
    echo "  --port PORT         HTTP server port (default: 8030)"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                  # Start HTTP server on localhost:8030"
    echo "  $0 --http           # Start HTTP server on localhost:8030"
    echo "  $0 --stdio          # Start stdio server"
    echo "  $0 --http --port 9000  # Start HTTP server on localhost:9000"
    echo "  $0 --http --host 0.0.0.0 --port 8080  # Start HTTP server on all interfaces"
    echo ""
}

# Start the MCP server
start_server() {
    print_status "Starting Maestro Knowledge MCP Server..."
    
    # Check if already running
    if check_running; then
        local pid=$(cat "$PID_FILE")
        print_warning "MCP server is already running (PID: $pid)"
        return 0
    fi
    
    # Create log file if it doesn't exist
    touch "$LOG_FILE"
    
    # Set PYTHONPATH to include the project root
    export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"
    
    if [ "$MODE" = "http" ]; then
        start_http_server
    else
        start_stdio_server
    fi
}

# Start HTTP server
start_http_server() {
    print_info "Starting FastMCP HTTP server..."
    print_status "Host: $HOST"
    print_status "Port: $PORT"
    
    # Load .env file if it exists
    if [ -f "$SCRIPT_DIR/.env" ]; then
        print_status "Loading environment variables from .env file..."
        export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
    fi

    if [ -n "$CUSTOM_EMBEDDING_URL" ]; then
        print_info "🧬 Custom Embedding Endpoint is configured:"
        print_info "   - URL:    $CUSTOM_EMBEDDING_URL"
        # Use a default for the model if the variable isn't set
        print_info "   - Model:  ${CUSTOM_EMBEDDING_MODEL:-nomic-embed-text}"
    else
        print_info "🧬 Using default OpenAI embedding configuration."
    fi
    
    # Start the HTTP server in background
    python -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from src.maestro_mcp.server import run_http_server_sync
run_http_server_sync('$HOST', $PORT)
" > "$LOG_FILE" 2>&1 &
    
    local pid=$!
    echo "$pid" > "$PID_FILE"
    
    # Wait a moment for server to start
    sleep 2
    
    # Check if server started successfully
    if ps -p "$pid" > /dev/null 2>&1; then
        print_success "FastMCP HTTP server started successfully (PID: $pid)"
        print_info "🌐 Server URL: http://$HOST:$PORT"
        print_info "📖 OpenAPI docs: http://$HOST:$PORT/docs"
        print_info "📚 ReDoc docs: http://$HOST:$PORT/redoc"
        print_info "🔧 MCP endpoint: http://$HOST:$PORT/mcp/"
        print_status "Log file: $LOG_FILE"
        print_status "PID file: $PID_FILE"
        print_status "To stop server, run: ./stop.sh"
        print_status "To check status, run: ./stop.sh status"
    else
        print_error "Failed to start HTTP server"
        print_status "Check the log file for details: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

# Start stdio server (for MCP clients)
start_stdio_server() {
    print_info "Starting FastMCP stdio server..."
    print_status "Note: This mode is for MCP client communication via stdio"
    
    # Load .env file if it exists
    if [ -f "$SCRIPT_DIR/.env" ]; then
        print_status "Loading environment variables from .env file..."
        export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
    fi
    
    # Test module import
    if python -c "import $PYTHON_MODULE; print('Module imported successfully')" > "$LOG_FILE" 2>&1; then
        print_success "FastMCP stdio server module is ready"
        print_status "To use with MCP clients, run: python -m $PYTHON_MODULE"
        # Create a status file to track that the module is ready
        echo "ready" > "$PID_FILE"
        print_status "Log file: $LOG_FILE"
        print_status "PID file: $PID_FILE"
        print_status "To check status, run: ./stop.sh status"
        print_info "💡 Tip: Use --http flag to start HTTP server for browser access"
        return 0
    else
        print_error "Failed to import MCP server module"
        print_status "Check the log file for details: $LOG_FILE"
        return 1
    fi
}

# Main execution
main() {
    print_status "Maestro Knowledge MCP Server Manager"
    print_status "====================================="
    
    # Parse command line arguments
    parse_args "$@"
    
    # Check if Python is available
    if ! command -v python &> /dev/null; then
        print_error "Python is not installed or not in PATH"
        exit 1
    fi
    
    # Check if the MCP module exists
    if ! python -c "import $PYTHON_MODULE" 2>/dev/null; then
        print_error "MCP server module not found: $PYTHON_MODULE"
        print_status "Make sure you're running this from the project root directory"
        exit 1
    fi
    
    start_server
    exit $?
}

# Run main function
main "$@" 