# Maestro Knowledge CLI

A command-line interface for interacting with the Maestro Knowledge MCP server.

## Features

- **List vector databases**: List all available vector database instances
- **Environment variable support**: Configure MCP server URI via environment variables
- **Command-line flag override**: Override MCP server URI via command-line flags
- **Dry-run mode**: Test commands without making actual changes
- **Verbose output**: Get detailed information about operations
- **Silent mode**: Suppress success messages

## Installation

### Prerequisites

- Go 1.21 or later
- Access to a running Maestro Knowledge MCP server

### Building

```bash
cd cli
go build -o maestro-k src/*.go
```

## Usage

### Basic Commands

```bash
# Show help
./maestro-k --help

# Show version
./maestro-k --version

# List vector databases
./maestro-k list vector-db

# List vector databases with verbose output
./maestro-k list vector-db --verbose
```

### MCP Server Configuration

The CLI can connect to an MCP server using several methods:

#### 1. Environment Variable (Recommended)

Set the `MAESTRO_KNOWLEDGE_MCP_SERVER_URI` environment variable:

```bash
export MAESTRO_KNOWLEDGE_MCP_SERVER_URI="http://localhost:8030"
./maestro-k list vector-db
```

#### 2. .env File

Create a `.env` file in the current directory:

```bash
echo "MAESTRO_KNOWLEDGE_MCP_SERVER_URI=http://localhost:8030" > .env
./maestro-k list vector-db
```

#### 3. Command-line Flag

Override the MCP server URI via command-line flag:

```bash
./maestro-k list vector-db --mcp-server-uri="http://localhost:8030"
```

**Priority order**: Command-line flag > Environment variable > .env file > Default (http://localhost:8000)

### Global Flags

- `--verbose`: Show detailed output
- `--silent`: Suppress success messages
- `--dry-run`: Test commands without making changes
- `--mcp-server-uri`: Override MCP server URI
- `--help`: Show help information
- `--version`: Show version information

### List Command

The `list` command displays information about vector databases:

```bash
# List all vector databases
./maestro-k list vector-db

# List with verbose output
./maestro-k list vector-db --verbose

# Test the command without connecting to server
./maestro-k list vector-db --dry-run
```

#### Output Format

When databases are found, the output shows:
- Database name and type
- Collection name
- Document count

Example:
```
Found 2 vector database(s):

1. project_a_db (weaviate)
   Collection: ProjectADocuments
   Documents: 15

2. project_b_db (milvus)
   Collection: ProjectBDocuments
   Documents: 8
```

## Examples

### Complete Workflow

1. **Start the MCP server**:
   ```bash
   cd /path/to/maestro-knowledge
   ./start.sh --http
   ```

2. **List databases**:
   ```bash
   cd cli
   ./maestro-k list vector-db --mcp-server-uri="http://localhost:8030"
   ```

3. **List with verbose output**:
   ```bash
   ./maestro-k list vector-db --mcp-server-uri="http://localhost:8030" --verbose
   ```

### Examples

See the [examples/](examples/) directory for usage examples:

- [example_usage.sh](examples/example_usage.sh) - Comprehensive CLI usage demonstration with MCP server

### Testing

Run the integration test suite:

```bash
./test_integration.sh
```

This will test:
- CLI help functionality
- Dry-run mode
- Verbose mode
- Environment variable support
- Command-line flag override
- .env file support

## Troubleshooting

### Connection Issues

If you get connection errors:

1. **Check if the MCP server is running**:
   ```bash
   cd /path/to/maestro-knowledge
   ./stop.sh status
   ```

2. **Verify the server URI**:
   ```bash
   ./maestro-k list vector-db --mcp-server-uri="http://localhost:8030" --verbose
   ```

3. **Check server logs**:
   ```bash
   tail -f /path/to/maestro-knowledge/mcp_server.log
   ```

### Common Issues

- **"connection refused"**: MCP server is not running or wrong port
- **"HTTP error 404"**: Wrong endpoint or server not configured correctly
- **"failed to parse database list"**: Server response format issue

## Development

### Project Structure

```
cli/
├── src/
│   ├── main.go          # Main CLI entry point
│   ├── list.go          # List command implementation
│   ├── create.go        # Create command (placeholder)
│   ├── delete.go        # Delete command (placeholder)
│   ├── validate.go      # Validate command (placeholder)
│   └── mcp_client.go    # MCP server client
├── examples/
│   ├── example_usage.sh # Comprehensive CLI usage examples
│   └── README.md        # Examples documentation
├── tests/
│   ├── list_test.go     # List command tests
│   ├── create_test.go   # Create command tests
│   ├── delete_test.go   # Delete command tests
│   ├── validate_test.go # Validate command tests
│   └── main_test.go     # Main CLI tests
├── go.mod               # Go module dependencies
├── go.sum               # Go module checksums
├── test_integration.sh  # Integration test script
└── README.md           # This file
```

### Adding New Commands

1. Create a new command file (e.g., `src/new_command.go`)
2. Define the command using Cobra
3. Add the command to `main.go`
4. Update this README

### Testing

```bash
# Run integration tests
./test_integration.sh

# Build and test manually
go build -o maestro-k src/*.go
./maestro-k --help
```

## License

MIT License - see the main project LICENSE file for details. 