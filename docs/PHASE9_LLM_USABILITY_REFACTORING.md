# Phase 9: LLM Usability Refactoring Plan

**Status**: READY FOR IMPLEMENTATION (2025-01-12)  
**Based on**: Real-world LLM testing feedback (docs/LLM_TESTING_NOTES_PART_1.md)  
**Approach**: Aggressive consolidation with breaking changes (approved)  
**Clarifications**: All feedback questions answered in this document (see Appendix D)

## Executive Summary

This refactoring addresses 14 critical usability issues discovered during real-world LLM agent testing. The goal is to create a cleaner, more intuitive API that reduces cognitive load for both LLM agents and human developers.

### Key Changes
- **Tool count reduction**: 22 → 14 tools (36% reduction)
- **Consistent naming**: All tools follow verb-noun pattern
- **JSON-first responses**: All tools return structured JSON with embedded human-readable text
- **No default collection**: Explicit collection creation required
- **Safety features**: Force flags for destructive operations
- **Better errors**: Parameter-specific error messages with full error codes
- **Query/Search distinction**: Keep both - query returns natural language summary, search returns structured results

---

## Issues Summary (from Testing Notes)

| # | Issue | Impact | Solution |
|---|-------|--------|----------|
| 1 | Tool naming confusion (register vs setup, cleanup vs delete) | High | Rename to clear verbs: create_database, delete_database |
| 2 | Default database in Attu not visible in list_databases() | Medium | Fix database sync, document behavior |
| 3-4 | Default "MaestroDocs" collection appears but doesn't exist | High | Remove default collection entirely |
| 5 | Deletions too easy, no safety checks | High | Add force parameter with warnings |
| 6 | Embedding info lacks detail (custom_local mapping unclear) | Medium | Return detailed embedding configuration |
| 7 | Inconsistent text vs JSON responses | High | Standardize all responses as JSON |
| 8 | Default chunking strategy "None" fails for large docs | Critical | Already fixed in Phase 8.5 |
| 9 | count_documents redundant with get_collection_info | Low | Merge into get_collection_info |
| 10 | write_document assumes MaestroDocs collection | High | Require explicit collection parameter |
| 11 | URL parameter confusion (required vs optional) | High | Make URL optional with auto-generation |
| 12 | document_name parameter causes cryptic errors | High | Improve error messages with parameter names |
| 13 | Unable to write documents (dictionary error) | Critical | Fix parameter validation |
| 14 | list_documents flattens collection structure | Medium | Return hierarchical structure |

---

## Phase 9.1: Tool Consolidation & Naming

### Current Tools (22)
**Database Management (6):**
- register_database ❌ → create_database
- setup_database ❌ → MERGED into create_database
- get_database_info ✅ (keep)
- list_databases ✅ (keep)
- cleanup ❌ → delete_database
- resync_databases_tool ❌ → refresh_databases

**Collection Management (5):**
- create_collection ✅ (keep)
- list_collections ✅ (keep)
- get_collection_info ✅ (keep, merge count_documents)
- delete_collection ✅ (keep, add force)
- count_documents ❌ → MERGED into get_collection_info

**Document Operations (9):**
- write_documents ✅ (keep)
- write_document ❌ → MERGED into write_documents
- write_document_to_collection ❌ → MERGED into write_documents
- list_documents ❌ → MERGED into list_collections (with details flag)
- list_documents_in_collection ❌ → MERGED into list_collections
- get_document ✅ (keep)
- delete_document ❌ → MERGED into delete_documents
- delete_documents ✅ (keep, add force)
- delete_document_from_collection ❌ → MERGED into delete_documents

**Query Operations (2):**
- query ✅ (keep - returns natural language summary with citations)
- search ✅ (keep - returns structured JSON results with full metadata)

### Proposed Tools (14)

**Note on Query vs Search**: Both tools serve distinct purposes:
- **query**: Returns natural language summary suitable for direct user presentation. Includes citations but focuses on readability.
- **search**: Returns structured JSON with full metadata, scores, and citations. Suitable for programmatic processing or when detailed control is needed.

This distinction is valuable for LLM agents who need both conversational responses (query) and structured data (search).

**Database Management (5):**
1. **create_database** (was register_database + setup_database)
   - Combines registration and initialization
   - Parameters: database, database_type, embedding="auto"
   - Returns: JSON with status, connection info

2. **delete_database** (was cleanup)
   - Parameters: database, force=False
   - Returns: JSON with deletion stats, warnings if not empty

3. **get_database_info** (unchanged)
   - Returns: JSON with database details

4. **list_databases** (unchanged)
   - Returns: JSON array of database names with basic info

5. **refresh_databases** (was resync_databases_tool)
   - Discovers and registers backend databases
   - Returns: JSON with newly discovered databases

**Collection Management (4):**
6. **create_collection** (unchanged)
   - Parameters: database, collection, embedding="auto", chunking_config=None
   - Returns: JSON with collection details

