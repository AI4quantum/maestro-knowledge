# API Naming Analysis: Chunks vs Documents

## Current State

### Backend Methods (VectorDatabase)
**Document-level operations:**
- `write_documents()` - Writes documents, internally chunks them
- `delete_documents()` - Deletes by document_id (all chunks)
- `get_document()` - Gets document by document_id (reassembles chunks)
- `list_documents()` - Lists documents (deduplicated, one per document)
- `count_documents()` - Counts unique documents

**Chunk-level operations:**
- `get_document_chunks()` - Gets individual chunks for a document
- `search()` - Returns chunks with scores (but includes document_id)

**Collection operations:**
- `create_collection()`
- `delete_collection()`
- `list_collections()`
- `get_collection_info()`

### MCP Tools (Current - 11 tools)
1. `write_documents` ✅ Document-level
2. `delete_documents` ✅ Document-level  
3. `get_document` ✅ Document-level
4. `create_collection` ✅ Collection-level
5. `delete_collection` ✅ Collection-level
6. `get_collection` ✅ Collection-level
7. `list_collections` ✅ Collection-level
8. `search` ⚠️ Returns chunks (but with document_id)
9. `query` ⚠️ Returns formatted chunks
10. `get_config` ✅ System-level
11. `refresh_databases` ✅ System-level

**Missing:**
- ❌ `list_documents` - No way to browse/discover documents!

## Problem

**Inconsistency:**
- Most tools are document-centric (write, delete, get)
- But `search` returns chunks, not documents
- No way to list documents in a collection

**Agent confusion:**
- "How do I see what documents are in my collection?"
- "What's the difference between get_document and search?"

## Recommendation: Document-Centric API

### Principle
**Agents think in documents, not chunks.** Chunking is an implementation detail.

### Proposed Changes

#### 1. Add `list_documents` Tool
```python
list_documents(
    collection: str,
    limit: int = 10,
    offset: int = 0,
    name_filter: str | None = None,
    url_filter: str | None = None,
    metadata_filters: dict[str, Any] | None = None
) -> str
```

**Returns:** List of documents with document_id, name, url, chunk_count

**Use case:** "Show me what documents are in this collection"

#### 2. Keep `search` As-Is (Returns Chunks)
**Rationale:**
- Search results are naturally chunk-level (relevance scoring per chunk)
- But include `document_id` so agents can identify source documents
- Agents can use document_id to get full document if needed

**Clarify in docs:**
- "Returns relevant text chunks with document_id for source tracking"
- "Use get_document(document_id) to retrieve full document"

#### 3. Remove `query` (Redundant)
- Just a text formatter for search results
- No LLM, no added value
- Agents can format search results themselves

### Final Tool List (11 tools)

**Document Operations (4 tools):**
1. `write_documents` - Add documents to collection
2. `delete_documents` - Remove documents by ID
3. `get_document` - Retrieve full document by ID
4. `list_documents` - **NEW** - Browse documents in collection

**Collection Operations (4 tools):**
5. `create_collection` - Create new collection
6. `delete_collection` - Remove collection
7. `get_collection` - Get collection info
8. `list_collections` - List all collections

**Query Operations (1 tool):**
9. `search` - Find relevant chunks (includes document_id)

**System Operations (2 tools):**
10. `get_config` - Get system configuration
11. `refresh_databases` - Refresh database registry

### Naming Clarity

**Clear distinction:**
- `*_document*` = Document-level (whole documents)
- `*_collection*` = Collection-level (containers)
- `search` = Chunk-level results (but with document_id)

**Agent mental model:**
1. Create collection
2. Write documents to collection
3. Search finds relevant chunks (with document_id)
4. Get full document if needed
5. List documents to see what's available
6. Delete documents when done

## Implementation Priority

1. **High**: Add `list_documents` MCP tool
2. **High**: Remove `query` MCP tool and backend methods
3. **Medium**: Update documentation to clarify chunk vs document
4. **Low**: Consider renaming `search` to `search_chunks` (breaking change)

## Alternative: Explicit Chunk Operations

If we want to be more explicit:

**Document operations:**
- `write_documents`
- `delete_documents`
- `get_document`
- `list_documents`

**Chunk operations:**
- `search_chunks` (renamed from `search`)
- `get_document_chunks` (expose existing backend method)

**Verdict:** Not necessary. Current naming is clear enough with good documentation.