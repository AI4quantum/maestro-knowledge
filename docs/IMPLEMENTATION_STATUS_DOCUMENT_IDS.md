# Document ID Feature Implementation Status

**Date**: 2025-01-14  
**Feature**: Document ID Management (Phase 8.6)  
**Status**: Core Implementation Complete, Testing & Documentation Pending

## Overview

This document tracks the implementation of the Document ID feature as specified in `docs/FEATURE_DOCUMENT_IDS.md`. The feature introduces deterministic document IDs as the primary identifier for all document operations, replacing the previous reliance on optional URL/name metadata fields.

## Design Decision

**URL and document_name remain first-class parameters** (not just metadata):
- **Rationale**: Better API clarity, explicit deduplication checking, and backward compatibility
- **document_id**: Auto-generated 16-character SHA-256 hash
  - URL-based if URL provided (prevents duplicate writes for same URL)
  - Content-based if no URL (idempotent writes for same content)

## Completed Work

### 1. Core Backend Implementation ✅

#### New Module: `src/db/document_id.py`
```python
def generate_document_id(text: str, url: str | None = None) -> str:
    """Generate deterministic 16-char hex document ID.
    
    Priority:
    1. If URL provided: hash(URL)
    2. Otherwise: hash(text)
    """
```

#### Updated: `src/db/vector_db_milvus.py`
- **write_documents()**: Generates document_id, stores in metadata, tracks in stats
- **search()**: Extracts document_id to top level in results
- **list_documents()**: 
  - Returns document_id for each document
  - Deduplicates by document_id (one entry per document)
  - Added `metadata_filters` parameter for arbitrary filtering
- **delete_documents()**: Uses document_id filter (not internal DB IDs)
- **get_document()**: Parameter changed from `doc_name` to `document_id`
- **Removed**: `query()` and `create_query_agent()` methods

#### Updated: `src/db/vector_db_weaviate.py`
- Same changes as Milvus (see above)

#### Updated: `src/db/vector_db_base.py`
- **Removed**: `query()` and `create_query_agent()` abstract methods
- **Updated**: `list_documents()` signature to include `metadata_filters`
- **Updated**: `get_document()` parameter from `doc_name` to `document_id`

### 2. MCP Server Changes ✅

#### Updated: `src/maestro_mcp/server.py`
- **write_documents tool**: 
  - Extracts `document_ids` from backend stats
  - Returns document_ids list in response
- **list_documents tool** (NEW):
  - Lists documents with filtering by name, url, metadata_filters
  - Returns document_id, name, url, chunk count for each document
- **delete_documents tool**: Updated docstring to clarify uses document_id
- **get_document tool**: Parameter renamed from `document_name` to `document_id`
- **query tool**: REMOVED (redundant - just formatted search results)
- **Removed**: "query" from TIMEOUT_DEFAULTS configuration

### 3. Test Updates ✅

#### Removed Obsolete Tests
- `tests/test_query_functionality.py` - Tested removed query method
- `tests/test_mcp_query.py` - Tested removed query tool
- `tests/test_query_integration.py` - Integration tests for query

#### Fixed Tests
- `tests/e2e/test_functions.py`: Removed query tool call from `run_query_operations_tests()`

#### New Tests
- `tests/test_document_id.py`: Core document ID generation tests
  - `test_generate_id_from_url()`: URL-based ID generation
  - `test_generate_id_from_text()`: Content-based ID generation
  - `test_url_takes_precedence()`: URL priority over content

#### Verified Passing
```bash
✅ 21 tests passing:
  - Document ingestion integration (6 tests)
  - Chunking functionality (15 tests)
  - Document ID generation (3 tests)
```

## Remaining Work

### 1. Integration Tests (HIGH PRIORITY)

Need to add tests verifying document_id in actual workflows:

#### Test File: `tests/test_document_id_integration.py` (CREATE)
```python
# Test document_id in write_documents response
async def test_write_documents_returns_document_ids():
    """Verify write_documents returns document_ids list."""
    # Write documents with URLs
    # Assert document_ids in response
    # Verify IDs are 16-char hex strings

# Test document_id in search results
async def test_search_includes_document_id():
    """Verify search results include document_id."""
    # Write documents
    # Search for content
    # Assert document_id in each result

# Test document_id in list_documents
async def test_list_documents_includes_document_id():
    """Verify list_documents returns document_id."""
    # Write documents
    # List documents
    # Assert document_id present for each

# Test delete by document_id
async def test_delete_by_document_id():
    """Verify delete_documents works with document_id."""
    # Write documents, capture document_ids
    # Delete by document_id
    # Verify documents deleted

# Test get_document by document_id
async def test_get_document_by_id():
    """Verify get_document works with document_id."""
    # Write document, capture document_id
    # Get document by document_id
    # Verify correct document returned

# Test duplicate prevention
async def test_same_url_generates_same_id():
    """Verify same URL generates same document_id."""
    # Write document with URL
    # Write again with same URL, different content
    # Verify same document_id generated
```

#### Test File: `tests/test_list_documents_tool.py` (CREATE)
```python
# Test list_documents MCP tool
async def test_list_documents_tool_basic():
    """Test basic list_documents tool functionality."""
    # Register database, create collection
    # Write documents
    # Call list_documents tool
    # Verify response includes document_id, name, url, chunks

# Test filtering by name
async def test_list_documents_filter_by_name():
    """Test list_documents with name_filter."""
    # Write multiple documents
    # Filter by name
    # Verify only matching documents returned

# Test filtering by url
async def test_list_documents_filter_by_url():
    """Test list_documents with url_filter."""
    # Write multiple documents
    # Filter by url
    # Verify only matching documents returned

# Test filtering by metadata
async def test_list_documents_filter_by_metadata():
    """Test list_documents with metadata_filters."""
    # Write documents with custom metadata
    # Filter by metadata
    # Verify only matching documents returned
```

### 2. Update Existing Tests (MEDIUM PRIORITY)

#### Files to Check/Update:
- `tests/test_unit_models.py`: Remove query parameter tests if any
- `tests/test_integration_mcp_server.py`: Remove query workflow tests if any
- `tests/test_vector_db_weaviate.py`: Remove `test_create_query_agent()` if exists
- `tests/e2e/test_mcp_milvus_e2e.py`: Verify no query tool calls
- `tests/e2e/test_mcp_weaviate_e2e.py`: Verify no query tool calls

### 3. Documentation Updates (MEDIUM PRIORITY)

#### Update: `docs/MCP_API_REFERENCE.md`
- Document document_id concept and generation
- Update write_documents: Add document_ids to response
- Update list_documents: Document new tool and filtering
- Update delete_documents: Clarify uses document_id
- Update get_document: Parameter renamed to document_id
- Update search: Document document_id in results
- Remove query tool documentation

#### Create: `docs/MIGRATION_GUIDE_PHASE_8.6.md`
```markdown
# Migration Guide: Phase 8.6 - Document IDs

## Breaking Changes

1. **delete_documents**: Now uses document_id (not doc_name)
2. **get_document**: Parameter renamed from document_name to document_id
3. **query tool**: Removed (use search instead)

## New Features

1. **document_id**: Auto-generated in all operations
2. **list_documents tool**: New tool for listing documents
3. **metadata_filters**: Arbitrary metadata filtering

## Migration Steps

### Before (Phase 8.5)
```python
# Query tool
result = await client.call_tool("query", {
    "collection": "docs",
    "query": "What is AI?",
    "limit": 5
})

# Delete by name
await client.call_tool("delete_documents", {
    "collection": "docs",
    "document_ids": ["doc1.pdf", "doc2.pdf"]  # Actually names
})
```

### After (Phase 8.6)
```python
# Use search instead of query
result = await client.call_tool("search", {
    "collection": "docs",
    "query": "What is AI?",
    "limit": 5
})

# List documents to get IDs
docs = await client.call_tool("list_documents", {
    "collection": "docs"
})
doc_ids = [doc["document_id"] for doc in docs["documents"]]

# Delete by document_id
await client.call_tool("delete_documents", {
    "collection": "docs",
    "document_ids": doc_ids
})
```
```