7. **delete_collection** (enhanced)
   - Parameters: database, collection, force=False
   - Returns: JSON with deletion stats, document count warning

8. **get_collection_info** (enhanced - merges count_documents)
   - Parameters: database, collection
   - Returns: JSON with collection details INCLUDING document_count

9. **list_collections** (enhanced - merges list_documents variants)
   - Parameters: database, include_documents=False, limit=10
   - Returns: JSON array of collections, optionally with document summaries

**Document Operations (3):**
10. **write_documents** (enhanced - merges all write variants)
    - Parameters: database, collection, documents (list or single dict)
    - Auto-detects single vs bulk
    - Returns: JSON with write stats

11. **delete_documents** (enhanced - merges all delete variants)
    - Parameters: database, collection, document_ids (list or single string), force=False
    - Returns: JSON with deletion stats

12. **get_document** (unchanged)
    - Parameters: database, collection, document_id
    - Returns: JSON with full document content (reassembled from chunks)

**Query Operations (2):**
13. **query** (enhanced)
    - Returns: JSON with natural language summary + citations
    - Format: `{"summary": "text", "sources": [...]}`
    - Use case: Direct presentation to users

14. **search** (enhanced)
    - Returns: JSON array of detailed search results
    - Format: `[{"text": "...", "score": 0.95, "url": "...", "metadata": {...}}]`
    - Use case: Programmatic processing, detailed analysis

**Removed Tools:**
- list_documents → Use list_collections with include_documents=True
- list_documents_in_collection → Use list_collections with include_documents=True
- get_supported_embeddings → MERGED into get_database_info
- get_supported_chunking_strategies → MERGED into get_database_info

---

## Phase 9.2: Remove Default Collection Behavior

### Current Behavior
- `register_database()` mentions "MaestroDocs" in response
- `write_document()` assumes default collection if not specified
- Causes confusion when collection doesn't actually exist

### New Behavior
1. **No default collection creation**
   - `create_database()` only creates database, no collections
   - Response clearly states: "Database created. Use create_collection() to add collections."

2. **Explicit collection required**
   - All document operations require `collection` parameter
   - No auto-detection or fallback to "MaestroDocs"
   - Clear error if collection parameter missing

3. **Migration path**
   - Update all examples to explicitly create collections
   - Error messages guide users to create_collection()

### Implementation
```python
# OLD (Phase 8.5)
await register_database(database="mydb", database_type="milvus")
# Response mentions "MaestroDocs" collection

await write_document(database="mydb", text="content")
# Assumes MaestroDocs collection

# NEW (Phase 9.2)
await create_database(database="mydb", database_type="milvus")
# Response: "Database created. No collections yet."

await create_collection(database="mydb", collection="docs")
# Response: "Collection 'docs' created"

await write_documents(database="mydb", collection="docs", documents=[{"text": "content"}])
# Explicit collection required
```

---

## Phase 9.3: Standardize JSON Response Format

### Current State
- Mixed text and JSON responses
- Some tools return plain text with embedded JSON
- Inconsistent structure across tools

### Standard Response Format

**Success Response:**
```json
{
  "status": "success",
  "message": "Human-readable summary",
  "data": {
    // Tool-specific data
  },
  "metadata": {
    "timestamp": "2025-01-12T12:00:00Z",
    "operation": "write_documents",
    "database": "mydb",
    "collection": "docs"
  }
}
```

**Error Response:**
```json
{
  "status": "error",
  "error_code": "COLLECTION_NOT_FOUND",
  "message": "Collection 'docs' not found in database 'mydb'",
  "details": {
    "database": "mydb",
    "collection": "docs",
    "available_collections": ["other_docs", "archive"]
  },
  "suggestion": "Create the collection first: create_collection(database='mydb', collection='docs')"
}
```

### Tool-Specific Data Formats

**create_database:**
```json
{
  "status": "success",
  "message": "Database 'mydb' created successfully",
  "data": {
    "database": "mydb",
    "database_type": "milvus",
    "embedding": "custom_local",
    "connection_status": "connected",
    "collections_count": 0
  }
}
```

**write_documents:**
```json
{
  "status": "success",
  "message": "Wrote 5 documents to collection 'docs'",
  "data": {
    "documents_written": 5,
    "chunks_created": 23,
    "collection": "docs",
    "embedding_model": "custom_local"
  },
  "metadata": {
    "sample_query": "What is machine learning?",
    "collection_total_documents": 105
  }
}
```

**get_collection_info:**
```json
{
  "status": "success",
  "message": "Collection 'docs' information",
  "data": {
    "name": "docs",
    "database": "mydb",
    "document_count": 105,
    "chunk_count": 523,
    "embedding": {
      "model": "custom_local",
      "provider": "ollama",
      "vector_size": 768,
      "url": "http://localhost:11434"
    },
    "chunking": {
      "strategy": "Sentence",
      "chunk_size": 512,
      "overlap": 0
    },
    "created_at": "2025-01-10T10:00:00Z",
    "last_updated": "2025-01-12T12:00:00Z"
  }
}
```

