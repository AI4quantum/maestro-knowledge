# Maestro Knowledge MCP Server - API Guide

> **Current Version**: v2.1 (2025-01-13)
>
> **Breaking Changes**: This version includes significant API improvements for better LLM agent integration.

## What Changed

The Maestro Knowledge MCP server has been redesigned to be more intuitive and reliable for AI agents and application developers. All changes focus on making the API clearer, safer, and easier to use.

### Key Improvements

1. **Structured JSON Responses** - All tools now return consistent JSON instead of plain text
2. **Simplified Tool Set** - Reduced from 22 to 11 active tools by consolidating related functionality
3. **Auto-Bootstrap** - Collections auto-create database connections (Phase 8.5)
4. **Auto-Detection** - Embedding models auto-detected from environment
5. **Safety Features** - Destructive operations require explicit confirmation
6. **Consistent Naming** - Standardized parameter names across all tools
7. **Better Error Messages** - Error codes and actionable suggestions included

## Breaking Changes

### 1. JSON Response Format

**What Changed:** All MCP tools now return structured JSON instead of plain text.

**Before:**
```python
result = await client.call_tool("create_database", {...})
print(result)  # "Database 'mydb' created successfully"
```

**After:**
```python
import json

result = await client.call_tool("create_database", {...})
response = json.loads(result)

if response["status"] == "success":
    print(f"Database: {response['data']['database']}")
    print(f"Type: {response['data']['database_type']}")
else:
    print(f"Error: {response['error_code']}")
    print(f"Suggestion: {response['suggestion']}")
```

**Response Format:**
```json
{
  "status": "success",
  "message": "Human-readable summary",
  "data": {
    // Tool-specific data
  },
  "metadata": {
    "timestamp": "2025-01-13T12:00:00Z",
    "operation": "tool_name"
  }
}
```

**Error Format:**
```json
{
  "status": "error",
  "message": "Error description",
  "error_code": "DB_NOT_FOUND",
  "suggestion": "Use list_databases to see available databases"
}
```

### 2. Explicit Collection Parameter

**What Changed:** The `write_documents` tool now requires an explicit `collection` parameter.

**Before:**
```python
await client.call_tool("write_documents", {
    "database": "mydb",
    "documents": [...]
})  # Used implicit default collection
```

**After:**
```python
await client.call_tool("write_documents", {
    "database": "mydb",
    "collection": "docs",  # Now required
    "documents": [...]
})
```

### 3. Safety Confirmations

**What Changed:** Destructive operations require explicit `force=True` parameter.

**Affected Operations:**
- `delete_database`
- `delete_collection`
- `delete_documents`

**Example:**
```python
# This will fail with error
await client.call_tool("delete_database", {
    "database": "mydb"
})

# This will succeed
await client.call_tool("delete_database", {
    "database": "mydb",
    "force": True
})
```

### 4. Parameter Names

**What Changed:** Standardized parameter naming for consistency.

| Old Name | New Name |
|----------|----------|
| `db_name` | `database` |
| `db_type` | `database_type` |
| `collection_name` | `collection` |
| `doc_name` | `document_name` |

### 5. Tool Consolidation

**What Changed:** Reduced tool count by merging related functionality.

**Removed Tools:**
- `list_documents` → Use `search(query="*")` instead
- `get_supported_embeddings` → Now part of `get_database_info`
- `get_supported_chunking_strategies` → Now part of `get_database_info`

**Example:**
```python
# Before: Separate tools
embeddings = await client.call_tool("get_supported_embeddings", {...})
chunking = await client.call_tool("get_supported_chunking_strategies", {...})

# After: Single tool
info = await client.call_tool("get_database_info", {"database": "mydb"})
response = json.loads(info)
embeddings = response["data"]["supported_embeddings"]
chunking = response["data"]["supported_chunking"]
```

## Phase 8.5 Improvements (2025-01-13)

### Auto-Bootstrap Database Connections

**What Changed:** Collections now automatically create database connections when needed.

**Before (Phase 2.6):**
```python
# Step 1: Register database
await client.call_tool("register_database", {
    "database": "mydb",
    "database_type": "milvus",
    "collection": "docs",
    "embedding": "auto"
})

# Step 2: Setup database
await client.call_tool("setup_database", {"database": "mydb"})

# Step 3: Create collection
await client.call_tool("create_collection", {
    "database": "mydb",
    "collection": "docs"
})
```

**After (Phase 8.5):**
```python
# Single step: Create collection (auto-bootstraps connection)
await client.call_tool("create_collection", {
    "collection": "docs",
    "embedding": "auto"  # Optional - auto-detects from environment
})
```

**Benefits:**
- Reduced from 3 steps to 1 step
- No need to manage database connections manually
- Embedding auto-detection from environment variables
- Simpler mental model for users

### Auto-Detection of Embeddings

**What Changed:** Embedding models are now auto-detected from environment variables.

**Environment Variables:**
- `CUSTOM_EMBEDDING_URL` - URL of custom embedding service (e.g., `http://localhost:11434/api/embeddings`)
- `CUSTOM_EMBEDDING_MODEL` - Model name (e.g., `nomic-embed-text`)
- `CUSTOM_EMBEDDING_VECTORSIZE` - Vector dimension (e.g., `768`)

**Behavior:**
```python
# If custom embedding env vars are set:
embedding="auto"  # → Uses custom_local

# If no custom embedding configured:
embedding="auto"  # → Falls back to text-embedding-ada-002 (requires OPENAI_API_KEY)
```

