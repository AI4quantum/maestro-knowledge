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
    "url": str,               # Optional: Source URL (auto-generated if empty)
    "metadata": dict          # Optional: Custom metadata
}
```

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

## Error Handling

All tools return JSON responses with consistent structure:

**Success Response:**
```json
{
    "status": "success",
    "message": "Operation completed",
    "data": { ... }
}
```

**Error Response:**
```json
{
    "status": "error",
    "error_code": "COLL_NOT_FOUND",
    "message": "Collection 'docs' not found",
    "details": { ... },
    "suggestion": "Create the collection first: create_collection(collection='docs')"
}
```

---

## Environment Variables

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