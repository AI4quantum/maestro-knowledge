# Phase 9 Clarifications & Decisions

**Date**: 2025-01-12  
**Status**: Approved clarifications based on feedback

## Feedback Questions & Decisions

### 1. Additional Input from LLM Agent Responses

**Reviewed**: docs/LLM_TESTING_NOTES_PARK1_RESPONSE.md

**Key Alignments**:
- ✅ Naming consolidation (register→create, cleanup→delete)
- ✅ Force flags for deletions
- ✅ JSON-first responses with embedded text
- ✅ Enhanced embedding details
- ✅ Remove default collection behavior
- ✅ Merge count_documents into get_collection_info

**Discrepancies Noted**:
- Agent suggested "remove_database" vs our "delete_database"
  - **Decision**: Use `delete_database` (more common in APIs, matches delete_collection)
- Agent suggested separate list_documents_in_collection
  - **Decision**: Merge into list_collections with include_documents flag (reduces tool count)

### 2. Query vs Search - Keep Both?

**Question**: Do we need both query and search tools?

**Decision**: YES - Keep both with clear distinction

**Rationale**:
- **query**: Returns natural language summary with citations
  - Format: `{"summary": "Machine learning is...", "sources": [...]}`
  - Use case: Direct presentation to end users
  - LLM-friendly conversational response
  
- **search**: Returns structured JSON array with full metadata
  - Format: `[{"text": "...", "score": 0.95, "url": "...", "source_citation": "...", "metadata": {...}}]`
  - Use case: Programmatic processing, detailed analysis, filtering
  - Supports min_score and metadata_filters for quality control

**Value**: Different use cases require different formats. Query is for "tell me about X" while search is for "find all documents matching Y with score > 0.8"

### 3. JSON Responses and CLI Compatibility

**Question**: Does JSON-first break CLI usability?

**Decision**: JSON-first is correct approach

**Rationale from Section 9.3**:
- MCP tools should return structured data (JSON)
- Client applications (CLI, UI) handle presentation
- CLI can parse JSON and format for terminal display
- Separation of concerns: tools provide data, clients provide UX

**Implementation**:
```json
{
  "status": "success",
  "message": "Human-readable summary for quick display",
  "data": {
    // Structured data for programmatic use
  }
}
```

**CLI Handling**:
- Simple mode: Display `message` field only
- Verbose mode: Pretty-print full JSON
- Programmatic mode: Output raw JSON for piping

**Note**: maestro-cli (separate repo) will be updated to parse JSON responses

### 4. Chunking Configuration Retrieval

**Question**: Can we retrieve chunking config after collection creation?

**Decision**: YES - Already supported, enhance visibility

**Current State**:
- `get_collection_info()` returns chunking configuration
- Stored in collection metadata

**Enhancement for Phase 9**:
```json
{
  "status": "success",
  "data": {
    "name": "docs",
    "chunking": {
      "strategy": "Sentence",
      "parameters": {
        "chunk_size": 512,
        "overlap": 0
      },
      "immutable": true,
      "note": "Chunking strategy cannot be changed after collection creation"
    }
  }
}
```

**Milvus Storage**:
- Collection description field stores JSON metadata
- Format: `{"chunking": {...}, "embedding": {...}, "created_at": "..."}`
- Retrieved via collection.describe()

**Future Enhancement** (not Phase 9):
- Consider dedicated metadata table for complex metadata
- Current single description field is sufficient for now

### 5. Embedding Configuration Scope

**Question**: Embeddings are server-global, but returned per-database?

**Decision**: YES - Keep current behavior, document clearly

**Current Architecture**:
- Server enforces same embedding config for all databases
- Environment variables (CUSTOM_EMBEDDING_URL, etc.) are global
- Each database can theoretically use different embedding, but server config is shared

**Phase 9 Approach**:
- Return embedding info in `get_database_info()` response
- Include note: "Embedding configuration is server-wide"
- Most clients use single database, so this is practical

