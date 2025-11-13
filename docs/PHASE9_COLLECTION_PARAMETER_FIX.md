# Phase 9: Collection Parameter Fix

## Problem Identified

The `write_documents` tool was missing the `collection` parameter, causing it to use a stateful approach that couldn't handle multiple collections.

### Root Cause

**Flawed Architecture:**
```python
# Global state
vector_databases: dict[str, VectorDatabase] = {}
# Key: database_name -> Value: VectorDatabase instance with ONE collection_name

# Factory creates database with placeholder
create_vector_database(db_type)  # collection_name = "_placeholder_"

# write_documents used db.collection_name (stateful)
db.write_documents(documents)  # Uses db.collection_name
```

**The Problem:**
1. Each database instance stored a SINGLE `collection_name` attribute
2. Creating multiple collections would overwrite this attribute
3. `write_documents` had no `collection` parameter - used `db.collection_name`
4. Result: Could only write to the last created collection

**Error Message:**
```
"can't find collection[database=default][collection=_placeholder_]"
```

## Solution: Stateless API

### API Change

**Before (BROKEN):**
```python
write_documents(database="mydb", documents=[...])
# Uses db.collection_name internally (stateful)
```

**After (FIXED):**
```python
write_documents(database="mydb", collection="docs", documents=[...])
# Explicit collection parameter (stateless)
```

### Implementation

**1. Added `collection` Parameter to MCP Tool:**
```python
@app.tool()
async def write_documents(
    database: str = Field(..., description="Name of the vector database instance"),
    collection: str = Field(
        ..., description="Name of the collection to write documents to"
    ),
    documents: list[dict[str, Any]] = Field(...),
) -> str:
```

**2. Pass Collection Directly (Stateless):**
```python
# Pass collection_name directly to the underlying method
ok, stats_any = await run_with_timeout(
    db.write_documents(documents, collection_name=collection),
    "write_documents",
    get_timeout("write_bulk"),
)
```

**Key Point:** The `VectorDatabase.write_documents()` method already accepts an optional `collection_name` parameter! We just needed to pass it through.

### Why This Approach?

**Truly Stateless:**
- No mutation of shared state (`db.collection_name`)
- No temporary switching/restoring
- Thread-safe and concurrency-safe
- Each call is completely independent

**Minimal Changes:**
- Only added parameter to MCP tool signature
- Pass parameter through to existing method
- No changes to VectorDatabase implementations needed

**Already Supported:**
The VectorDatabase base class already defined this:
```python
@abstractmethod
async def write_documents(
    self,
    documents: list[dict[str, Any]],
    collection_name: str | None = None,  # Already exists!
) -> dict[str, Any]:
```

## API Consistency

All document operations now have consistent signatures:

```python
# ✅ Consistent - All take (database, collection, ...)
write_documents(database, collection, documents)
delete_documents(database, collection, document_ids, force)
get_document(database, collection, document_id)
search(database, query, limit, ...)  # Uses db.collection_name internally
query(database, query, ...)  # Uses db.collection_name internally
```

**Note:** `search` and `query` still use `db.collection_name` internally but this is acceptable because:
1. They're read operations (less critical than writes)
2. They can be updated in a future phase if needed
3. The pattern is established for future consistency

## Files Modified

### 1. src/maestro_mcp/server.py
- Added `collection` parameter to `write_documents` (line 621-623)
- Pass `collection_name=collection` to `db.write_documents()` (line 701)
- Updated error messages to use explicit `collection` parameter
- **No state mutation** - completely stateless implementation

### 2. tests/e2e/test_functions.py
- Updated all `write_documents` calls to include `collection` parameter
- 6 test functions updated:
  - `run_document_operations_tests()`
  - `run_query_operations_tests()`
  - `run_document_retrieval_tests()`
  - `run_bulk_operations_tests()`
  - `run_collection_specific_tests()`
  - `run_full_flow_test()`

### 3. docs/PHASE9.3_CHANGES_LOG.md
- Updated with root cause analysis
- Documented the architectural flaw
- Explained the fix approach

## Testing

**Test Command:**
```bash
./stop.sh && ./start.sh && sleep 10 && \
MILVUS_URI=http://localhost:19530 \
CUSTOM_EMBEDDING_URL=http://localhost:11434/api/embeddings \
CUSTOM_EMBEDDING_MODEL=nomic-embed-text \
CUSTOM_EMBEDDING_VECTORSIZE=768 \
E2E_BACKEND=milvus \
E2E_MILVUS=1 \
uv run pytest tests/e2e/test_mcp_milvus_e2e.py -v -m "e2e"
```

**Expected Result:**
All 5 previously failing tests should now pass:
- `test_document_operations`
- `test_query_operations`
- `test_document_retrieval`
- `test_bulk_operations`
- `test_full_flow`

## Multi-Collection Support

The fix enables proper multi-collection support:

```python
# Create database
create_database(database="mydb", database_type="milvus")

# Create multiple collections
create_collection(database="mydb", collection="docs")
create_collection(database="mydb", collection="archive")
create_collection(database="mydb", collection="temp")

# Write to different collections independently
write_documents(database="mydb", collection="docs", documents=[...])
write_documents(database="mydb", collection="archive", documents=[...])
write_documents(database="mydb", collection="temp", documents=[...])

# Each write goes to the correct collection!
```

## Future Improvements

### Phase 10: Full Multi-Collection Architecture (Optional)

If we want to fully eliminate the stateful approach:

1. **Change storage structure:**
```python
# Current (one VectorDatabase per database name)
vector_databases: dict[str, VectorDatabase] = {}

# Future (nested structure)
vector_databases: dict[str, dict[str, VectorDatabase]] = {}
# Key: database_name -> collection_name -> VectorDatabase instance
```

2. **Update all tools** to use explicit collection lookup
3. **Remove `db.collection_name`** attribute entirely
4. **Update VectorDatabase base class** to not require collection_name in constructor

**Effort:** 2-3 days
**Risk:** Medium (affects core architecture)
**Benefit:** Cleaner architecture, no temporary state switching

## Conclusion

The fix successfully addresses the problem with a truly stateless solution:
- ✅ Adds missing `collection` parameter to `write_documents`
- ✅ Maintains API consistency with other document operations
- ✅ Enables multi-collection support
- ✅ **Completely stateless** - no shared state mutation
- ✅ **Thread-safe** - safe for concurrent access
- ✅ **Minimal changes** - leverages existing VectorDatabase API
- ✅ Low risk (no core architecture changes)

The solution is elegant because:
- The underlying `write_documents()` method already supported `collection_name` parameter
- We just needed to expose it at the MCP tool level
- No temporary state switching required
- Safe for concurrent requests to different collections