**list_collections:**
```json
{
  "status": "success",
  "message": "Found 3 collections in database 'mydb'",
  "data": {
    "collections": [
      {
        "name": "docs",
        "document_count": 105,
        "embedding": "custom_local",
        "created_at": "2025-01-10T10:00:00Z"
      },
      {
        "name": "archive",
        "document_count": 50,
        "embedding": "text-embedding-3-small",
        "created_at": "2025-01-09T15:00:00Z"
      }
    ],
    "total_collections": 3
  }
}
```

---

## Phase 9.4: Improve Parameter Consistency

### Issues
- Inconsistent parameter names across similar operations
- URL vs document_name vs document_id confusion
- Optional vs required parameters unclear

### Standardization Rules

**1. Database/Collection Parameters:**
- Always `database` (never `db`, `db_name`, `database_name`)
- Always `collection` (never `coll`, `collection_name`)
- Both required unless operation is database-level only

**2. Document Identifiers:**
- Use `document_id` for retrieval/deletion (unique identifier)
- Use `url` in write operations (can be URL or identifier)
- `url` is optional in writes (auto-generated if empty)
- `document_id` is required in get/delete operations

**3. Bulk vs Single Operations:**
- `documents` parameter accepts both list and single dict
- Tool auto-detects and handles appropriately
- No separate tools for single vs bulk

**4. Optional Parameters:**
- Always use `Field(default=...)` with clear description
- Document what happens when omitted
- Provide sensible defaults

### Parameter Matrix

| Tool | database | collection | document_id | documents | url | force |
|------|----------|------------|-------------|-----------|-----|-------|
| create_database | ✓ req | - | - | - | - | - |
| delete_database | ✓ req | - | - | - | - | ✓ opt |
| create_collection | ✓ req | ✓ req | - | - | - | - |
| delete_collection | ✓ req | ✓ req | - | - | - | ✓ opt |
| write_documents | ✓ req | ✓ req | - | ✓ req | in docs | - |
| delete_documents | ✓ req | ✓ req | ✓ req | - | - | ✓ opt |
| get_document | ✓ req | ✓ req | ✓ req | - | - | - |
| list_documents | ✓ req | ✓ req | - | - | - | - |
| query | ✓ req | ✓ opt | - | - | - | - |
| search | ✓ req | ✓ opt | - | - | - | - |

---

## Phase 9.5: Add Safety Features

### Force Parameter for Destructive Operations

**Operations requiring force flag:**
1. `delete_database(database, force=False)`
2. `delete_collection(database, collection, force=False)`
3. `delete_documents(database, collection, document_ids, force=False)`

**Behavior:**
- `force=False` (default): Check if resource is empty/has dependencies
  - If not empty: Return error with stats and require force=True
  - If empty: Proceed with deletion
- `force=True`: Delete regardless of contents, return deletion stats

**Example Responses:**

```json
// delete_collection without force, collection has documents
{
  "status": "error",
  "error_code": "COLLECTION_NOT_EMPTY",
  "message": "Cannot delete collection 'docs' - it contains 105 documents",
  "details": {
    "collection": "docs",
    "document_count": 105,
    "chunk_count": 523,
    "estimated_size_mb": 12.5
  },
  "suggestion": "To delete anyway, use: delete_collection(database='mydb', collection='docs', force=True)"
}

// delete_collection with force=True
{
  "status": "success",
  "message": "Deleted collection 'docs' and all its contents",
  "data": {
    "collection": "docs",
    "documents_deleted": 105,
    "chunks_deleted": 523,
    "freed_space_mb": 12.5
  },
  "warning": "This operation cannot be undone"
}
```

### Confirmation Warnings

For operations with `force=True`, include warnings in response:
- "This operation cannot be undone"
- "All data in this [database/collection] will be permanently deleted"
- Statistics about what will be deleted

---

## Phase 9.6: Enhanced Embedding Information

### Current Issue
- `get_supported_embeddings()` returns list of names
- No details about what "custom_local" maps to
- Users need to guess configuration

### Solution: Merge into get_database_info

