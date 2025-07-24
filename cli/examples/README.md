# CLI Examples

This directory contains example scripts and usage patterns for the Maestro Knowledge CLI.

## Examples

### `example_usage.sh`

A comprehensive example script that demonstrates how to use the CLI with a real MCP server.

#### Features

- **Automatic MCP server detection**: Checks if the MCP server is running and starts it if needed
- **Multiple usage patterns**: Shows different ways to configure and use the CLI
- **Environment variable examples**: Demonstrates environment variable configuration
- **Command-line flag examples**: Shows command-line flag usage
- **Dry-run and verbose modes**: Examples of testing and debugging modes

#### Usage

```bash
# Make the script executable
chmod +x example_usage.sh

# Run the examples
./example_usage.sh
```

#### What it demonstrates

1. **Basic list command**: Simple usage without additional flags
2. **Verbose output**: Using `--verbose` for detailed information
3. **Environment variable configuration**: Setting `MAESTRO_KNOWLEDGE_MCP_SERVER_URI`
4. **`.env` file usage**: Loading configuration from `.env` files
5. **Dry-run mode**: Testing commands without making changes
6. **Silent mode**: Suppressing success messages

#### Prerequisites

- Go 1.21 or later
- Access to the Maestro Knowledge project root
- MCP server (will be started automatically if not running)

#### Output

The script will show:
- CLI build status
- MCP server status and startup
- Example command outputs
- Success/failure indicators

#### Troubleshooting

If the script fails:

1. **Check Go installation**: Ensure Go 1.21+ is installed
2. **Verify project structure**: Make sure you're in the correct directory
3. **Check MCP server**: The script will attempt to start the server automatically
4. **Review permissions**: Ensure the script is executable

## Adding New Examples

To add new examples:

1. Create your example script in this directory
2. Make it executable: `chmod +x your_example.sh`
3. Update this README.md with documentation
4. Test your example thoroughly

## Example Structure

```bash
#!/bin/bash
# Example: Your Example Name
# Description: What this example demonstrates

set -e

# Your example code here
echo "Running example..."

# Demonstrate CLI usage
./maestro-k --help
```

## Related Documentation

- [CLI README](../README.md) - Main CLI documentation
- [Project README](../../README.md) - Project overview
- [MCP Server Documentation](../../src/maestro_mcp/README.md) - MCP server details 