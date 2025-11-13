# MCP API Reference

**Last Updated**: 2025-01-13 (Phase 9 - API Cleanup Complete)

This document provides the complete reference for all active MCP tools in the Maestro Knowledge system.

---

## Quick Reference

**Total Active Tools**: 11

| Category | Tools |
|----------|-------|
| Document Operations | 3 tools |
| Collection Operations | 4 tools |
| Query Operations | 2 tools |
| System Operations | 2 tools |

---

## Document Operations

### 1. write_documents

Write one or more documents to a collection.

**Signature:**
```python
write_documents(
    collection: str,           # Required: Collection name
    documents: list[dict]      # Required: List of document objects
) -> str
```

**Document Format:**
```python
{
    "text": str,              # Required: Document content
    "url": str,               # Optional: Source URL or identifier (auto-generated from text hash if empty)
    "metadata": dict          # Optional: Custom metadata
}
```

**Note**: In Phase 8.5, the `url` field became optional. If not provided or empty, it will be auto-generated from the text content hash.

**Example:**
```python
write_documents(
    collection="docs",
    documents=[
        {
            "text": "Python is a programming language",
            "url": "https://example.com/python",
            "metadata": {"author": "John", "category": "tech"}
        }
    ]
)
```

---

### 2. delete_documents

Delete specific documents from a collection by their IDs.

**Signature:**
```python
delete_documents(
    collection: str,           # Required: Collection name
    document_ids: list[str],   # Required: List of document IDs to delete
    force: bool = False        # Optional: Skip safety checks if True
) -> str
```

**Safety**: By default (`force=False`), requires explicit confirmation. Set `force=True` to proceed.

**Example:**
```python
delete_documents(
    collection="docs",
    document_ids=["doc_123", "doc_456"],
    force=True
)
```

---

### 3. get_document

Retrieve a specific document by its ID.

**Signature:**
```python
get_document(
    collection: str,           # Required: Collection name
    document_id: str           # Required: Document ID
) -> str
```

**Example:**
```python
get_document(
    collection="docs",
    document_id="doc_123"
)
```

---

## Collection Operations

### 4. create_collection

Create a new collection with specified embedding model and chunking configuration.

**Signature:**
```python
create_collection(
    collection: str,                    # Required: Collection name
    database: str | None = None,        # Optional: For backward compatibility (defaults to collection)
    embedding: str = "auto",            # Optional: Embedding model (auto-detects from environment)
    chunking_config: dict | None = None # Optional: Chunking configuration
) -> str
```

**Embedding Options:**
- `"auto"` (default) - Auto-detect from environment (custom_local if configured, else OpenAI)
- `"text-embedding-ada-002"` - OpenAI Ada-002
- `"text-embedding-3-small"` - OpenAI 3-small
- `"text-embedding-3-large"` - OpenAI 3-large
- `"custom_local"` - Custom embedding (requires env vars)

**Chunking Config Example:**
```python
{
    "strategy": "Sentence",
    "parameters": {
        "chunk_size": 512,
        "overlap": 1
    }
}
```

**Example:**
```python
create_collection(
    collection="docs",
    embedding="auto",
    chunking_config={
        "strategy": "Sentence",
        "parameters": {"chunk_size": 512, "overlap": 1}
    }
)
```

---

### 5. delete_collection

Delete an entire collection and all its contents.

**Signature:**
```python
delete_collection(
    collection: str,           # Required: Collection name
    force: bool = False        # Optional: Skip safety checks if True
) -> str
```

**Safety**: By default (`force=False`), checks if collection is empty. Set `force=True` to delete regardless.

**Example:**
```python
delete_collection(
    collection="docs",
    force=True
)
```

---

### 6. get_collection

Get detailed information about a collection.

**Signature:**
```python
get_collection(
    collection: str | None = None,  # Optional: Collection name (defaults to first registered)
    include_count: bool = False     # Optional: Include document count
) -> str
```

**Returns:**
- Collection name
- Embedding model details
- Chunking configuration
- Document count (if `include_count=True`)
- Creation timestamp

**Example:**
```python
get_collection(
    collection="docs",
    include_count=True
)
```

---

### 7. list_collections

List all collections in the system.

**Signature:**
```python
list_collections() -> str
```

**Returns:**
- List of collection names
- Embedding model for each
- Creation timestamp for each

**Example:**
```python
list_collections()
```

---

## Query Operations

### 8. query

Perform a semantic search across a collection.

**Signature:**
```python
query(
    query: str,                    # Required: Search query
    limit: int = 5,                # Optional: Max results (default: 5)
    collection: str | None = None  # Optional: Collection name (defaults to first registered)
) -> str
```

**Returns:**
- Matching documents with similarity scores
- Source URLs
- Ready-to-use citations
- Metadata

**Example:**
```python
query(
    query="What is Python?",
    limit=10,
    collection="docs"
)
```

---

### 9. search

Advanced semantic search with filtering and quality controls.