**Enhanced get_database_info response:**
```json
{
  "status": "success",
  "message": "Database 'mydb' information",
  "data": {
    "database": "mydb",
    "database_type": "milvus",
    "connection_status": "connected",
    "collections_count": 3,
    "embedding_config": {
      "current": "custom_local",
      "supported": [
        {
          "name": "default",
          "display_name": "OpenAI text-embedding-ada-002",
          "provider": "openai",
          "vector_size": 1536,
          "requires": ["OPENAI_API_KEY"],
          "status": "not_configured"
        },
        {
          "name": "text-embedding-3-small",
          "display_name": "OpenAI text-embedding-3-small",
          "provider": "openai",
          "vector_size": 1536,
          "requires": ["OPENAI_API_KEY"],
          "status": "not_configured"
        },
        {
          "name": "custom_local",
          "display_name": "Custom Local Embedding",
          "provider": "ollama",
          "model": "nomic-embed-text",
          "vector_size": 768,
          "url": "http://localhost:11434/api/embeddings",
          "requires": ["CUSTOM_EMBEDDING_URL", "CUSTOM_EMBEDDING_MODEL", "CUSTOM_EMBEDDING_VECTORSIZE"],
          "status": "configured"
        }
      ]
    },
    "chunking_strategies": [
      {
        "name": "None",
        "description": "No chunking; entire document is single chunk",
        "parameters": {},
        "use_case": "Small documents (<1000 chars)"
      },
      {
        "name": "Sentence",
        "description": "Sentence-aware chunking with size limit",
        "parameters": {
          "chunk_size": {"type": "int", "default": 512, "min": 100, "max": 2000},
          "overlap": {"type": "int", "default": 0, "min": 0, "max": 500}
        },
        "use_case": "General purpose, respects sentence boundaries"
      },
      {
        "name": "Fixed",
        "description": "Fixed-size character windows",
        "parameters": {
          "chunk_size": {"type": "int", "default": 512, "min": 100, "max": 2000},
          "overlap": {"type": "int", "default": 0, "min": 0, "max": 500}
        },
        "use_case": "Uniform chunks, may split sentences"
      },
      {
        "name": "Semantic",
        "description": "Semantic similarity-based chunking",
        "parameters": {
          "chunk_size": {"type": "int", "default": 768, "min": 100, "max": 2000},
          "overlap": {"type": "int", "default": 0, "min": 0, "max": 500},
          "window_size": {"type": "int", "default": 1, "min": 1, "max": 5},
          "threshold_percentile": {"type": "float", "default": 95.0, "min": 0, "max": 100}
        },
        "use_case": "Coherent semantic units, slower processing"
      }
    ]
  }
}
```

**Remove separate tool:**
- Delete `get_supported_embeddings()`
- Delete `get_supported_chunking_strategies()`
- All info available in `get_database_info()`

---

## Phase 9.7: Fix Database Sync Issues

### Issue #2: Default Database Visibility
- Attu UI shows "default" database
- `list_databases()` returns empty list
- Causes confusion about what exists

### Root Cause Analysis
1. Milvus creates a "default" database automatically
2. Our `list_databases()` only shows registered databases in `vector_databases` dict
3. Attu connects directly to Milvus and sees the backend database

### Solution Options

**Option A: Auto-register backend databases (RECOMMENDED)**
```python
async def list_databases() -> str:
    """List all databases, including auto-discovered backend databases."""
    # 1. Get registered databases
    registered = list(vector_databases.keys())
    
    # 2. Auto-discover backend databases
    discovered = await discover_backend_databases()
    
    # 3. Merge and return
    all_databases = {
        "registered": registered,
        "discovered": discovered,
        "total": len(set(registered + discovered))
    }
    
    return json.dumps({
        "status": "success",
        "data": all_databases
    })
```

**Option B: Explicit sync command**
- Keep current behavior
- Add note in response: "Use refresh_databases() to discover backend databases"
- Less automatic, more explicit

**Recommendation: Option A**
- More intuitive for users
- Matches Attu behavior
- Auto-registration is safe (read-only discovery)

### Implementation
1. Add `discover_backend_databases()` helper
2. Call automatically in `list_databases()`
3. Register discovered databases in memory
4. Mark as "auto-discovered" vs "user-created"

---

## Phase 9.8: Update Error Messages

### Current Issues
- Generic errors: "dictionary update sequence element #0 has length 1; 2 is required"
- Don't reference parameter names
- No actionable guidance

### New Error Message Format

**Structure:**
```json
{
  "status": "error",
  "error_code": "ERROR_CODE",
  "message": "Human-readable error description",
  "details": {
    "parameter": "parameter_name",
    "provided_value": "what_was_provided",
    "expected": "what_was_expected",
    "available_options": ["option1", "option2"]
  },
  "suggestion": "Specific fix: tool_name(param='value')"
}
```

### Error Code Categories

**Database Errors (DB_*):**
- `DB_NOT_FOUND`: Database doesn't exist
- `DB_ALREADY_EXISTS`: Database name in use
- `DB_NOT_INITIALIZED`: Database not connected
- `DB_CONNECTION_FAILED`: Can't connect to backend

**Collection Errors (COLL_*):**
- `COLL_NOT_FOUND`: Collection doesn't exist
- `COLL_ALREADY_EXISTS`: Collection name in use
- `COLL_NOT_EMPTY`: Can't delete non-empty collection without force

**Document Errors (DOC_*):**
- `DOC_NOT_FOUND`: Document ID doesn't exist
- `DOC_INVALID_FORMAT`: Document structure invalid
- `DOC_MISSING_REQUIRED`: Required field missing (specify which)
- `DOC_URL_REQUIRED`: URL parameter required but not provided