**Response Format**:
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

**Future Consideration** (Phase 10+):
- Per-database embedding configuration
- Requires architecture change (separate embedding clients per database)
- Not priority for current use cases

### 6. Document ID Source and Standardization

**Question**: Where does document_id come from in standardization rules?

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

**Updated Parameter Matrix**:
| Tool | url (write) | document_id (read/delete) |
|------|-------------|---------------------------|
| write_documents | ✓ in docs (optional) | - |
| get_document | - | ✓ required |
| delete_documents | - | ✓ required |

### 7. Database Sync Solution

**Question**: Which option for database sync?

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
            # Register with minimal config
            vector_databases[db_name] = create_vector_database(
                db_type="milvus",  # or detect from backend
                collection_name=db_name,
                auto_discovered=True
            )
    
    # 4. Return merged list
    all_databases = list(set(registered + discovered))
    
    return json.dumps({
        "status": "success",
        "data": {
            "databases": all_databases,
            "total": len(all_databases),
            "note": "Includes auto-discovered backend databases"
        }
    })
```

**Benefits**:
- Matches Attu UI behavior
- No manual sync required
- Safe (read-only discovery)
- Transparent to users

### 8. Error Code Naming

**Question**: Use short codes (DB_NOT_FOUND) or long (DATABASE_NOT_FOUND)?

**Decision**: Use FULL names for clarity

**Rationale**:
- LLMs parse text better with full words
- Humans find full names clearer
- Slight length increase is worth clarity
- Consistent with industry standards (HTTP uses full words)

**Updated Error Codes**:
- ~~DB_NOT_FOUND~~ → `DATABASE_NOT_FOUND`
- ~~COLL_NOT_FOUND~~ → `COLLECTION_NOT_FOUND`
- ~~DOC_NOT_FOUND~~ → `DOCUMENT_NOT_FOUND`
- ~~PARAM_MISSING~~ → `PARAMETER_MISSING`
- ~~CONFIG_EMBEDDING_INVALID~~ → `CONFIGURATION_EMBEDDING_INVALID`

**Format**:
```json
{
  "status": "error",
  "error_code": "COLLECTION_NOT_FOUND",
  "message": "Collection 'docs' not found in database 'mydb'",
  "details": {...},
  "suggestion": "..."
}
```

## Summary of Changes to Plan

### Tool Count
- **Original**: 22 → 15 tools
- **Updated**: 22 → 14 tools (removed list_documents as separate tool)

### Key Decisions
1. ✅ Keep query AND search (different use cases)
2. ✅ JSON-first with embedded human-readable text
3. ✅ Chunking config retrievable via get_collection_info
4. ✅ Embedding config returned per-database (server-wide scope documented)
5. ✅ document_id comes from url parameter in writes
6. ✅ Auto-register backend databases (Option A)
7. ✅ Full error code names (DATABASE_NOT_FOUND not DB_NOT_FOUND)

### Updated Tool List (14 tools)

**Database (5)**: create_database, delete_database, get_database_info, list_databases, refresh_databases

**Collection (4)**: create_collection, delete_collection, get_collection_info, list_collections

**Document (3)**: write_documents, delete_documents, get_document

**Query (2)**: query, search

### No Changes Needed
- Phase 9.3 already covers JSON + text approach
- Phase 9.6 already covers embedding in get_database_info
- Phase 9.7 already recommends Option A for sync
- Phase 9.4 parameter matrix needs minor update for document_id clarification

## Action Items

1. Update PHASE9_LLM_USABILITY_REFACTORING.md:
   - Change tool count to 14
   - Add query vs search distinction explanation
   - Update error codes to full names
   - Clarify document_id source
   - Confirm Option A for database sync

2. Proceed with implementation once plan approved

3. Ensure CLI compatibility documented for maestro-cli team

---

**Status**: Ready for implementation approval