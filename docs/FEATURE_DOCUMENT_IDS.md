# Feature: Document ID Management

## Problem Statement

Currently, document operations rely on optional metadata fields (URL, name) which creates several issues:

1. **No guaranteed unique identifier**: URL and name are optional, leading to ambiguity
2. **Difficult document management**: Agents must search/query to find documents before deleting
3. **Inconsistent API**: Some operations use URL, others use name, creating confusion
4. **No direct document reference**: Can't directly reference a document across operations

## Proposed Solution

Introduce a mandatory `document_id` as the primary identifier for all document operations.

### Key Principles

1. **Auto-generated**: System generates UUID for each document if not provided
2. **Immutable**: Document ID never changes once assigned
3. **Unique per collection**: Each document has a unique ID within its collection
4. **Spans all chunks**: All chunks of a document share the same document_id
5. **Primary identifier**: All document operations use document_id as primary key

### Design

#### Document ID Generation

```python
import hashlib
import uuid

def generate_document_id(text: str, url: str | None = None) -> str:
    """Generate a deterministic document ID.
    
    Strategy:
    1. If URL provided and non-empty: Use hash of URL
    2. Otherwise: Use hash of text content
    
    This ensures:
    - Same URL always gets same ID (prevents duplicates)
    - Same text gets same ID if no URL (idempotent writes)
    - Deterministic and reproducible
    """
    if url and url.strip():
        # Use URL-based ID for documents with URLs
        return hashlib.sha256(url.encode()).hexdigest()[:16]
    else:
        # Use content-based ID for documents without URLs
        return hashlib.sha256(text.encode()).hexdigest()[:16]
```

#### Metadata Structure

Each chunk will include:
```python
{
    "document_id": "abc123def456",  # NEW: Primary identifier
    "doc_name": "optional-name",     # Optional: Human-readable name
    "url": "https://...",            # Optional: Source URL
    "chunk_sequence_number": 1,
    "total_chunks": 5,
    # ... other metadata
}
```

### API Changes

#### 1. write_documents Response

**Before**:
```json
{
  "status": "success",
  "data": {
    "documents_written": 2,
    "chunks_created": 10,
    "collection": "mydocs",
    "embedding_model": "custom_local"
  }
}
```

**After**:
```json
{
  "status": "success",
  "data": {
    "documents_written": 2,
    "chunks_created": 10,
    "collection": "mydocs",
    "embedding_model": "custom_local",
    "document_ids": ["abc123def456", "789ghi012jkl"]
  }
}
```

#### 2. delete_documents

**Before** (uses doc_name from metadata):
```python
delete_documents(
    collection="mydocs",
    document_ids=["doc1.pdf", "doc2.pdf"],  # Actually doc_names
    force=True
)
```

**After** (uses actual document IDs):
```python
delete_documents(
    collection="mydocs",
    document_ids=["abc123def456", "789ghi012jkl"],
    force=True
)
```

#### 3. get_document

**Before**:
```python
get_document(
    collection="mydocs",
    document_id="doc1.pdf"  # Actually doc_name
)
```

**After**:
```python
get_document(
    collection="mydocs",
    document_id="abc123def456"  # Actual document ID
)
```

#### 4. list_documents

**Before**:
```json
{
  "documents": [
    {
      "name": "doc1.pdf",
      "url": "https://example.com/doc1.pdf",
      "chunks": 5
    }
  ]
}
```

**After**:
```json
{
  "documents": [
    {
      "document_id": "abc123def456",
      "name": "doc1.pdf",
      "url": "https://example.com/doc1.pdf",
      "chunks": 5
    }
  ]
}
```

#### 5. query/search Results

**Before**:
```json
{
  "results": [
    {
      "text": "...",
      "url": "https://example.com/doc1.pdf",
      "score": 0.95,
      "metadata": {...}
    }
  ]
}
```

**After**:
```json
{
  "results": [
    {
      "document_id": "abc123def456",
      "text": "...",
      "url": "https://example.com/doc1.pdf",
      "score": 0.95,
      "metadata": {...}
    }
  ]
}
```

### Implementation Plan

#### Phase 1: Backend Changes (Milvus & Weaviate)

1. **Add document_id generation** in `write_documents()`
   - Generate ID from URL or text hash
   - Add to chunk metadata
   - Track document IDs in write stats

2. **Update return values**
   - Add `document_ids` list to write response
   - Include document_id in all query/search results

3. **Update document operations**
   - Modify `get_document()` to use document_id
   - Modify `delete_documents()` to use document_id
   - Modify `list_documents()` to return document_id

#### Phase 2: MCP Server Changes

1. **Update write_documents tool**
   - Extract document_ids from backend response
   - Pass to response formatter
   - Update docstring to mention returned IDs

2. **Update delete_documents tool**
   - Change parameter description to clarify it's document IDs
   - Update examples to show ID-based deletion

3. **Update get_document tool**
   - Rename parameter from `document_name` to `document_id`
   - Update docstring

4. **Update list_documents tool**
   - Include document_id in response
   - Update docstring

5. **Update query/search tools**
   - Include document_id in results
   - Update docstrings

#### Phase 3: Documentation & Migration

1. **Update API documentation**
   - Document document_id concept
   - Provide migration examples
   - Update all tool descriptions

2. **Update examples**
   - Show ID-based workflows
   - Demonstrate list → delete pattern

3. **Add migration guide**
   - Explain breaking changes
   - Provide upgrade path

### Benefits

1. **Clearer API**: Single, consistent identifier across all operations
2. **Better UX**: Agents can reliably reference documents
3. **Prevents duplicates**: URL-based IDs prevent duplicate writes
4. **Simpler workflows**: List documents → get IDs → delete by ID
5. **Future-proof**: Enables features like document versioning, updates

### Breaking Changes

1. **delete_documents**: Parameter semantics change from doc_name to document_id
2. **get_document**: Parameter rename from document_name to document_id
3. **Existing data**: Old documents won't have document_id in metadata

### Migration Strategy

1. **Backward compatibility**: Support both old (doc_name) and new (document_id) for one release
2. **Deprecation warnings**: Warn when using doc_name-based operations
3. **Data migration**: Provide script to add document_ids to existing documents
4. **Documentation**: Clear migration guide with examples

### Timeline

- **Phase 1** (Backend): 2-3 days
- **Phase 2** (MCP Server): 1-2 days
- **Phase 3** (Documentation): 1 day
- **Total**: 4-6 days

### Priority

**High** - This significantly improves API usability and agent experience.

### Related Issues

- Addresses user feedback about confusing document management
- Enables future features like document updates, versioning
- Aligns with best practices for RESTful APIs

### Next Steps

1. Review and approve design
2. Implement Phase 1 (backend changes)
3. Test with existing E2E tests
4. Implement Phase 2 (MCP server changes)
5. Update documentation
6. Release with migration guide