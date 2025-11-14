# Maestro Vector Database MCP Server

This MCP (Model Context Protocol) server exposes the Maestro Vector Database functionality to AI agents through a standardized interface with flexible embedding strategies and multi-database support. The server is built using **FastMCP**, a modern and efficient implementation of the Model Context Protocol.

## FastMCP Implementation

This MCP server has been migrated from the standard MCP library to **FastMCP** for improved performance and developer experience:

### Benefits of FastMCP
- **Better Performance**: Optimized for high-throughput operations
- **Type Safety**: Full Pydantic integration for input validation
- **Modern API**: Cleaner, more intuitive tool definitions
- **Enhanced Error Handling**: Better error messages and validation
- **Async Support**: Native async/await support for all operations

## Features

The MCP server provides the following tools for vector database operations with support for multiple simultaneous databases:

### Database Management
- **create_vector_database_tool**: Create a new vector database instance (Weaviate or Milvus) with a unique name
- **setup_database**: Set up a vector database and create collections with specified embedding
- **get_supported_embeddings**: Get list of supported embedding models for a specific database
- **list_collections**: List all collections in a specific vector database
- **cleanup**: Clean up resources and close database connections for a specific database
- **get_database_info**: Get information about a specific vector database including supported embeddings
- **list_databases**: List all available vector database instances

### Document Operations
- **write_document**: Write a single document to a specific vector database with specified embedding strategy
- **write_documents**: Write multiple documents to a specific vector database with specified embedding strategy
- **list_documents**: List documents from a specific vector database
- **list_documents_in_collection**: List documents from a specific collection in a vector database
- **count_documents**: Get the current count of documents in a specific collection
- **query**: Query documents using natural language with semantic search

### Document Management
- **delete_document**: Delete a single document by ID from a specific database
- **delete_documents**: Delete multiple documents by IDs from a specific database
- **delete_collection**: Delete an entire collection from a specific database

## Query Functionality

The MCP server provides natural language querying capabilities that work across both Weaviate and Milvus vector databases:

### Query Features

- **Natural Language Queries**: Use plain English to search through your documents
- **Semantic Search**: Finds relevant documents based on meaning, not just keywords
- **Multi-Database Support**: Query works consistently across Weaviate and Milvus
- **Collection Targeting**: Optionally specify which collection to search in
- **Configurable Limits**: Control how many documents to consider in the search
- **Rich Results**: Returns relevant document content with metadata

### Query Parameters

- **db_name**: The name of the vector database to query
- **query**: The natural language query string
- **limit**: Maximum number of documents to consider (default: 5)
- **collection_name**: Optional collection name to restrict search to

### Query Examples

```json
{
  "name": "query",
  "arguments": {
    "database": "my_database",
    "query": "What is machine learning?",
    "limit": 10,
    "collection": "technical_docs"
  }
}
```

This will search through the documents in the specified database and return relevant results based on semantic similarity to the query.

## Embedding Strategies

The MCP server supports flexible embedding strategies for both vector databases:

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
- `custom_local`: Uses a custom, local embedding endpoint. **All three** `CUSTOM_EMBEDDING_URL`, `CUSTOM_EMBEDDING_MODEL`, and `CUSTOM_EMBEDDING_VECTORSIZE` environment variables are **required** for this embedding type. `CUSTOM_EMBEDDING_API_KEY` is optional.


## Multi-Database Support

The MCP server now supports managing multiple vector databases simultaneously. Each database is identified by a unique name, allowing you to:

- Create and manage multiple databases of different types (Weaviate, Milvus)
- Use different databases for different purposes or projects
- Operate on specific databases by providing the database name in tool calls
- List all available databases and their status

### Key Benefits

- **Isolation**: Each database operates independently with its own collections and documents
- **Flexibility**: Mix different database types (Weaviate and Milvus) in the same session
- **Organization**: Use descriptive names to organize databases by project or purpose
- **Resource Management**: Clean up specific databases without affecting others

## Usage

### Running the Server

```bash
# From the project root
./start.sh

# Stop the server
./stop.sh

# Check server status
./stop.sh status

# Restart the server
./stop.sh restart
```

### Configuration

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