**Signature:**
```python
search(
    query: str,                         # Required: Search query
    limit: int = 5,                     # Optional: Max results (default: 5)
    collection: str | None = None,      # Optional: Collection name
    min_score: float | None = None,     # Optional: Minimum similarity score (0-1)
    metadata_filters: dict | None = None # Optional: Filter by metadata fields
) -> str
```

**Metadata Filters Example:**
```python
{
    "author": "John",
    "category": "tech"
}
```

**Example:**
```python
search(
    query="Python programming",
    limit=10,
    collection="docs",
    min_score=0.7,
    metadata_filters={"category": "tech"}
)
```

---

## System Operations

### 10. get_config

Get system configuration and available options.

**Signature:**
```python
get_config(
    include_embeddings: bool = False,  # Optional: Include supported embedding models
    include_chunking: bool = False     # Optional: Include supported chunking strategies
) -> str
```

**Returns:**
- Backend type (Milvus/Weaviate)
- Collections count
- Total document count
- Supported embeddings (if requested)
- Supported chunking strategies (if requested)

**Example:**
```python
get_config(
    include_embeddings=True,
    include_chunking=True
)
```

---

### 11. refresh_databases

Discover and register collections from connected backends.

**Signature:**
```python
refresh_databases() -> str
```

**Purpose**: Syncs the in-memory registry with actual collections in Milvus/Weaviate.

**Returns:**
- Number of collections discovered
- Breakdown by backend (Milvus/Weaviate)

**Example:**
```python
refresh_databases()
```

---

## Disabled Tools

The following tools are disabled and not exposed in the MCP API:

- `create_database_DISABLED()` - Use `create_collection()` instead
- `delete_database_DISABLED()` - Use `delete_collection()` instead  
- `list_databases_DISABLED()` - Use `list_collections()` instead

These were disabled because they exposed confusing "database" terminology. See `docs/DATABASE_COLLECTION_ARCHITECTURE.md` for details.

---

## Common Patterns

### Creating and Populating a Collection

```python
# 1. Create collection
create_collection(
    collection="my_docs",
    embedding="auto"
)

# 2. Write documents
write_documents(
    collection="my_docs",
    documents=[
        {"text": "Document 1", "url": "https://example.com/1"},
        {"text": "Document 2", "url": "https://example.com/2"}
    ]
)

# 3. Query
query(
    query="What is in document 1?",
    collection="my_docs"
)
```

### Cleaning Up

```python
# Delete specific documents
delete_documents(
    collection="my_docs",
    document_ids=["doc_123"],
    force=True
)

# Or delete entire collection
delete_collection(
    collection="my_docs",
    force=True
)
```

### Advanced Search

```python
# Search with quality controls
search(
    query="Python programming",
    collection="my_docs",
    limit=10,
    min_score=0.7,
    metadata_filters={"category": "tech", "author": "John"}
)
```

---

## Response Format Documentation

All tools return JSON responses with consistent structure.

### Success Response Structure

```json
{
    "status": "success",
    "message": "Human-readable summary of the operation",
    "data": {
        // Tool-specific data (varies by operation)
    },
    "metadata": {
        // Optional metadata (included when relevant)
        "timestamp": "2025-01-13T16:00:00.000Z",
        "operation": "tool_name",
        "database": "collection_name",
        "collection": "collection_name"
    }
}
```

**Fields**:
- `status`: Always "success" for successful operations
- `message`: Human-readable summary (e.g., "Wrote 3 documents to collection 'docs'")
- `data`: Tool-specific response data (structure varies by tool)
- `metadata`: Optional metadata about the operation (timestamp, operation name, etc.)

### Error Response Structure

```json
{
    "status": "error",
    "error_code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
        // Additional error context
    },
    "suggestion": "Actionable suggestion to fix the error"
}
```

**Fields**:
- `status`: Always "error" for failed operations
- `error_code`: Machine-readable error code (see Error Codes section)
- `message`: Human-readable error description
- `details`: Optional additional context (parameters, available options, etc.)
- `suggestion`: Optional actionable suggestion to resolve the error

### Error Codes

Error codes follow a consistent naming convention with prefixes:

**Database/Collection Errors**:
- `DB_NOT_FOUND`: Collection not found
- `DB_NOT_INITIALIZED`: Collection not properly initialized
- `COLL_NOT_FOUND`: Collection not found
- `COLL_ALREADY_EXISTS`: Collection already exists
- `COLL_NOT_EMPTY`: Collection contains documents (for delete operations)
- `COLL_CREATION_FAILED`: Collection creation failed
- `COLL_DELETE_FAILED`: Collection deletion failed
- `COLL_INFO_FAILED`: Failed to retrieve collection information

**Document Errors**:
- `DOC_WRITE_FAILED`: Document write operation failed
- `DOC_DELETE_FAILED`: Document deletion failed
- `DOC_DELETE_REQUIRES_FORCE`: Deletion requires force=True
- `DOC_NOT_FOUND`: Document not found
- `DOC_RETRIEVAL_FAILED`: Document retrieval failed

**Parameter Errors**:
- `PARAM_INVALID_VALUE`: Parameter value out of valid range
- `PARAM_MISSING`: Required parameter missing

