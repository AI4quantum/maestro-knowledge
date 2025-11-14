# TODO: Collection Metadata Persistence

**Status:** PARTIALLY MITIGATED (Default Fallback Added in Phase 8.6)  
**Date Updated:** 2025-11-14

## Problem

Currently, collection-level metadata (embedding configuration and chunking configuration) is stored in memory in the `_collections_metadata` instance variable of the vector database classes. This metadata is lost when:

1. The MCP server restarts
2. A new database instance is created
3. Collections are accessed after server restart

This means that while the metadata IS stored during `create_collection()`, it's not available when querying collection info later, especially after restarts.

## Current Behavior

### What Works
- Metadata is stored in `_collections_metadata` during `create_collection()`:
  ```python
  self._collections_metadata[collection_name] = {
      "embedding": embedding,
      "vector_size": dimension,
      "chunking": chunking_config or {"strategy": "None", "parameters": {}},
  }
  ```

### What Doesn't Work
- After server restart, `_collections_metadata` is empty
- `get_collection_info()` tries to read from `_collections_metadata` but finds nothing
- Users see default chunking config with a note instead of actual config

### Current Workaround

**Phase 8.6 Fix Applied (2025-11-14):**
Default chunking fallback now prevents the no-chunking scenario:

```python
# In write_documents() at line ~508:
if chunking_conf is None:
    chunking_conf = {
        "strategy": "Sentence",
        "parameters": {"chunk_size": 512, "overlap": 0},
    }
    logger.info(f"No chunking config found for '{target_collection}', using default: Sentence(512, 0)")
```

This ensures chunking is ALWAYS applied, even after server restart when metadata is lost.

**Previous Workaround (for display only):**
The MCP server shows default chunking configuration when metadata is not available:
```json
{
  "chunking": {
    "strategy": "Sentence",
    "chunk_size": 512,
    "overlap": 1,
    "note": "Default chunking configuration (not explicitly set during collection creation)"
  }
}
```

## Proposed Solutions

### Option 1: Store in Collection Description (Milvus)
**Pros:**
- Native Milvus feature
- Persists with collection
- No additional storage needed

**Cons:**
- Description field is limited in size
- Requires JSON serialization/deserialization
- May not be supported by all Milvus versions

**Implementation:**
```python
# During create_collection
metadata = {
    "embedding": embedding,
    "vector_size": dimension,
    "chunking": chunking_config
}
await self.client.alter_collection(
    collection_name=collection_name,
    properties={"description": json.dumps(metadata)}
)

# During get_collection_info
description = collection_info.get("description")
if description:
    metadata = json.loads(description)
```

### Option 2: Separate Metadata Collection
**Pros:**
- Flexible schema
- Can store any amount of metadata
- Easy to query and update
- Works across all vector DB types

**Cons:**
- Requires managing an additional collection
- Adds complexity to initialization
- Need to handle metadata collection lifecycle

**Implementation:**
```python
# Create metadata collection on first use
METADATA_COLLECTION = "_maestro_metadata"

# Store metadata
await self.client.insert(
    collection_name=METADATA_COLLECTION,
    data=[{
        "collection_name": collection_name,
        "embedding": embedding,
        "vector_size": dimension,
        "chunking": chunking_config,
        "created_at": datetime.now().isoformat()
    }]
)

# Retrieve metadata
results = await self.client.query(
    collection_name=METADATA_COLLECTION,
    filter=f"collection_name == '{collection_name}'"
)
```

### Option 3: File-Based Persistence
**Pros:**
- Simple to implement
- No dependency on vector DB features
- Easy to backup and restore

**Cons:**
- Requires file system access
- Need to handle file locking
- Doesn't scale well in distributed environments
- Separate from vector DB data

**Implementation:**
```python
import json
from pathlib import Path

METADATA_FILE = Path.home() / ".maestro" / "collection_metadata.json"

# Save metadata
def save_metadata(collection_name, metadata):
    METADATA_FILE.parent.mkdir(exist_ok=True)
    data = {}
    if METADATA_FILE.exists():
        data = json.loads(METADATA_FILE.read_text())
    data[collection_name] = metadata
    METADATA_FILE.write_text(json.dumps(data, indent=2))

# Load metadata
def load_metadata(collection_name):
    if not METADATA_FILE.exists():
        return None
    data = json.loads(METADATA_FILE.read_text())
    return data.get(collection_name)
```

### Option 4: Hybrid Approach
**Pros:**
- Best of both worlds
- Fallback mechanism
- Flexible

**Cons:**
- More complex
- Need to handle sync between sources

**Implementation:**
1. Try to read from collection description (Option 1)
2. If not found, try metadata collection (Option 2)
3. If still not found, try file-based cache (Option 3)
4. If all fail, return defaults with note

## Recommendation

**Recommended: Option 2 (Separate Metadata Collection)**

Reasons:
1. **Portable**: Works across Milvus, Weaviate, and future backends
2. **Flexible**: Can store any metadata without size limits
3. **Queryable**: Easy to list all collections with their metadata
4. **Maintainable**: Clear separation of concerns
5. **Scalable**: Works in distributed environments

## Implementation Plan

### Phase 1: Add Metadata Collection Support
1. Create `_maestro_metadata` collection on first use
2. Store metadata during `create_collection()`
3. Read metadata during `get_collection_info()`
4. Handle metadata collection lifecycle (create, delete)

### Phase 2: Migration Support
1. Add tool to migrate existing collections to metadata collection
2. Provide backward compatibility for collections without metadata
3. Document migration process

### Phase 3: Enhanced Features
1. Add metadata versioning
2. Support metadata updates
3. Add metadata validation
4. Implement metadata backup/restore

## Related Files

- [`src/db/vector_db_milvus.py:290-388`](../src/db/vector_db_milvus.py) - `create_collection()` method
- [`src/db/vector_db_milvus.py:804-1050`](../src/db/vector_db_milvus.py) - `get_collection_info()` method
- [`src/maestro_mcp/server.py:1729-1742`](../src/maestro_mcp/server.py) - Chunking display with fallback

## Testing Requirements

1. **Persistence Tests**
   - Create collection with metadata
   - Restart server
   - Verify metadata is still available

2. **Migration Tests**
   - Create collection without metadata (old way)
   - Run migration
   - Verify metadata is now available

3. **Backward Compatibility Tests**
   - Collections created before metadata persistence
   - Should show defaults with note
   - Should not break existing functionality

## Priority

**Medium-High Priority**

This affects user experience when:
- Querying collection configuration
- Understanding what chunking strategy is being used
- Debugging embedding issues
- Documenting collection setup

However, the current workaround (showing defaults with note) is acceptable for now.

## Estimated Effort

- **Option 1**: 2-3 days
- **Option 2**: 3-5 days (recommended)
- **Option 3**: 1-2 days
- **Option 4**: 5-7 days

## References

- [Milvus Collection Properties](https://milvus.io/docs/manage-collections.md)
- [Weaviate Schema Configuration](https://weaviate.io/developers/weaviate/config-refs/schema)
- Phase 8.5 default chunking: Sentence-based, chunk_size=512, overlap=1