### Example Usage

Here's how an AI agent might interact with multiple vector databases:

1. **Register and set up multiple vector databases** (3-step workflow):
   ```json
   {
     "name": "register_database",
     "arguments": {
       "database": "project_a_db",
       "database_type": "weaviate",
       "collection": "ProjectADocuments"
     }
   }
   ```
   ```json
   {
     "name": "setup_database",
     "arguments": {
       "database": "project_a_db",
       "embedding": "text-embedding-ada-002"
     }
   }
   ```
   ```json
   {
     "name": "create_collection",
     "arguments": {
       "database": "project_a_db",
       "collection": "ProjectADocuments",
       "embedding": "text-embedding-ada-002"
     }
   }
   ```

2. **List all available databases**:
   ```json
   {
     "name": "list_databases",
     "arguments": {}
   }
   ```

3. **Get supported embeddings for a specific database**:
   ```json
   {
     "name": "get_supported_embeddings",
     "arguments": {
       "database": "project_a_db"
     }
   }
   ```

4. **Write documents** (uses collection's embedding model):
   ```json
   {
     "name": "write_document",
     "arguments": {
       "database": "project_a_db",
       "url": "https://example.com/doc1",
       "text": "This is the content of the document",
       "metadata": {
         "author": "John Doe",
         "date": "2024-01-01"
       }
     }
   }
   ```
   ```json
   {
     "name": "write_document",
     "arguments": {
       "database": "project_b_db",
       "url": "https://example.com/doc2",
       "text": "This document has a pre-computed vector",
       "metadata": {
         "author": "Jane Smith",
         "date": "2024-01-02"
       },
       "vector": [0.1, 0.2, 0.3, ...]
     }
   }
   ```

5. **Write multiple documents**:
   ```json
   {
     "name": "write_documents",
     "arguments": {
       "database": "project_a_db",
       "documents": [
         {
           "url": "https://example.com/doc3",
           "text": "First document",
           "metadata": {"category": "tech"}
         },
         {
           "url": "https://example.com/doc4",
           "text": "Second document",
           "metadata": {"category": "science"}
         }
       ]
     }
   }
   ```

6. **Query with search quality controls**:
   ```json
   {
     "name": "query",
     "arguments": {
       "database": "project_a_db",
       "query": "What is the main topic of the documents?",
       "limit": 10,
       "collection": "ProjectADocuments",
       "min_score": 0.8,
       "metadata_filters": {"category": "tech"}
     }
   }
   ```

7. **Search with quality controls**:
   ```json
   {
     "name": "search",
     "arguments": {
       "database": "project_a_db",
       "query": "machine learning concepts",
       "limit": 5,
       "min_score": 0.7,
       "metadata_filters": {"author": "John Doe"}
     }
   }
   ```

8. **List documents from a specific database**:
   ```json
   {
     "name": "list_documents",
     "arguments": {
       "database": "project_a_db",
       "limit": 10,
       "offset": 0
     }
   }
   ```

9. **List documents from a specific collection**:
   ```json
   {
     "name": "list_documents_in_collection",
     "arguments": {
       "database": "project_a_db",
       "collection": "ProjectADocuments",
       "limit": 10,
       "offset": 0
     }
   }
   ```

10. **Get information about a specific database**:
     ```json
     {
       "name": "get_database_info",
       "arguments": {
         "database": "project_a_db"
       }
     }
     ```

11. **Clean up a specific database**:
     ```json
     {
       "name": "cleanup",
       "arguments": {
         "database": "project_a_db"
       }
     }
     ```

## Environment Variables

The server respects the following environment variables:

### Database Configuration
- `VECTOR_DB_TYPE`: Default vector database type (defaults to "weaviate")
- `MILVUS_URI`: Milvus connection URI (e.g., `http://localhost:19530`)
- `WEAVIATE_URL`: Weaviate connection URL (e.g., `http://localhost:8080`)

### Embedding Configuration
- `OPENAI_API_KEY`: Required for OpenAI embedding models
- `CUSTOM_EMBEDDING_URL`: The URL for the custom embedding endpoint (required for `custom_local` embedding for Milvus).
- `CUSTOM_EMBEDDING_API_KEY`: The API key for the custom embedding endpoint (optional, but recommended for authentication).
- `CUSTOM_EMBEDDING_MODEL`: The model name for the custom embedding endpoint (required for `custom_local` embedding for Milvus).
- `CUSTOM_EMBEDDING_VECTORSIZE`: The vector dimension for the `custom_local` embedding model (required when using `custom_local`).
- `CUSTOM_EMBEDDING_HEADERS`: Custom headers for your embedding provider when using `embedding: custom_local`.
  **Important**: Due to shell parsing, the value **must be enclosed in single quotes** in your `.env` file to handle special characters correctly.
  - **Recommended format (JSON string):**
    ```
    CUSTOM_EMBEDDING_HEADERS='{"API_SECRET_KEY": "your-secret-key", "Another-Header": "value"}'
    ```
  - **Alternative format (key-value pairs):**
    ```
    CUSTOM_EMBEDDING_HEADERS='API_SECRET_KEY=your-secret-key,Another-Header=value'
    ```

### Timeout Configuration

All MCP tool operations have configurable timeouts to prevent hanging operations. You can customize timeouts using environment variables:

#### Global Timeout
- `MCP_TOOL_TIMEOUT`: Default timeout for all tools (default: 15 seconds)

#### Per-Operation Timeouts
Override specific operation timeouts using `MCP_TIMEOUT_<OPERATION>`:

```bash
# Database operations
export MCP_TIMEOUT_LIST_DATABASES=15        # List all databases (default: 15s)
export MCP_TIMEOUT_LIST_COLLECTIONS=15      # List collections (default: 15s)
export MCP_TIMEOUT_GET_DATABASE_INFO=15     # Get database info (default: 15s)
export MCP_TIMEOUT_GET_COLLECTION_INFO=30   # Get collection info (default: 30s)

# Collection operations
export MCP_TIMEOUT_CREATE_COLLECTION=60     # Create collection (default: 60s)
export MCP_TIMEOUT_SETUP_DATABASE=60        # Setup database (default: 60s)
export MCP_TIMEOUT_DELETE=60                # Delete operations (default: 60s)

# Document operations
export MCP_TIMEOUT_LIST_DOCUMENTS=30        # List documents (default: 30s)
export MCP_TIMEOUT_COUNT_DOCUMENTS=15       # Count documents (default: 15s)
export MCP_TIMEOUT_WRITE_SINGLE=900         # Write single document (default: 15 min)
export MCP_TIMEOUT_WRITE_BULK=3600          # Write bulk documents (default: 60 min)

# Query operations
export MCP_TIMEOUT_QUERY=30                 # Query documents (default: 30s)
export MCP_TIMEOUT_SEARCH=30                # Search documents (default: 30s)

# Maintenance operations
export MCP_TIMEOUT_CLEANUP=60               # Cleanup resources (default: 60s)
export MCP_TIMEOUT_RESYNC=60                # Resync databases (default: 60s)
export MCP_TIMEOUT_HEALTH=30                # Health check (default: 30s)
```

#### Example: Increase Timeout for Slow Backend

If your vector database backend is slow to respond (e.g., during initialization), increase the relevant timeouts:

```bash
# In your .env file or shell
export MCP_TIMEOUT_CREATE_COLLECTION=120    # 2 minutes
export MCP_TIMEOUT_LIST_COLLECTIONS=30      # 30 seconds
export MCP_TIMEOUT_WRITE_BULK=7200          # 2 hours for large bulk writes
```

#### Timeout Error Messages

When an operation times out, you'll receive a detailed error message with:
- The operation that timed out
- The timeout duration
- Troubleshooting steps
- The environment variable to adjust the timeout

## Error Handling

The server provides detailed error messages for common issues:
- Missing database initialization
- Invalid database types
- Unsupported embedding models
- Missing API keys for embedding services
- Connection errors
- Document operation failures
- Database not found errors
- Collection not found errors

## Dependencies

- `fastmcp`: FastMCP library for Model Context Protocol
- All existing Maestro Vector Database dependencies (Weaviate, Milvus, etc.)
- `openai`: Required for OpenAI embedding models 