**Configuration Errors**:
- `CONFIG_EMBEDDING_INVALID`: Invalid embedding model specified

**System Errors**:
- `NO_DATABASES`: No collections registered
- `QUERY_FAILED`: Query operation failed
- `SEARCH_FAILED`: Search operation failed
- `REFRESH_FAILED`: Database refresh failed

### Response Examples by Tool

**write_documents Success**:
```json
{
    "status": "success",
    "message": "Wrote 2 documents to collection 'docs'",
    "data": {
        "documents_written": 2,
        "chunks_created": 8,
        "collection": "docs",
        "embedding_model": "text-embedding-ada-002"
    },
    "metadata": {
        "timestamp": "2025-01-13T16:00:00.000Z",
        "operation": "write_documents",
        "collection": "docs",
        "collection_total_documents": 10,
        "sample_query": "What is Python programming"
    }
}
```

**query Success**:
```json
{
    "status": "success",
    "message": "Query completed for 'What is Python?'",
    "data": {
        "query": "What is Python?",
        "summary": "Python is a high-level programming language...",
        "limit": 5
    },
    "metadata": {
        "timestamp": "2025-01-13T16:00:00.000Z",
        "operation": "query",
        "database": "docs",
        "collection": "docs"
    }
}
```

**search Success**:
```json
{
    "status": "success",
    "message": "Found 3 results in collection 'docs'",
    "data": {
        "query": "Python programming",
        "results_count": 3,
        "results": [
            {
                "text": "Python is a programming language...",
                "url": "https://example.com/python",
                "source_citation": "[Python Guide](https://example.com/python)",
                "score": 0.92,
                "metadata": {"author": "John"},
                "rank": 1
            }
        ]
    },
    "metadata": {
        "timestamp": "2025-01-13T16:00:00.000Z",
        "operation": "search",
        "collection": "docs",
        "limit": 10
    }
}
```

**Error Example**:
```json
{
    "status": "error",
    "error_code": "COLL_NOT_FOUND",
    "message": "Collection 'docs' not found",
    "details": {
        "collection": "docs",
        "database": "docs",
        "available_collections": ["other_collection"]
    },
    "suggestion": "Create the collection first: create_collection(collection='docs')"
}
```

---

## Environment Variables
---

## Parameter Validation

All tools validate their parameters and return clear error messages for invalid values.

### Common Parameter Constraints

**limit** (query, search):
- Type: integer
- Range: 1-100 (inclusive)
- Default: 5
- Error: `PARAM_INVALID_VALUE` if out of range

**min_score** (search):
- Type: float
- Range: 0.0-1.0 (inclusive)
- Optional: Yes
- Error: Invalid if outside range
- Interpretation:
  - 0.0 = include all results
  - 0.5 = moderate similarity threshold
  - 0.7 = good similarity threshold
  - 0.8 = high similarity threshold
  - 1.0 = exact matches only

**force** (delete_documents, delete_collection):
- Type: boolean
- Default: False
- Purpose: Safety mechanism requiring explicit confirmation for destructive operations
- Error: Operation rejected if False and would delete data

**collection**:
- Type: string
- Required: Yes (for most operations)
- Validation: Must exist (checked at runtime)
- Error: `COLL_NOT_FOUND` if collection doesn't exist

**embedding** (create_collection):
- Type: string
- Default: "auto"
- Valid values:
  - "auto" - Auto-detect from environment (recommended)
  - "text-embedding-ada-002" - OpenAI default
  - "text-embedding-3-small" - OpenAI small
  - "text-embedding-3-large" - OpenAI large
  - "custom_local" - Custom embedding (requires env vars)
- Error: `CONFIG_EMBEDDING_INVALID` if unsupported

**documents** (write_documents):
- Type: list of dicts
- Required: Yes
- Minimum: 1 document
- Each document must have:
  - `text` (required): string
  - `url` (optional): string (auto-generated if empty)
  - `metadata` (optional): dict
- Error: Validation error if empty or missing required fields

**metadata_filters** (search):
- Type: dict
- Optional: Yes
- Format: `{"field_name": "value"}`
- Behavior: AND logic (all filters must match)
- Example: `{"author": "John", "category": "tech"}`


### Required for OpenAI Embeddings
```bash
OPENAI_API_KEY=sk-...
```

### Required for Custom Embeddings
```bash
CUSTOM_EMBEDDING_URL=http://localhost:11434/api/embeddings
CUSTOM_EMBEDDING_MODEL=nomic-embed-text
CUSTOM_EMBEDDING_VECTORSIZE=768
```

### Backend Configuration
```bash
# Milvus
MILVUS_URI=http://localhost:19530

# Weaviate
WEAVIATE_URL=http://localhost:8080
```

---

## See Also

- **Architecture Issues**: `docs/DATABASE_COLLECTION_ARCHITECTURE.md`
- **Migration Guide**: `docs/MIGRATION_GUIDE.md`
- **API Cleanup Summary**: `docs/API_CLEANUP_SUMMARY.md`
- **Testing Guide**: `tests/e2e/README.md`