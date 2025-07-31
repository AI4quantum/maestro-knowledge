# Maestro Knowledge

A modular vector database interface supporting multiple backends (Weaviate, Milvus) with a unified API and flexible embedding strategies.

## Features

- **Multi-backend support**: Weaviate and Milvus vector databases
- **Flexible embedding strategies**: Support for pre-computed vectors and multiple embedding models
- **Unified API**: Consistent interface across different vector database implementations
- **Factory pattern**: Easy creation and switching between database types
- **MCP Server**: Model Context Protocol server for AI agent integration with multi-database support
- **CLI Tool**: Command-line interface for vector database operations with YAML configuration
- **Document management**: Write, read, delete, and query documents
- **Collection management**: List and manage collections across vector databases
- **Metadata support**: Rich metadata handling for documents
- **Environment variable substitution**: Dynamic configuration with `{{ENV_VAR_NAME}}` syntax

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd maestro-knowledge

# Install dependencies
uv sync
```

### Basic Usage

```python
from src.vector_db import create_vector_database

# Create a vector database (defaults to Weaviate)
db = create_vector_database("weaviate", "MyCollection")

# Set up the database
db.setup()

# Write documents with default embedding
documents = [
    {
        "url": "https://example.com/doc1",
        "text": "This is a document about machine learning.",
        "metadata": {"topic": "ML", "author": "Alice"}
    }
]
db.write_documents(documents, embedding="default")

# List documents
docs = db.list_documents(limit=10)
print(f"Found {len(docs)} documents")

# Clean up
db.cleanup()
```

## Embedding Strategies

The library supports flexible embedding strategies for both vector databases:

### Supported Embedding Models

#### Weaviate
- `default`: Uses Weaviate's built-in text2vec-weaviate vectorizer
- `text2vec-weaviate`: Weaviate's built-in text vectorizer
- `text2vec-openai`: OpenAI's embedding models (requires API key)
- `text2vec-cohere`: Cohere's embedding models
- `text2vec-huggingface`: Hugging Face models
- `text-embedding-ada-002`: OpenAI's Ada-002 model
- `text-embedding-3-small`: OpenAI's text-embedding-3-small model
- `text-embedding-3-large`: OpenAI's text-embedding-3-large model

#### Milvus
- `default`: Uses pre-computed vectors if available, otherwise text-embedding-ada-002
- `text-embedding-ada-002`: OpenAI's Ada-002 embedding model
- `text-embedding-3-small`: OpenAI's text-embedding-3-small model
- `text-embedding-3-large`: OpenAI's text-embedding-3-large model
- `custom_local`: Uses a custom, local embedding endpoint (e.g., Ollama). Requires `CUSTOM_EMBEDDING_URL`, `CUSTOM_EMBEDDING_MODEL` environment variable, and optionally `CUSTOM_EMBEDDING_API_KEY`.

### Usage Examples

#### Using Pre-computed Vectors (Milvus)

```python
# Documents with pre-computed vectors
documents_with_vectors = [
    {
        "url": "https://example.com/doc1",
        "text": "Machine learning algorithms",
        "metadata": {"topic": "ML"},
        "vector": [0.1, 0.2, 0.3, ...]  # 1536-dimensional vector
    }
]

db.write_documents(documents_with_vectors, embedding="default")
```

#### Using Embedding Models

Simple example:

```python
# Documents without vectors (will be generated using embedding model)
documents_without_vectors = [
    {
        "url": "https://example.com/doc1",
        "text": "Machine learning algorithms",
        "metadata": {"topic": "ML"}
    }
]

# Use OpenAI's Ada-002 model (requires OPENAI_API_KEY)
db.write_documents(documents_without_vectors, embedding="text-embedding-ada-002")

# Use Weaviate's built-in vectorizer
db.write_documents(documents_without_vectors, embedding="text2vec-weaviate")

```

Using milvus with a custom embedding :

Ensure `CUSTOM_EMBEDDING_URL` and `CUSTOM_EMBEDDING_MODEL` are set in your environment variables, and optionally `CUSTOM_EMBEDDING_API_KEY` if your model requires authentication.

```bash
export CUSTOM_EMBEDDING_URL="http://localhost:11434/v1/"
export CUSTOM_EMBEDDING_MODEL="nomic-embed-text"
export CUSTOM_EMBEDDING_API_KEY="your-api-key"  # Optional
```
Then, you can create a Milvus database with a custom local embedding model:

```python
# Create a Milvus database with a specific dimension for a custom model (must match model)
db = create_vector_database("milvus", "MyCustomCollection", dimension=768)
db.setup(embedding="custom_local") # Setup with custom local model

# Documents without vectors (will be generated using embedding model)
documents_without_vectors = [
    {
        "url": "https://example.com/doc1",
        "text": "Machine learning algorithms",
        "metadata": {"topic": "ML"}
    }
]

