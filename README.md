# Maestro Knowledge

A modular vector database interface supporting multiple backends (Weaviate, Milvus) with a unified API and flexible embedding strategies.

## Features

- **Multi-backend support**: Weaviate and Milvus vector databases
- **Flexible embedding strategies**: Support for pre-computed vectors and multiple embedding models
- **Unified API**: Consistent interface across different vector database implementations
- **Factory pattern**: Easy creation and switching between database types
- **MCP Server**: Model Context Protocol server for AI agent integration
- **Document management**: Write, read, delete, and query documents
- **Metadata support**: Rich metadata handling for documents

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

## MCP Server

The project includes a Model Context Protocol (MCP) server that exposes vector database functionality to AI agents through a standardized interface.

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

- **create_vector_database**: Create a new vector database instance
- **setup_database**: Set up the current vector database with specified embedding
- **get_supported_embeddings**: Get list of supported embedding models
- **write_document**: Write a single document with specified embedding strategy
- **write_documents**: Write multiple documents with specified embedding strategy
- **list_documents**: List documents from the database
- **count_documents**: Get document count
- **delete_document**: Delete a single document
- **delete_documents**: Delete multiple documents
- **delete_collection**: Delete an entire collection
- **cleanup**: Clean up resources
- **get_database_info**: Get database information including supported embeddings

For more details, see [src/maestro_mcp/README.md](src/maestro_mcp/README.md).

## Examples

See the [examples/](examples/) directory for usage examples:

- [Weaviate Example](examples/weaviate_example.py) - Demonstrates Weaviate with different embedding models
- [Milvus Example](examples/milvus_example.py) - Shows Milvus with pre-computed vectors and embedding models
- [MCP Server Example](examples/mcp_example.py)

## Testing

```bash
# Run tests
./tests.sh

# Or run individual test files
python -m pytest tests/

# Run YAML schema validation tests
pytest tests/test_vector_database_yamls.py -v
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
├── start.sh                 # MCP server start script
├── stop.sh                  # MCP server stop script
├── tests/                   # Test suite
│   ├── test_vector_db_*.py  # Vector database tests
│   ├── test_mcp_server.py   # MCP server tests
│   ├── test_integration_*.py # Integration tests
│   ├── test_vector_database_yamls.py # YAML schema validation tests
│   └── yamls/               # YAML configuration examples
│       ├── local_milvus.yaml
│       └── remote_weaviate.yaml
├── examples/                # Usage examples
│   ├── weaviate_example.py  # Weaviate usage
│   ├── milvus_example.py    # Milvus usage
│   └── mcp_example.py       # MCP server usage
├── schemas/                 # JSON schemas
│   ├── vector-database-schema.json # Vector database configuration schema
│   └── README.md            # Schema documentation
└── docs/                    # Documentation
    └── CONTRIBUTING.md      # Contribution guidelines
```

## Environment Variables

- `VECTOR_DB_TYPE`: Default vector database type (defaults to "weaviate")
- `OPENAI_API_KEY`: Required for OpenAI embedding models
- Database-specific environment variables for Weaviate and Milvus connections

## Contributing

See [CONTRIBUTING.md](docs/CONTRIBUTING.md) for contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE) file for details.