**Parameter Errors (PARAM_*):**
- `PARAM_MISSING`: Required parameter not provided
- `PARAM_INVALID_TYPE`: Wrong type (expected X, got Y)
- `PARAM_INVALID_VALUE`: Value out of range or invalid
- `PARAM_CONFLICT`: Conflicting parameters provided

**Configuration Errors (CONFIG_*):**
- `CONFIG_EMBEDDING_INVALID`: Embedding model not supported
- `CONFIG_EMBEDDING_NOT_CONFIGURED`: Missing API keys/env vars
- `CONFIG_CHUNKING_INVALID`: Invalid chunking configuration

### Example Error Messages

**Missing required parameter:**
```json
{
  "status": "error",
  "error_code": "PARAM_MISSING",
  "message": "Required parameter 'collection' not provided",
  "details": {
    "parameter": "collection",
    "operation": "write_documents",
    "database": "mydb"
  },
  "suggestion": "Specify collection: write_documents(database='mydb', collection='docs', documents=[...])"
}
```

**Collection not found:**
```json
{
  "status": "error",
  "error_code": "COLL_NOT_FOUND",
  "message": "Collection 'docs' not found in database 'mydb'",
  "details": {
    "database": "mydb",
    "collection": "docs",
    "available_collections": ["archive", "temp"]
  },
  "suggestion": "Create collection first: create_collection(database='mydb', collection='docs')"
}
```

**Invalid document format:**
```json
{
  "status": "error",
  "error_code": "DOC_INVALID_FORMAT",
  "message": "Document missing required field 'text'",
  "details": {
    "document_index": 0,
    "provided_fields": ["url", "metadata"],
    "required_fields": ["text"],
    "optional_fields": ["url", "metadata", "vector"]
  },
  "suggestion": "Each document must have 'text' field: {'text': 'content', 'url': 'optional'}"
}
```

---

## Phase 9.9: Update Tests

### Test Categories

**1. Unit Tests (test_phase9_*.py)**
- Test each consolidated tool individually
- Test parameter validation
- Test error messages with error codes
- Test JSON response format
- Test force parameter behavior

**2. Integration Tests**
- Test tool consolidation (write_documents handles single/bulk)
- Test no default collection behavior
- Test database auto-discovery
- Test embedding info in get_database_info

**3. E2E Tests**
- Full workflow with new tool names
- Error recovery scenarios
- Force parameter workflows
- JSON parsing by LLM agents

### Test Files to Create/Update

**New test files:**
- `tests/test_phase9_tool_consolidation.py`
- `tests/test_phase9_json_responses.py`
- `tests/test_phase9_safety_features.py`
- `tests/test_phase9_error_messages.py`

**Update existing:**
- `tests/test_integration_mcp_server.py` - Update tool names
- `tests/test_mcp_server.py` - Update all tool calls
- `tests/e2e/test_mcp_milvus_e2e.py` - Update workflow
- `tests/test_phase26_workflow.py` - Update to Phase 9 workflow

### Test Coverage Requirements
- 100% coverage of new error codes
- All JSON response formats validated
- All force parameter scenarios tested
- Backward compatibility tests (should fail appropriately)

---

## Phase 9.10: Update Documentation

### Documents to Update

**1. README.md**
- Update quick start with new tool names
- Update workflow examples
- Add JSON response examples
- Document force parameter usage

**2. docs/MIGRATION_GUIDE.md**
- Add Phase 9 migration section
- Tool name mapping table
- Parameter changes
- Response format changes
- Breaking changes summary

**3. docs/REFACTORING_SUMMARY.md**
- Add Phase 9 summary
- Update tool count (22 → 15)
- Document consolidation decisions

**4. docs/AGENTS.md**
- Update tool list
- Update common commands
- Add JSON parsing examples

**5. src/maestro_mcp/README.md**
- Update all examples
- Document new response format
- Add error handling examples

