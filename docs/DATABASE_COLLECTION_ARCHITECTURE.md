# Database vs Collection Architecture Issues

## Current Status: Partially Resolved

This document explains the confusing terminology in our codebase and what we've done to mitigate it.

---

## The Core Problem

### What Users Expect
In typical vector database architectures:
- **Database** = Top-level container (e.g., PostgreSQL database)
- **Collection/Table** = Container within a database (e.g., "documents", "embeddings")
- **Documents** = Individual records within a collection

Example hierarchy:
```
Database: "production"
  ├── Collection: "user_docs"
  │   ├── Document 1
  │   ├── Document 2
  │   └── ...
  └── Collection: "system_logs"
      ├── Document 1
      └── ...
```

### What We Actually Have

Our internal architecture conflates these concepts:

```python
# Internal registry (in server.py)
vector_databases = {
    "my_collection": VectorDatabase(collection_name="my_collection"),
    "another_collection": VectorDatabase(collection_name="another_collection"),
}
```

**The Problem**: Each key in `vector_databases` dict is called a "database" but actually represents a **collection instance**.

### Why This Happened

1. **Historical reasons**: Early code used "database" to mean "a database connection"
2. **Backend differences**:
   - **Milvus**: Has databases → collections → documents hierarchy
   - **Weaviate**: Has classes (collections) → objects (documents) - no database concept
3. **Abstraction leak**: We tried to abstract over both backends but leaked the wrong terminology

---

## Impact on Users

### Confusion Example 1: List Operations
User calls `list_databases()` expecting:
```
Database: milvus_prod
  - Collection: docs (100 documents)
  - Collection: logs (50 documents)
```

But actually gets:
```
Database: docs (100 documents)
Database: logs (50 documents)
```

Each "database" is actually a collection!

### Confusion Example 2: Delete Operations
User calls:
```python
delete_collection(database="my_db", collection="my_collection")
```

But `database` parameter is actually the collection identifier, and `collection` is the collection name within that "database". This is backwards!

### Confusion Example 3: Caching Bug
When deleting a collection:
1. Collection deleted from Milvus ✅
2. Entry NOT removed from `vector_databases` dict ❌
3. `list_databases()` still shows deleted collection ❌

---

## What We've Fixed (Phase 9)

### 1. Removed "database" Parameter from MCP API ✅

**Before:**
```python
write_documents(database="my_db", collection="my_coll", documents=[...])
delete_collection(database="my_db", collection="my_coll")
```

**After:**
```python
write_documents(collection="my_coll", documents=[...])
delete_collection(collection="my_coll")
```

**Internal behavior**: `database` variable still exists internally and defaults to `collection` name.

### 2. Fixed Delete Collection Caching Bug ✅

Added cleanup code to remove from in-memory registry:
```python
# In delete_collection()
if database in vector_databases:
    del vector_databases[database]
    logger.info(f"Removed database '{database}' from in-memory registry")
```

### 3. Disabled Confusing Database Tools ✅

Disabled from MCP API (commented out `@app.tool()`):
- `create_database_DISABLED()`
- `delete_database_DISABLED()`
- `list_databases_DISABLED()`

These tools exposed the confusing "database" concept to users.

### 4. Renamed Tools for Clarity ✅

- `get_database_info()` → `get_config()` - Returns system configuration
- `get_collection_info()` → `get_collection()` - Gets collection details

### 5. Updated Error Messages ✅

Changed from:
```
"Database 'my_db' not found"
```

To:
```
"Collection 'my_coll' not found"
```

---

## What Still Needs Fixing (Future Work)

### 1. Internal Variable Names

Throughout `server.py`, we still use:
```python
database = collection  # Confusing!
db = get_database_by_name(database)
```

**Should be:**
```python
collection_id = collection
db = get_collection_instance(collection_id)
```

### 2. The `vector_databases` Dict

Should be renamed to `collection_instances`:
```python
# Current (confusing)
vector_databases: dict[str, VectorDatabase] = {}

# Better
collection_instances: dict[str, VectorDatabase] = {}
```

### 3. VectorDatabase Class Name

The class `VectorDatabase` should be `CollectionInstance` or `VectorCollection`:
```python
# Current
class VectorDatabase:
    def __init__(self, collection_name: str, ...):
        self.collection_name = collection_name

# Better
class VectorCollection:
    def __init__(self, name: str, ...):
        self.name = name
```

### 4. Backend Abstraction

We need to properly abstract the database/collection hierarchy:

**For Milvus:**
```python
class MilvusBackend:
    def __init__(self, database_name: str):
        self.database = database_name
    
    def get_collection(self, collection_name: str) -> MilvusCollection:
        return MilvusCollection(self.database, collection_name)
```

**For Weaviate:**
```python
class WeaviateBackend:
    def __init__(self):
        pass  # No database concept
    
    def get_collection(self, class_name: str) -> WeaviateCollection:
        return WeaviateCollection(class_name)
```

---

## Migration Strategy (Future)

### Phase 1: Internal Refactoring (Non-Breaking)
1. Rename `vector_databases` → `collection_instances`
2. Rename internal `database` variables → `collection_id`
3. Rename `VectorDatabase` class → `VectorCollection`
4. Update all internal function names

### Phase 2: API Cleanup (Breaking Changes)
1. Remove `database` parameter entirely from internal functions
2. Update all tool implementations
3. Update tests
4. Update documentation

### Phase 3: Backend Abstraction (Major Refactor)
1. Create proper `Backend` abstraction layer
2. Separate database-level operations from collection-level
3. Support multiple databases per backend
4. Update MCP tools to support database selection

---

## Current MCP API (After Phase 9)

### Active Tools (11 total)

**Document Operations:**
1. `write_documents(collection, documents)`
2. `delete_documents(collection, document_ids, force?)`
3. `get_document(collection, document_id)`

**Collection Operations:**
4. `create_collection(collection, database?, embedding?, chunking_config?)`
5. `delete_collection(collection, force?)`
6. `get_collection(collection?, include_count?)`
7. `list_collections()`

**Query Operations:**
8. `query(query, limit?, collection?)`
9. `search(query, limit?, collection?, min_score?, metadata_filters?)`

**System Operations:**
10. `get_config(include_embeddings?, include_chunking?)`
11. `refresh_databases()` - Internal tool for discovery

**Note**: `create_collection` still has optional `database` parameter for backward compatibility, but it defaults to `collection` name if not provided.

### Disabled Tools (Not Exposed in MCP API)
- `create_database_DISABLED()`
- `delete_database_DISABLED()`
- `list_databases_DISABLED()`

---

## Key Takeaways

1. **Current state**: "database" parameter removed from most MCP tools, but internal code still uses confusing terminology
2. **User impact**: Significantly reduced - users now work with "collections" not "databases"
3. **Technical debt**: Internal code needs major refactoring to fix terminology
4. **Backward compatibility**: Optional `database` parameter in `create_collection` for transition period

---

## References

- **Phase 9 Changes**: See `docs/API_CLEANUP_SUMMARY.md`
- **Migration Guide**: See `docs/MIGRATION_GUIDE.md`
- **Original Problem**: See `docs/DATABASE_PARAMETER_SIMPLIFICATION.md`