**Example:**
```bash
# Configure custom embeddings
export CUSTOM_EMBEDDING_URL="http://localhost:11434/api/embeddings"
export CUSTOM_EMBEDDING_MODEL="nomic-embed-text"
export CUSTOM_EMBEDDING_VECTORSIZE="768"

# Now create_collection will auto-detect and use custom embeddings
```

### Optional URL Parameter

**What Changed:** The `url` parameter in `write_documents` is now optional.

**Before:**
```python
await client.call_tool("write_documents", {
    "collection": "docs",
    "documents": [
        {"url": "https://example.com/doc1.html"}  # Required
    ]
})
```

**After:**
```python
await client.call_tool("write_documents", {
    "collection": "docs",
    "documents": [
        {"text": "Direct text content"}  # url auto-generated from text hash
    ]
})
```

**Auto-Generated URLs:**
- Format: `text://hash-{first_8_chars_of_sha256}`
- Example: `text://hash-a1b2c3d4`
- Ensures unique document IDs even without explicit URLs

### Improved Default Chunking

**What Changed:** Default chunking strategy changed from "None" to "Sentence".

**Before:**
- Default: No chunking (entire document as single chunk)
- Required explicit chunking configuration for most use cases

**After:**
- Default: Sentence-based chunking (512 chars, respects sentence boundaries)
- Better out-of-box experience for most documents
- Can still override with custom chunking config

## Current API Reference

### Available Tools (11 total)

**Configuration (2 tools):**
- `get_config` - Get system configuration and capabilities
- `refresh_databases` - Sync with backend databases

**Collection Management (3 tools):**
- `create_collection` - Create a new collection
- `delete_collection` - Delete a collection (requires force=True)
- `list_collections` - List all collections

**Document Operations (3 tools):**
- `write_documents` - Write documents to a collection
- `delete_documents` - Delete documents (requires force=True)
- `get_document` - Retrieve a document

**Query Operations (2 tools):**
- `query` - Natural language query with text summary
- `search` - Vector search with structured results

### Common Workflows

#### Creating a Collection and Adding Documents

```python
import json

# 1. Create collection (auto-bootstraps database connection)
result = await client.call_tool("create_collection", {
    "collection": "docs",
    "embedding": "auto"  # Auto-detects from environment
})
response = json.loads(result)
print(f"Created: {response['data']['collection']}")

# 2. Write documents
result = await client.call_tool("write_documents", {
    "collection": "docs",
    "documents": [
        {
            "url": "https://example.com/doc1.html",
            "metadata": {"author": "Alice"}
        },
        {
            "text": "Direct text content",  # url auto-generated
            "metadata": {"author": "Bob"}
        }
    ]
})
response = json.loads(result)
print(f"Wrote {response['data']['documents_written']} documents")
```

#### Searching Documents

```python
# Search with filters
result = await client.call_tool("search", {
    "collection": "docs",
    "query": "machine learning",
    "limit": 10,
    "min_score": 0.8,
    "metadata_filters": {"author": "Alice"}
})

response = json.loads(result)
for doc in response["data"]["results"]:
    print(f"Score: {doc['score']}")
    print(f"Text: {doc['text']}")
    print(f"Citation: {doc['source_citation']}")
```

#### Deleting Resources

```python
# Delete documents (requires force)
result = await client.call_tool("delete_documents", {
    "collection": "docs",
    "document_ids": ["doc1", "doc2"],
    "force": True
})

# Delete collection (requires force)
result = await client.call_tool("delete_collection", {
    "collection": "docs",
    "force": True
})
```

## Error Codes

All errors include an `error_code` field for programmatic handling:

**Database Errors:**
- `DB_NOT_FOUND` - Database doesn't exist
- `DB_ALREADY_EXISTS` - Database name already in use
- `DB_CONNECTION_ERROR` - Cannot connect to database backend

**Collection Errors:**
- `COLL_NOT_FOUND` - Collection doesn't exist
- `COLL_ALREADY_EXISTS` - Collection name already in use

**Document Errors:**
- `DOC_NOT_FOUND` - Document doesn't exist
- `DOC_WRITE_ERROR` - Failed to write document

**Parameter Errors:**
- `PARAM_INVALID` - Invalid parameter value
- `PARAM_MISSING` - Required parameter not provided

**Configuration Errors:**
- `CONFIG_INVALID` - Invalid configuration
- `CONFIG_MISSING` - Required configuration not found

## Migration Checklist

- [ ] Update all tool calls to parse JSON responses
- [ ] Add `collection` parameter to `write_documents` calls
- [ ] Add `force=True` to all delete operations
- [ ] Update parameter names (`db_name` → `database`, etc.)
- [ ] Replace `list_documents` with `search(query="*")`
- [ ] Update error handling to check `error_code` field
- [ ] Test all integrations with new response format

## Benefits

**For Developers:**
- Structured responses are easier to parse and validate
- Error codes enable robust error handling
- Explicit parameters prevent accidental operations
- Consistent naming reduces cognitive load

**For AI Agents:**
- JSON format is natively parseable
- Clear error messages with suggestions
- No implicit behavior to learn
- Predictable API surface

## Support

For questions or issues:
- Check [README.md](../README.md) for quick start guide
- Review [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md) for API design rationale
- See [TESTING_GUIDE.md](TESTING_GUIDE.md) for testing guidelines
- Refer to [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines

## Future Features

Planned enhancements (not yet implemented):
- Ownership metadata for documents
- Access control and permissions
- See [FEATURES_ACCESS_CONTROL.md](FEATURES_ACCESS_CONTROL.md) for details