**6. examples/**
- Update all example scripts
- Add error handling examples
- Add force parameter examples

### New Documentation

**docs/PHASE9_MIGRATION.md** (detailed migration guide)
- Tool-by-tool migration instructions
- Code examples (before/after)
- Common migration issues
- Automated migration script

**docs/ERROR_CODES.md** (error reference)
- Complete list of error codes
- When each error occurs
- How to fix each error
- Example error responses

**docs/JSON_RESPONSE_FORMAT.md** (response reference)
- Standard response structure
- Tool-specific response formats
- Parsing examples for LLMs
- Error response handling

---

## Implementation Order

### Phase 9.1: Tool Consolidation (Week 1)
1. Create new consolidated tools
2. Mark old tools as deprecated
3. Add deprecation warnings
4. Update internal routing

### Phase 9.2: Remove Default Collection (Week 1)
1. Remove MaestroDocs references
2. Make collection parameter required
3. Update error messages
4. Update examples

### Phase 9.3: JSON Responses (Week 2)
1. Define response schemas
2. Update all tools to return JSON
3. Add response validation
4. Update tests

### Phase 9.4: Parameter Consistency (Week 2)
1. Standardize parameter names
2. Update validation
3. Update error messages
4. Update tests

### Phase 9.5: Safety Features (Week 3)
1. Add force parameter
2. Implement safety checks
3. Add deletion stats
4. Update tests

### Phase 9.6: Embedding Info (Week 3)
1. Enhance get_database_info
2. Remove old tools
3. Update documentation
4. Update tests

### Phase 9.7: Database Sync (Week 4)
1. Implement auto-discovery
2. Update list_databases
3. Add sync status
4. Update tests

### Phase 9.8: Error Messages (Week 4)
1. Define error codes
2. Update all error messages
3. Add error code tests
4. Document error codes

### Phase 9.9: Tests (Week 5)
1. Create new test files
2. Update existing tests
3. Add E2E tests
4. Verify coverage

### Phase 9.10: Documentation (Week 5-6)
1. Update all docs
2. Create new docs
3. Update examples
4. Create migration guide

---

## Breaking Changes Summary

### Removed Tools (7)
1. `setup_database` → merged into `create_database`
2. `cleanup` → renamed to `delete_database`
3. `write_document` → merged into `write_documents`
4. `write_document_to_collection` → merged into `write_documents`
5. `delete_document` → merged into `delete_documents`
6. `delete_document_from_collection` → merged into `delete_documents`
7. `count_documents` → merged into `get_collection_info`
8. `list_documents_in_collection` → merged into `list_collections`
9. `resync_databases_tool` → renamed to `refresh_databases`
10. `get_supported_embeddings` → merged into `get_database_info`
11. `get_supported_chunking_strategies` → merged into `get_database_info`

### Renamed Tools (3)
1. `register_database` → `create_database`
2. `cleanup` → `delete_database`
3. `resync_databases_tool` → `refresh_databases`

### Parameter Changes
- All tools: Response format changed to JSON
- `write_documents`: Now handles single and bulk
- `delete_documents`: Now handles single and bulk
- All document operations: `collection` parameter required
- Destructive operations: Added `force` parameter

### Response Format Changes
- All tools now return JSON (was mixed text/JSON)
- Standard structure with status, message, data, metadata
- Error responses include error_code and suggestion

---

## Migration Script

```python
# tools/migrate_to_phase9.py
"""
Automated migration script for Phase 9 changes.
Scans code and updates tool calls to new format.
"""

TOOL_MIGRATIONS = {
    "register_database": "create_database",
    "setup_database": "create_database",  # Merge
    "cleanup": "delete_database",
    "write_document": "write_documents",
    "write_document_to_collection": "write_documents",
    "delete_document": "delete_documents",
    "delete_document_from_collection": "delete_documents",
    "count_documents": "get_collection_info",
    "list_documents_in_collection": "list_collections",
    "resync_databases_tool": "refresh_databases",
}

def migrate_file(filepath):
    """Migrate a single file to Phase 9 API."""
    # Read file
    # Find tool calls
    # Update tool names
    # Update parameters
    # Add collection parameter where needed
    # Update response parsing (text → JSON)
    # Write file
    pass

def main():
    # Scan all Python files
    # Migrate each file
    # Generate migration report
    pass
```

---

## Success Metrics

### Quantitative
- Tool count: 22 → 15 (32% reduction) ✓
- Average parameters per tool: Reduced by 20%
- Error message clarity: 100% include error codes
- JSON response coverage: 100% of tools
- Test coverage: Maintain >90%

### Qualitative
- LLM agents can complete tasks without confusion
- Error messages are actionable
- No ambiguity in tool selection
- Consistent patterns across all operations
- Clear migration path for existing code

---

## Risk Assessment

### High Risk
1. **Breaking changes impact**: All existing code needs updates
   - Mitigation: Comprehensive migration guide + automated script
   
2. **JSON parsing complexity**: LLMs must parse JSON correctly
   - Mitigation: Standard format, clear examples, validation

### Medium Risk
3. **Tool consolidation confusion**: Users expect separate tools
   - Mitigation: Clear documentation, deprecation warnings
   
4. **Force parameter misuse**: Users might always use force=True
   - Mitigation: Strong warnings, require explicit True

### Low Risk
5. **Performance impact**: JSON serialization overhead
   - Mitigation: Minimal impact, JSON is fast
   
6. **Database sync issues**: Auto-discovery might be slow
   - Mitigation: Cache results, timeout protection

---

## Rollout Plan

### Phase 1: Internal Testing (Week 1-2)
- Implement changes in feature branch
- Run full test suite
- Manual testing with LLM agents

### Phase 2: Beta Release (Week 3-4)
- Release as v2.0.0-beta
- Gather feedback from early adopters
- Fix critical issues

### Phase 3: Documentation (Week 5)
- Complete all documentation updates
- Create video tutorials
- Update examples

### Phase 4: Stable Release (Week 6)
- Release as v2.0.0
- Announce breaking changes
- Provide migration support

### Phase 5: Deprecation (Week 7-12)
- Keep old tools with deprecation warnings
- Monitor usage
- Remove in v3.0.0

---

## Appendix A: Tool Comparison Matrix

| Old Tool | New Tool | Status | Notes |
|----------|----------|--------|-------|
| register_database | create_database | Renamed | Merged with setup |
| setup_database | create_database | Merged | Combined into create |
| cleanup | delete_database | Renamed | Clearer name |
| write_document | write_documents | Merged | Handles single/bulk |
| write_document_to_collection | write_documents | Merged | Collection param |
| write_documents | write_documents | Kept | Enhanced |
| delete_document | delete_documents | Merged | Handles single/bulk |
| delete_document_from_collection | delete_documents | Merged | Collection param |
| delete_documents | delete_documents | Kept | Enhanced |
| list_documents | list_documents | Simplified | Metadata only |
| list_documents_in_collection | list_collections | Merged | With details flag |
| count_documents | get_collection_info | Merged | In collection info |
| get_document | get_document | Kept | Unchanged |
| resync_databases_tool | refresh_databases | Renamed | Clearer name |
| get_supported_embeddings | get_database_info | Merged | In database info |
| get_supported_chunking_strategies | get_database_info | Merged | In database info |

---

## Appendix B: Example Workflows

### Before (Phase 8.5)
```python
# Create database
await register_database(database="mydb", database_type="milvus")
await setup_database(database="mydb", embedding="auto")

# Create collection
await create_collection(database="mydb", collection="docs")

# Write document (assumes MaestroDocs if collection not specified)
await write_document(database="mydb", text="content")

# List documents (flattens all collections)
await list_documents(database="mydb")

# Delete (no safety check)
await cleanup(database="mydb")
```

### After (Phase 9)
```python
# Create database (merged register + setup)
result = await create_database(database="mydb", database_type="milvus", embedding="auto")
# Returns: {"status": "success", "data": {"database": "mydb", ...}}

# Create collection (explicit required)
result = await create_collection(database="mydb", collection="docs")
# Returns: {"status": "success", "data": {"collection": "docs", ...}}

# Write document (collection required)
result = await write_documents(
    database="mydb",
    collection="docs",
    documents=[{"text": "content"}]  # Single or list
)
# Returns: {"status": "success", "data": {"documents_written": 1, ...}}

# List documents (per collection)
result = await list_documents(database="mydb", collection="docs")
# Returns: {"status": "success", "data": {"documents": [...], ...}}

# Delete (with safety check)
result = await delete_database(database="mydb", force=False)
# Returns: {"status": "error", "error_code": "DB_NOT_EMPTY", ...}

result = await delete_database(database="mydb", force=True)
# Returns: {"status": "success", "data": {"collections_deleted": 1, ...}}
```

---

## Appendix C: Error Code Reference

See `docs/ERROR_CODES.md` for complete reference (to be created in Phase 9.10).

Quick reference:
- `DB_*`: Database-level errors
- `COLL_*`: Collection-level errors
- `DOC_*`: Document-level errors
- `PARAM_*`: Parameter validation errors
- `CONFIG_*`: Configuration errors

---

## Questions for Review

1. **Tool consolidation**: Is 15 tools the right number, or should we consolidate further?
2. **Force parameter**: Should we require force=True for all deletions, or only non-empty resources?
3. **JSON format**: Is the proposed structure clear enough for LLM parsing?
4. **Migration timeline**: Is 6 weeks realistic for implementation?
5. **Backward compatibility**: Should we keep old tools with deprecation warnings, or remove immediately?

---

**End of Phase 9 Planning Document**

---

## Appendix D: Clarifications & Decisions (from Feedback)

### Question 1: Query vs Search - Keep Both?

**Decision**: YES - Keep both tools

**Rationale**:
- **query**: Returns natural language summary with citations
  - Format: `{"summary": "Machine learning is...", "sources": [...]}`
  - Use case: Direct presentation to end users, conversational responses
  
- **search**: Returns structured JSON array with full metadata
  - Format: `[{"text": "...", "score": 0.95, "url": "...", "metadata": {...}}]`
  - Use case: Programmatic processing, detailed analysis, quality filtering

**Value**: Different use cases require different formats. Query is for "tell me about X" while search is for "find all documents matching Y with score > 0.8"

### Question 2: JSON Responses and CLI Compatibility

**Decision**: JSON-first is correct approach

**Rationale**:
- MCP tools should return structured data (JSON)
- Client applications (CLI, UI) handle presentation
- CLI can parse JSON and format for terminal display
- Separation of concerns: tools provide data, clients provide UX

**CLI Handling** (for maestro-cli team):
- Simple mode: Display `message` field only
- Verbose mode: Pretty-print full JSON
- Programmatic mode: Output raw JSON for piping

### Question 3: Chunking Configuration Retrieval

**Decision**: Already supported, enhance visibility

**Current State**:
- `get_collection_info()` returns chunking configuration
- Stored in Milvus collection description field as JSON

**Phase 9 Enhancement**:
```json
{
  "status": "success",
  "data": {
    "name": "docs",
    "chunking": {
      "strategy": "Sentence",
      "parameters": {"chunk_size": 512, "overlap": 0},
      "immutable": true,
      "note": "Chunking strategy cannot be changed after collection creation"
    }
  }
}
```

### Question 4: Embedding Configuration Scope

**Decision**: Keep current behavior (server-wide), document clearly

**Current Architecture**:
- Server enforces same embedding config for all databases
- Environment variables (CUSTOM_EMBEDDING_URL, etc.) are global
- Practical for most use cases (single database per client)

**Phase 9 Response Format**:
```json
{
  "status": "success",
  "data": {
    "database": "mydb",
    "embedding_config": {
      "current": "custom_local",
      "scope": "server-wide",
      "note": "All databases on this server use the same embedding configuration",
      "supported": [...]
    }
  }
}
```

**Future Consideration** (Phase 10+): Per-database embedding configuration

### Question 5: Document ID Source

**Clarification**: document_id is the unique identifier for retrieval/deletion

**Sources**:
1. **Write operations**: `url` parameter becomes document_id
   - If url provided: Use as-is
   - If url empty: Auto-generate from text hash (Phase 8.5 feature)
   - Example: `url="https://example.com/doc"` → `document_id="https://example.com/doc"`
   - Example: `url=""` → `document_id="doc_a1b2c3d4e5f6g7h8"` (auto-generated)

2. **Retrieval operations**: Specify document_id explicitly
   - `get_document(database="mydb", collection="docs", document_id="https://example.com/doc")`
   - `delete_documents(database="mydb", collection="docs", document_ids=["doc_a1b2c3d4"])`

**Naming Consistency**:
- Write: `url` parameter (can be URL or identifier)
- Read/Delete: `document_id` parameter (exact identifier to find)
- Internal: Both map to same field in database

### Question 6: Database Sync Solution

**Decision**: Option A - Auto-register backend databases (RECOMMENDED)

**Implementation**:
```python
async def list_databases() -> str:
    """List all databases, including auto-discovered backend databases."""
    # 1. Get registered databases
    registered = list(vector_databases.keys())
    
    # 2. Auto-discover backend databases (with timeout protection)
    discovered = await discover_backend_databases()
    
    # 3. Auto-register discovered databases
    for db_name in discovered:
        if db_name not in vector_databases:
            vector_databases[db_name] = create_vector_database(
                db_type="milvus",
                collection_name=db_name,
                auto_discovered=True
            )
    
    # 4. Return merged list
    all_databases = list(set(registered + discovered))
    
    return json.dumps({
        "status": "success",
        "data": {
            "databases": all_databases,
            "total": len(all_databases)
        }
    })
```

**Benefits**: Matches Attu UI behavior, no manual sync required, safe (read-only)

### Question 7: Error Code Naming

**Decision**: Use FULL names for clarity

**Rationale**:
- LLMs parse text better with full words
- Humans find full names clearer
- Consistent with industry standards

**Updated Error Codes**:
- `DATABASE_NOT_FOUND` (not DB_NOT_FOUND)
- `COLLECTION_NOT_FOUND` (not COLL_NOT_FOUND)
- `DOCUMENT_NOT_FOUND` (not DOC_NOT_FOUND)
- `PARAMETER_MISSING` (not PARAM_MISSING)
- `CONFIGURATION_EMBEDDING_INVALID` (not CONFIG_EMBEDDING_INVALID)

### Question 8: Additional LLM Agent Feedback

**Reviewed**: docs/LLM_TESTING_NOTES_PARK1_RESPONSE.md

**Key Alignments**:
- ✅ Naming consolidation (register→create, cleanup→delete)
- ✅ Force flags for deletions
- ✅ JSON-first responses with embedded text
- ✅ Enhanced embedding details
- ✅ Remove default collection behavior
- ✅ Merge count_documents into get_collection_info

**Discrepancies Resolved**:
- Agent suggested "remove_database" vs our "delete_database"
  - **Decision**: Use `delete_database` (more common in APIs, matches delete_collection)
- Agent suggested separate list_documents_in_collection
  - **Decision**: Merge into list_collections with include_documents flag (reduces tool count)

---

## Summary: Ready for Implementation

**Primary Document**: This file (PHASE9_LLM_USABILITY_REFACTORING.md)

**Status**: All feedback questions answered, plan is complete and ready for Code mode implementation

**Final Tool Count**: 14 tools (36% reduction from 22)

**Key Decisions Documented**:
1. ✅ Keep query AND search (different use cases)
2. ✅ JSON-first with embedded human-readable text
3. ✅ Chunking config retrievable via get_collection_info
4. ✅ Embedding config returned per-database (server-wide scope documented)
5. ✅ document_id comes from url parameter in writes
6. ✅ Auto-register backend databases (Option A)
7. ✅ Full error code names (DATABASE_NOT_FOUND not DB_NOT_FOUND)

**Next Step**: Switch to Code mode and begin Phase 9.1 implementation

---

**End of Phase 9 Planning Document**