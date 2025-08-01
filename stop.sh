#!/bin/bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 dr.max

# Maestro Knowledge MCP Server Stop Script

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

# Maximum time to wait for graceful shutdown (seconds)
MAX_GRACEFUL_SHUTDOWN=5
# Time between checks during graceful shutdown (seconds)
CHECK_INTERVAL=1

# Check if server is running
check_running() {
    if [ ! -f "$PID_FILE" ]; then
        return 1  # PID file doesn't exist
    fi
    
    local pid
    pid=$(cat "$PID_FILE") || return 1
    
    # Check if the content is "ready" (stdio mode)
    if [ "$pid" = "ready" ]; then
        return 1  # Not a running HTTP server
    fi
    
    if ps -p "$pid" > /dev/null 2>&1; then
        return 0  # Server is running
    fi
    
    # PID file exists but process is dead
    rm -f "$PID_FILE"
    return 1
}

# Check if server is ready (for stdio mode)
check_ready() {
    if [ ! -f "$PID_FILE" ]; then
        return 1  # Status file doesn't exist
    fi
    
    local status
    status=$(cat "$PID_FILE") || return 1
    
    if [ "$status" = "ready" ]; then
        return 0  # Server is ready
    fi
    
    # Status file exists but with wrong status
    rm -f "$PID_FILE"
    return 1
}

# Wait for process to terminate
wait_for_termination() {
    local pid=$1
    local timeout=$2
    local interval=${3:-1}
    local elapsed=0
    
    while ps -p "$pid" > /dev/null 2>&1; do
        if [ "$elapsed" -ge "$timeout" ]; then
            return 1  # Timeout
        fi
        print_status "Waiting for process to terminate (${elapsed}s/${timeout}s)..."
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
    
    return 0  # Process terminated
}

# Stop the MCP server
stop_server() {
    print_status "Stopping Maestro Knowledge MCP Server..."
    
    # Check if HTTP server is running
    if check_running; then
        local pid
        pid=$(cat "$PID_FILE") || return 1
        print_status "Found running HTTP server (PID: $pid)"
        
        # Attempt graceful shutdown
        if kill "$pid" 2>/dev/null; then
            if wait_for_termination "$pid" "$MAX_GRACEFUL_SHUTDOWN" "$CHECK_INTERVAL"; then
                print_success "HTTP server stopped gracefully"
            else
                print_warning "Process still running after ${MAX_GRACEFUL_SHUTDOWN}s, attempting force kill..."
                if kill -9 "$pid" 2>/dev/null; then
                    if wait_for_termination "$pid" 2 1; then
                        print_warning "Process force-killed successfully"
                    else
                        print_error "Failed to kill process even with SIGKILL"
                        return 1
                    fi
                else
                    print_error "Failed to send SIGKILL to process"
                    return 1
                fi
            fi
        else
            print_error "Failed to send stop signal to process"
            return 1
        fi
        
        # Remove the PID file only if process is confirmed dead
        if ! ps -p "$pid" > /dev/null 2>&1; then
            rm -f "$PID_FILE"
            return 0
        else
            print_error "Process still running, PID file not removed"
            return 1
        fi
    fi
    
    # Check if stdio server is ready
    if check_ready; then
        local status
        status=$(cat "$PID_FILE") || return 1
        print_status "Found ready stdio server (Status: $status)"
        
        # Remove the status file
        rm -f "$PID_FILE"
        print_success "MCP stdio server status cleared"
        return 0
    fi
    
    print_warning "No MCP server is running"
    return 0
}

# Show server status
show_status() {
    print_status "MCP Server Status"
    print_status "================="
    
    local pid
    local status
    
    # Check if HTTP server is running
    if check_running; then
        pid=$(cat "$PID_FILE") || return 1
        print_success "HTTP server is running (PID: $pid)"
        if [ -f "$LOG_FILE" ]; then
            print_status "Log file: $LOG_FILE"
            print_status "Recent log entries:"
            tail -n 5 "$LOG_FILE" 2>/dev/null || print_warning "No log entries found"
        fi
        print_info "🌐 Server URL: http://localhost:8030 (or check log for actual URL)"
        print_info "📖 OpenAPI docs: http://localhost:8030/docs"
        print_info "📚 ReDoc docs: http://localhost:8030/redoc"
        print_info "🔧 MCP endpoint: http://localhost:8030/mcp/"
    elif check_ready; then
        status=$(cat "$PID_FILE") || return 1
        print_success "Stdio server is ready (Status: $status)"
        if [ -f "$LOG_FILE" ]; then
            print_status "Log file: $LOG_FILE"
            print_status "Recent log entries:"
            tail -n 5 "$LOG_FILE" 2>/dev/null || print_warning "No log entries found"
        fi
        print_status "To use with MCP clients, run: python -m src.maestro_mcp.server"
        print_info "💡 Tip: Use './start.sh --http' to start HTTP server for browser access"
    else
        print_warning "No MCP server is running"
        if [ -f "$PID_FILE" ]; then
            print_warning "Stale PID file found: $PID_FILE"
        fi
    fi
}

# Clean up stale files
cleanup() {
    print_status "Cleaning up stale files..."
    
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE") || return 1
        
        if [ "$pid" = "ready" ]; then
            rm -f "$PID_FILE"
            print_success "Removed stale status file"
            return 0
        fi
        
        if ! ps -p "$pid" > /dev/null 2>&1; then
            rm -f "$PID_FILE"
            print_success "Removed stale PID file"
        else
            print_warning "PID file contains running process, not removing"
        fi
    fi
}

# Restart server with specified mode
restart_server() {
    local mode=$1
    local restart_cmd="./start.sh"
    
    case "$mode" in
        "http")
            print_status "Restarting MCP HTTP server..."
            restart_cmd="$restart_cmd --http"
            ;;
        "stdio")
            print_status "Restarting MCP server..."
            restart_cmd="$restart_cmd --stdio"
            ;;
        *)
            print_error "Invalid restart mode: $mode"
            return 1
            ;;
    esac
    
    if ! stop_server; then
        print_error "Failed to stop server, cannot restart"
        return 1
    fi
    
    # Wait for resources to be freed
    sleep 2
    
    # Execute restart command
    if ! $restart_cmd; then
        print_error "Failed to restart server"
        return 1
    fi
    
    return 0
}

# Main execution
main() {
    print_status "Maestro Knowledge MCP Server Manager"
    print_status "====================================="
    
    case "${1:-stop}" in
        "stop")
            if ! stop_server; then
                exit 1
            fi
            ;;
        "status")
            if ! show_status; then
                exit 1
            fi
            ;;
        "cleanup")
            if ! cleanup; then
                exit 1
            fi
            ;;
        "restart")
            if ! restart_server "stdio"; then
                exit 1
            fi
            ;;
        "restart-http")
            if ! restart_server "http"; then
                exit 1
            fi
            ;;
        *)
            print_error "Unknown command: $1"
            print_status "Usage: $0 {stop|status|cleanup|restart|restart-http}"
            print_status "  stop         - Stop the MCP server"
            print_status "  status       - Show server status"
            print_status "  cleanup      - Clean up stale files"
            print_status "  restart      - Restart the MCP stdio server"
            print_status "  restart-http - Restart the MCP HTTP server"
            exit 1
            ;;
    esac
}

# Run main function
main "$@" 