#### Update: `examples/` Directory
- Update examples to show document_id workflows
- Demonstrate list → delete pattern
- Show document_id in search results

### 4. E2E Testing (LOW PRIORITY)

Run full E2E tests to verify:
```bash
# Milvus E2E
E2E_MILVUS=1 MILVUS_URI=http://localhost:19530 \
CUSTOM_EMBEDDING_URL=http://localhost:11434/api/embeddings \
CUSTOM_EMBEDDING_MODEL=nomic-embed-text \
CUSTOM_EMBEDDING_VECTORSIZE=768 \
uv run pytest tests/e2e/test_mcp_milvus_e2e.py -v -m "e2e"

# Weaviate E2E (if applicable)
E2E_WEAVIATE=1 uv run pytest tests/e2e/test_mcp_weaviate_e2e.py -v -m "e2e"
```

## API Changes Summary

### Response Changes
```json
// write_documents - NEW field
{
  "status": "success",
  "data": {
    "documents_written": 2,
    "chunks_created": 10,
    "document_ids": ["abc123def456", "789ghi012jkl"]  // NEW
  }
}

// search - NEW top-level field
{
  "results": [
    {
      "document_id": "abc123def456",  // NEW
      "text": "...",
      "url": "https://example.com/doc1.pdf",
      "score": 0.95
    }
  ]
}

// list_documents - NEW tool
{
  "documents": [
    {
      "document_id": "abc123def456",  // NEW
      "name": "doc1.pdf",
      "url": "https://example.com/doc1.pdf",
      "chunks": 5
    }
  ]
}
```

### Parameter Changes
```python
# delete_documents - semantic change
delete_documents(
    collection="docs",
    document_ids=["abc123def456"]  # Now actual document IDs, not names
)

# get_document - parameter renamed
get_document(
    collection="docs",
    document_id="abc123def456"  # Was: document_name
)

# list_documents - NEW parameters
list_documents(
    collection="docs",
    name_filter="*.pdf",  # Optional
    url_filter="example.com",  # Optional
    metadata_filters={"author": "John"}  # Optional, NEW
)
```

## Testing Strategy

### Current Status
- ✅ Core functionality: 21 tests passing
- ✅ Document ID generation: 3 tests passing
- ⏳ Integration tests: Not yet created
- ⏳ E2E tests: Not yet run with changes

### Next Steps
1. Create integration tests (highest priority)
2. Run existing test suite to identify any remaining failures
3. Create list_documents tool tests
4. Update documentation
5. Run E2E tests to verify full stack

## Files Modified

### Core Implementation
- `src/db/document_id.py` (NEW)
- `src/db/vector_db_base.py`
- `src/db/vector_db_milvus.py`
- `src/db/vector_db_weaviate.py`
- `src/maestro_mcp/server.py`

### Tests
- `tests/test_document_id.py` (NEW)
- `tests/e2e/test_functions.py` (MODIFIED)
- `tests/test_query_functionality.py` (DELETED)
- `tests/test_mcp_query.py` (DELETED)
- `tests/test_query_integration.py` (DELETED)

### Documentation
- `docs/IMPLEMENTATION_STATUS_DOCUMENT_IDS.md` (THIS FILE)

## Notes for Continuation

1. **Test First**: Create integration tests before running full test suite
2. **Incremental**: Test one backend at a time (Milvus first, then Weaviate)
3. **E2E Last**: Only run E2E tests after unit/integration tests pass
4. **Documentation**: Update docs after tests are green
5. **Token Efficiency**: Focus on minimal, targeted changes

## Quick Commands

```bash
# Run core tests
uv run pytest tests/test_document_id.py tests/test_document_ingestion_integration.py -v

# Run all unit tests (excluding E2E)
uv run pytest tests/ -v -m "not e2e"

# Create integration test file
touch tests/test_document_id_integration.py

# Check for remaining query references
grep -r "query" tests/ --include="*.py" | grep -v "# query" | grep -v "request"
```

## Success Criteria

- [ ] All unit tests passing
- [ ] Integration tests created and passing
- [ ] E2E tests passing (Milvus minimum)
- [ ] Documentation updated
- [ ] Migration guide created
- [ ] Examples updated