# Use the custom local model
db.write_documents(documents_without_vectors, embedding="custom_local")
```

#### Checking Supported Embeddings

```python
# Get list of supported embedding models for the database
supported = db.supported_embeddings()
print(f"Supported embeddings: {supported}")
```

### Environment Variables for Embeddings

For OpenAI embedding models, set the following environment variable:
```bash
export OPENAI_API_KEY="your-openai-api-key"
```

## CLI Tool

The project includes a Go-based CLI tool for managing vector databases through the MCP server with support for YAML configuration and environment variable substitution.

### Installation

```bash
# Build the CLI tool
cd cli
go build -o maestro-k src/*.go

# Or use the build script
./build.sh
```

### Basic Usage

```bash
# List vector databases (using plural form)
./maestro-k list vector-dbs

# List embeddings for a specific database
./maestro-k list embeds my-database

# List collections for a specific database
./maestro-k list cols my-database

# List documents in a collection
./maestro-k list docs my-database my-collection

# Retrieve collection information
./maestro-k retrieve collection my-database
./maestro-k retrieve col my-database my-collection

# Retrieve document information
./maestro-k retrieve document my-database my-collection my-document
./maestro-k retrieve doc my-database my-collection my-document

# Get collection information (alternative command)
./maestro-k get collection my-database
./maestro-k get col my-database my-collection

# Get document information (alternative command)
./maestro-k get document my-database my-collection my-document
./maestro-k get doc my-database my-collection my-document

# Create vector database from YAML
./maestro-k create vector-db config.yaml

# Create collection in vector database
./maestro-k create collection my-database my-collection

# Create document in collection
./maestro-k create document my-database my-collection my-doc --file-name=document.txt

# Write document (alias for create document)
./maestro-k write document my-database my-collection my-doc --file-name=document.txt

# Delete vector database
./maestro-k delete vector-db my-db

# Delete collection
./maestro-k delete collection my-database my-collection

# Delete document
./maestro-k delete document my-database my-collection my-document

# Validate YAML configuration
./maestro-k validate config.yaml
```

### Configuration

The CLI supports multiple configuration methods:

```bash
# Environment variable
export MAESTRO_KNOWLEDGE_MCP_SERVER_URI="http://localhost:8030"

# Command-line flag
./maestro-k list vector-dbs --mcp-server-uri="http://localhost:8030"

# .env file
echo "MAESTRO_KNOWLEDGE_MCP_SERVER_URI=http://localhost:8030" > .env
```

### Environment Variable Substitution

The CLI supports environment variable substitution in YAML files using the `{{ENV_VAR_NAME}}` syntax:

```yaml
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: my-weaviate-db
spec:
  type: weaviate
  uri: {{WEAVIATE_URL}}
  collection_name: my_collection
  embedding: text-embedding-3-small
  mode: remote
```

When you run `./maestro-k create vector-db config.yaml`, the CLI will:
1. Load environment variables from `.env` file (if present)
2. Replace `{{WEAVIATE_URL}}` with the actual value from the environment
3. Process the YAML file with the substituted values

For more details, see [cli/README.md](cli/README.md).

## MCP Server

The project includes a Model Context Protocol (MCP) server that exposes vector database functionality to AI agents through a standardized interface with support for multiple simultaneous databases.

### Running the MCP Server

```bash
# Start the MCP server
./start.sh

# Stop the MCP server
./stop.sh

# Check server status
./stop.sh status

# Restart the server
./stop.sh restart
```

### MCP Configuration

Add the following to your MCP client configuration:

```json
{
  "mcpServers": {
    "maestro-vector-db": {
      "command": "python",
      "args": ["-m", "src.maestro_mcp.server"],
      "env": {
        "PYTHONPATH": "."
      }
    }
  }
}
```

### Available MCP Tools

- **create_vector_database_tool**: Create a new vector database instance
- **setup_database**: Set up a vector database with specified embedding
- **get_supported_embeddings**: Get list of supported embedding models
- **list_collections**: List all collections in a vector database
- **list_documents_in_collection**: List documents from a specific collection
- **write_document**: Write a single document with specified embedding strategy
- **write_documents**: Write multiple documents with specified embedding strategy
- **list_documents**: List documents from the database
- **count_documents**: Get document count
- **delete_document**: Delete a single document
- **delete_documents**: Delete multiple documents
- **delete_collection**: Delete an entire collection
- **cleanup**: Clean up resources for a specific database
- **get_database_info**: Get database information including supported embeddings
- **list_databases**: List all available vector database instances

### Multi-Database Support

The MCP server supports managing multiple vector databases simultaneously. Each database is identified by a unique name, allowing you to:

- Create and manage multiple databases of different types (Weaviate, Milvus)
- Use different databases for different purposes or projects
- Operate on specific databases by providing the database name in tool calls
- List all available databases and their status

For more details, see [src/maestro_mcp/README.md](src/maestro_mcp/README.md).

## Examples

See the [examples/](examples/) directory for usage examples:

- [Weaviate Example](examples/weaviate_example.py) - Demonstrates Weaviate with different embedding models
- [Milvus Example](examples/milvus_example.py) - Shows Milvus with pre-computed vectors and embedding models
- [MCP Server Example](examples/mcp_example.py)

## Available Scripts

The project includes several utility scripts for development and testing:

```bash
# Code quality and formatting
./tools/lint.sh              # Run linting and formatting checks

# MCP server management
./start.sh                   # Start the MCP server
./stop.sh                    # Stop the MCP server

# Testing
./test.sh [COMMAND]          # Run tests with options: cli, mcp, all, help
./test.sh cli                # Run only CLI tests (Go-based)
./test.sh mcp                # Run only MCP server tests (Python-based)
./test.sh all                # Run all tests (CLI + MCP + Integration)
./test.sh help               # Show test command help
./test-integration.sh        # Run CLI integration tests

# CLI tool
cd cli && ./build.sh         # Build the CLI tool
```

## Testing

```bash
# Run all tests (CLI + MCP + Integration)
./test.sh all

# Run specific test suites
./test.sh cli                # Run only CLI tests
./test.sh mcp                # Run only MCP server tests
./test.sh help               # Show test command help

# Run comprehensive test suite (recommended before PR)
./tools/lint.sh && ./test.sh all

# Or run individual test files
python -m pytest tests/

# Run YAML schema validation tests
pytest tests/test_vector_database_yamls.py -v

# Run integration tests
./test-integration.sh

# Run end-to-end tests
./tools/e2e.sh help                    # Show e2e test options
./tools/e2e.sh fast                    # Run fast e2e workflow
./tools/e2e.sh complete                # Run complete e2e workflow with error testing
./tools/e2e.sh all                     # Run both fast and complete workflows
```

## Project Structure

```
maestro-knowledge/
├── src/                     # Source code
│   ├── db/                  # Vector database implementations
│   │   ├── vector_db_base.py      # Abstract base class
│   │   ├── vector_db_weaviate.py  # Weaviate implementation
│   │   ├── vector_db_milvus.py    # Milvus implementation
│   │   └── vector_db_factory.py   # Factory function
│   ├── maestro_mcp/         # MCP server implementation
│   │   ├── server.py        # Main MCP server
│   │   ├── mcp_config.json  # MCP client configuration
│   │   └── README.md        # MCP server documentation
│   └── vector_db.py         # Main module exports
├── cli/                     # Go CLI tool
│   ├── src/                 # Go source code
│   ├── tests/               # CLI tests
│   ├── examples/            # CLI usage examples
│   ├── build.sh             # Build script
│   └── README.md            # CLI documentation
├── start.sh                 # MCP server start script
├── stop.sh                  # MCP server stop script
├── tools/                   # Development tools
│   ├── lint.sh              # Code linting and formatting
│   ├── e2e.sh               # End-to-end testing script
│   └── test-integration.sh  # Integration tests
├── test.sh                  # Test runner script (CLI, MCP, Integration)
├── tests/                   # Test suite
│   ├── test_vector_db_*.py  # Vector database tests
│   ├── test_mcp_server.py   # MCP server tests
│   ├── test_integration_*.py # Integration tests
│   ├── test_vector_database_yamls.py # YAML schema validation tests
│   └── yamls/               # YAML configuration examples
│       ├── test_local_milvus.yaml
│       └── test_remote_weaviate.yaml
├── examples/                # Usage examples
│   ├── weaviate_example.py  # Weaviate usage
│   ├── milvate_example.py   # Milvus usage
│   └── mcp_example.py       # MCP server usage
├── schemas/                 # JSON schemas
│   ├── vector-database-schema.json # Vector database configuration schema
│   └── README.md            # Schema documentation
└── docs/                    # Documentation
    ├── CONTRIBUTING.md      # Contribution guidelines
    └── PRESENTATION.md      # Project presentation
```

## Environment Variables

- `VECTOR_DB_TYPE`: Default vector database type (defaults to "weaviate")
- `OPENAI_API_KEY`: Required for OpenAI embedding models
- `MAESTRO_KNOWLEDGE_MCP_SERVER_URI`: MCP server URI for CLI tool
- Database-specific environment variables for Weaviate and Milvus connections

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for contribution guidelines.

### Pre-Pull Request Checklist

Before submitting a pull request, run the comprehensive test suite:

```bash
./tools/lint.sh && ./test.sh all
```

This ensures code quality, functionality, and integration with the CLI tool.

### Recommended Development Workflow

For a complete development workflow that tests everything end-to-end:

```bash
./start.sh && ./tools/e2e.sh fast && ./stop.sh
```

This workflow:
1. Starts the MCP server
2. Runs the fast end-to-end test suite
3. Stops the MCP server

This is useful for quickly validating that your changes work correctly in a real environment.

## License

Apache 2.0 License - see [LICENSE](LICENSE) file for details.
