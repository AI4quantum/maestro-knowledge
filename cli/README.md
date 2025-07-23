# Maestro Knowledge CLI

A command-line interface for the Maestro Knowledge system, built in Go using the Cobra library.

## Overview

The `maestro-k` CLI provides tools for validating YAML configuration files and schemas used in the Maestro Knowledge system. It's designed to be fast, reliable, and easy to use.

## Features

- **YAML Validation**: Validate YAML files against JSON schemas
- **Flexible Input**: Support for both single YAML file validation and schema + YAML file validation
- **Verbose Output**: Detailed logging for debugging and troubleshooting
- **Silent Mode**: Clean output for CI/CD pipelines
- **Dry Run Mode**: Preview validation without making changes

## Installation

### Prerequisites

- Go 1.21 or later
- Git

### Building from Source

1. Navigate to the CLI directory:
   ```bash
   cd cli
   ```

2. Download dependencies:
   ```bash
   go mod download
   ```

3. Build the binary:
   ```bash
   go build -o ../maestro-k ./src
   ```

4. (Optional) Install globally:
   ```bash
   go install ./src
   ```

### Using the Build Script

From the CLI directory, run:
```bash
./build.sh
```

This will build the `maestro-k` binary in the parent directory.

## Usage

### Basic Commands

```bash
# Show help
maestro-k --help

# Show version
maestro-k --version

# Validate a YAML file (uses default schema)
maestro-k validate config.yaml

# Validate a YAML file against a specific schema
maestro-k validate schema.json config.yaml
```

### Global Options

- `--verbose`: Show detailed output including file paths and validation steps
- `--silent`: Suppress success messages (useful for CI/CD)
- `--dry-run`: Preview what would be validated without actually performing validation

### Examples

```bash
# Basic validation
maestro-k validate my-config.yaml

# Verbose validation with custom schema
maestro-k validate --verbose schema.json my-config.yaml

# Silent validation for CI/CD
maestro-k validate --silent config.yaml

# Dry run to see what would be validated
maestro-k validate --dry-run config.yaml
```

## Command Reference

### `validate` Command

Validates YAML files against schemas.

**Syntax:**
```bash
maestro-k validate [YAML_FILE] [SCHEMA_FILE]
```

**Arguments:**
- `YAML_FILE`: Path to the YAML file to validate
- `SCHEMA_FILE`: (Optional) Path to the JSON schema file. If not provided, uses default schema.

**Examples:**
```bash
# Validate against default schema
maestro-k validate config.yaml

# Validate against custom schema
maestro-k validate schema.json config.yaml
```

## Development

### Project Structure

```
cli/
├── src/
│   ├── main.go          # Main entry point
│   └── validate.go      # Validate command implementation
├── tests/
│   ├── main_test.go     # Core CLI tests
│   ├── validate_test.go # Validate command tests
│   ├── go.mod           # Test module configuration
│   └── yamls/           # Test YAML files
│       ├── local_milvus.yaml
│       └── remote_weaviate.yaml
├── build.sh             # Build script
├── tests.sh             # Test runner script
├── go.mod               # Go module file
├── go.sum               # Go module checksums
├── README.md            # This file
└── USAGE.md             # Original usage reference
```

### Adding New Commands

To add a new command:

1. Create a new file (e.g., `newcommand.go`)
2. Define the command using Cobra
3. Add it to the root command in `main.go`

Example:
```go
var newCmd = &cobra.Command{
    Use:   "new",
    Short: "Description of the new command",
    RunE: func(cmd *cobra.Command, args []string) error {
        // Implementation here
        return nil
    },
}

// In main.go, add:
rootCmd.AddCommand(newCmd)
```

### Testing

#### CLI Tests Only
Run tests from the CLI directory:
```bash
./tests.sh
```

Or run tests manually:
```bash
go test -v ./tests/
```

#### Combined Testing (from project root)
The main `tests.sh` script in the project root now supports running both Python and CLI tests:

```bash
# Run Python tests only (default)
./tests.sh

# Run CLI tests only
./tests.sh cli

# Run both Python and CLI tests
./tests.sh all
```

## Error Handling

The CLI follows these error handling conventions:

- **File Not Found**: Returns clear error messages with file paths
- **Validation Errors**: Provides detailed feedback about what failed validation
- **Invalid Arguments**: Shows usage help when arguments are incorrect
- **Exit Codes**: Uses appropriate exit codes (0 for success, 1 for errors)

## CI/CD

The CLI has automated CI/CD workflows:

### Continuous Integration
- **Trigger**: Push to `cli/` directory or pull requests
- **Workflow**: `.github/workflows/cli_ci.yml`
- **Actions**: Builds CLI, runs tests, validates functionality
- **Artifacts**: Uploads CLI binary for 7 days

### Release Builds
- **Trigger**: GitHub releases
- **Workflow**: `.github/workflows/cli_release.yml`
- **Actions**: Builds CLI for multiple platforms (Linux, macOS, Windows)
- **Artifacts**: Uploads platform-specific binaries for 30 days

### Local Workflow Testing
```bash
# Validate workflows locally
.github/workflows/validate_workflows.sh

# Test workflow steps locally (now integrated into main tests.sh)
./tests.sh cli

# Test with act (if installed)
act push -W .github/workflows/cli_ci.yml
```

## Contributing

1. Follow Go coding conventions
2. Add tests for new functionality
3. Update documentation for new commands
4. Ensure all tests pass before submitting
5. CI/CD will automatically validate your changes

## License

This CLI is part of the Maestro Knowledge project and follows the same license terms. 