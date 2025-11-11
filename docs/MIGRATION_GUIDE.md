# Migration Guide: Maestro Knowledge LLM-Friendly Refactoring

> **⚠️ MIGRATION IN PROGRESS**
>
> **Current Status**: Phase 1 & 2 COMPLETE ✅
>
> **Next Phase**: Phase 3 (Bug Fixes) - See `docs/REFACTORING_PLAN.md`
>
> **For AI Agents**: Check `docs/AGENTS.md` for development tips and common pitfalls

## Migration Status Tracker

| Phase | Status | Description | Breaking Changes |
|-------|--------|-------------|------------------|
| Phase 1 | ✅ COMPLETE | Remove 'input' wrapper | YES - All tool calls |
| Phase 2 | ✅ COMPLETE | Remove per-write embedding | YES - Embedding architecture |
| Phase 2.5 | ✅ COMPLETE | Improve embedding docs | NO |
| Phase 2.6 | ✅ COMPLETE | Separate setup from collection creation | YES - Tool naming & workflow |
| Phase 3 | 📋 PLANNED | Fix reassembly bug | NO |
| Phase 4 | 📋 PLANNED | Add ownership metadata | NO |
| Phase 5 | 📋 PLANNED | Implement access control | NO |
| Phase 6 | 📋 PLANNED | Add search quality controls | NO |
| Phase 7 | 📋 PLANNED | Improve citation format | NO |
| Phase 8 | 📋 PLANNED | Enhance error messages | NO |
| Phase 9 | 📋 PLANNED | Update test suite | NO |
| Phase 10 | 📋 PLANNED | Update documentation | NO |

## Overview

The Maestro Knowledge MCP server is being refactored to be more LLM-agent friendly by:
1. **Removing nested 'input' wrappers** (Phase 1) ✅
2. **Renaming parameters for clarity** (Phase 2) 📋
3. **Fixing critical bugs** (Phase 3+) 📋

## Breaking Changes by Phase

### Phase 1: Flat Parameter Structure (COMPLETED)

**What Changed:**
- Removed nested `{"input": {...}}` wrapper from all tool calls
- All parameters are now at the top level of the request object
- Removed 21 Input model classes from the codebase

**Migration Required:** YES - All tool calls must be updated

#### Before (Old Format)
```python
# Old nested format with 'input' wrapper
await client.call_tool("create_vector_database_tool", {
    "input": {
        "db_name": "mydb",
        "db_type": "milvus",
        "collection_name": "docs"
    }
})

await client.call_tool("query", {
    "input": {
        "db_name": "mydb",
        "query": "What is this about?",
        "limit": 5
    }
})
```

#### After (New Format)
```python
# New flat format - parameters at top level
await client.call_tool("create_vector_database_tool", {
    "database": "mydb",
    "database_type": "milvus",
    "collection": "docs"
})

await client.call_tool("query", {
    "database": "mydb",
    "query": "What is this about?",
    "limit": 5
})
```

### Phase 2: Embedding Architecture Simplification (COMPLETED)

**What Changed:**
- Removed `embedding` parameter from all write operations (write_documents, write_document, write_document_to_collection)
- Embedding model is now configured ONLY during collection creation (setup_database, create_collection)
- All documents in a collection use the same embedding model (required for vector search consistency)
- Simplified API with clearer semantics

**Migration Required:** YES - Remove embedding parameter from write calls

**Rationale:** Per-document embedding configuration was confusing and technically incorrect. Vector search requires all documents in a collection to use the same embedding model for meaningful similarity comparisons.

#### API Changes

**Before (Phase 1):**
```python
# Old: Embedding could be specified per-write (INCORRECT)
await client.call_tool("write_documents", {
    "database": "mydb",
    "documents": [...],
    "embedding": "text-embedding-ada-002"  # ❌ Removed
})
```

**After (Phase 2):**
```python
# Step 1: Set embedding during collection creation
await client.call_tool("setup_database", {
    "database": "mydb",
    "embedding": "text-embedding-ada-002"  # ✅ Set once here
})

# Step 2: Write documents (no embedding parameter)
await client.call_tool("write_documents", {
    "database": "mydb",

### Phase 2.5: Improved Embedding Documentation (COMPLETED)

**What Changed:**
- Enhanced documentation for `embedding` parameter in `setup_database` and `create_collection`
- Clarified available embedding options and their behavior
- Added explicit guidance on when to use `custom_local` embedding

**Migration Required:** NO - Documentation only

**Benefits:**
- Clearer understanding of embedding options
- Better guidance for custom embedding configuration
- Explicit documentation of 'default' behavior

### Phase 2.6: Separated Database Setup from Collection Creation (COMPLETED)

**What Changed:**
- `setup_database` now ONLY initializes database connection (no longer creates collections)
- Added new `create_collection()` method to vector database implementations
- Renamed `create_vector_database_tool` to `register_database` for clarity
- Collections must now be created explicitly using `create_collection()`

**Migration Required:** YES - Workflow changes required

**Rationale:** Clearer separation of concerns makes the API more explicit and easier to understand for LLM agents. Database initialization and collection creation are now distinct operations.

#### Before (Phase 2)
```python
# Old: setup_database created a default collection
await client.call_tool("create_vector_database_tool", {
    "database": "mydb",
    "database_type": "milvus",
    "collection": "docs"
})

await client.call_tool("setup_database", {
    "database": "mydb",
    "embedding": "text-embedding-ada-002"
})
# Collection was created automatically during setup
```

#### After (Phase 2.6)
```python
# New: Explicit three-step process
# Step 1: Register database instance
await client.call_tool("register_database", {  # Renamed from create_vector_database_tool
    "database": "mydb",
    "database_type": "milvus",
    "collection": "docs"  # Default collection name only
})

# Step 2: Initialize connection
await client.call_tool("setup_database", {
    "database": "mydb",
    "embedding": "text-embedding-ada-002"
})

# Step 3: Explicitly create collection
await client.call_tool("create_collection", {
    "database": "mydb",
    "collection": "docs",
    "embedding": "text-embedding-ada-002"
})
```

#### Tool Naming Changes
- `create_vector_database_tool` → `register_database` (more accurate name)
- `setup_database` behavior changed (no longer creates collections)
- `cleanup` remains the counterpart to both `register_database` and `setup_database`

#### Operation Symmetry
```
register_database    → Creates registry entry
setup_database      → Initializes connection  
create_collection   → Creates collection
delete_collection   → Deletes collection
cleanup             → Closes connection & removes registry entry
```

    "documents": [...]  # Uses collection's embedding model
})
```

#### Examples

**Create Database:**
```python
# Before
{"input": {"db_name": "mydb", "db_type": "milvus", "collection_name": "docs"}}

# After
{"database": "mydb", "database_type": "milvus", "collection": "docs"}
```

**Write Documents:**
```python
# Before
{"input": {"db_name": "mydb", "documents": [...]}}

# After
{"database": "mydb", "documents": [...]}
```

**Query:**
```python
# Before
{"input": {"db_name": "mydb", "query": "search term", "limit": 5, "collection_name": "docs"}}

# After
{"database": "mydb", "query": "search term", "limit": 5, "collection": "docs"}
```

**Delete Document from Collection:**
```python
# Before
{"input": {"db_name": "mydb", "collection_name": "docs", "doc_name": "mydoc"}}

# After
{"database": "mydb", "collection": "docs", "document_name": "mydoc"}
```

## Complete Tool Reference

### Database Management Tools

#### register_database (formerly create_vector_database_tool)
**⚠️ RENAMED in Phase 2.6**
```python
# New format
{
    "database": str,              # Required: Database name
    "database_type": str,         # Required: "milvus" or "weaviate"
    "collection": str             # Optional: Default "MaestroDocs"
}
```

**Migration Note:** The tool `create_vector_database_tool` has been renamed to `register_database` for clarity. This tool creates an in-memory registry entry. After registration, you must call `setup_database()` to initialize the connection, then `create_collection()` to create collections.

#### setup_database
**⚠️ BEHAVIOR CHANGED in Phase 2.6**
```python
{
    "database": str,              # Required: Database name
    "embedding": str              # Optional: Default "default"
}
```

**Migration Note:** `setup_database` now ONLY initializes the database connection. It no longer creates collections. You must explicitly call `create_collection()` after setup.

#### get_database_info
```python
{
    "database": str               # Required: Database name
}
```

#### list_databases
```python
{}  # No parameters
```

#### cleanup
```python
{
    "database": str               # Required: Database name
}
```

### Collection Management Tools

#### create_collection
```python
{
    "database": str,              # Required: Database name
    "collection": str,            # Required: Collection name
    "embedding": str,             # Optional: Default "default"
    "chunking_config": dict       # Optional: Chunking configuration
}
```

#### list_collections
```python
{
    "database": str               # Required: Database name
}
```

#### get_collection_info
```python
{
    "database": str,              # Required: Database name
    "collection": str             # Optional: Default collection if not provided
}
```

#### delete_collection
```python
{
    "database": str,              # Required: Database name
    "collection": str             # Optional: Collection to delete
}
```

### Document Operations

#### write_documents
```python
{
    "database": str,              # Required: Database name
    "documents": list[dict]       # Required: List of documents
    # Note: Uses embedding model configured during collection creation
}
```

#### write_document
```python
{
    "database": str,              # Required: Database name
    "url": str,                   # Required: Document URL
    "text": str,                  # Required: Document text
    "metadata": dict,             # Optional: Additional metadata
    "vector": list[float]         # Optional: Pre-computed vector
    # Note: Uses embedding model configured during collection creation
}
```

#### write_document_to_collection
```python
{
    "database": str,              # Required: Database name
    "collection": str,            # Required: Collection name
    "document_name": str,         # Required: Document name
    "text": str,                  # Required: Document text
    "url": str,                   # Required: Document URL
    "metadata": dict,             # Optional: Additional metadata
    "vector": list[float]         # Optional: Pre-computed vector
    # Note: Uses embedding model configured during collection creation
}
```

#### list_documents
```python
{
    "database": str,              # Required: Database name
    "limit": int,                 # Optional: Default 10
    "offset": int                 # Optional: Default 0
}
```

#### list_documents_in_collection
```python
{
    "database": str,              # Required: Database name
    "collection": str,            # Required: Collection name
    "limit": int,                 # Optional: Default 10
    "offset": int                 # Optional: Default 0
}
```

#### count_documents
```python
{
    "database": str               # Required: Database name
}
```

#### get_document
```python
{
    "database": str,              # Required: Database name
    "collection": str,            # Required: Collection name
    "document_name": str          # Required: Document name
}
```

#### delete_document
```python
{
    "database": str,              # Required: Database name
    "document_id": str            # Required: Document ID
}
```

#### delete_documents
```python
{
    "database": str,              # Required: Database name
    "document_ids": list[str]     # Required: List of document IDs
}
```

#### delete_document_from_collection
```python
{
    "database": str,              # Required: Database name
    "collection": str,            # Required: Collection name
    "document_name": str          # Required: Document name
}
```

### Query and Search Tools

#### query
```python
{
    "database": str,              # Required: Database name
    "query": str,                 # Required: Query string
    "limit": int,                 # Optional: Default 5
    "collection": str             # Optional: Specific collection
}
```

#### search
```python
{
    "database": str,              # Required: Database name
    "query": str,                 # Required: Query string
    "limit": int,                 # Optional: Default 5
    "collection": str             # Optional: Specific collection
}
```

### Utility Tools

#### get_supported_embeddings
```python
{
    "database": str               # Required: Database name
}
```

#### get_supported_chunking_strategies
```python
{}  # No parameters
```

#### resync_databases_tool
```python
{}  # No parameters
```

## Migration Checklist

### For Application Developers

- [ ] Update all tool calls to remove `"input"` wrapper
- [ ] Rename all parameters according to the mapping table
- [ ] Update any hardcoded parameter names in your code
- [ ] Test all database operations
- [ ] Test all collection operations
- [ ] Test all document operations
- [ ] Test query and search functionality
- [ ] Update your documentation
- [ ] Update your tests

### For LLM Agent Developers

- [ ] Update tool schemas in your agent configuration
- [ ] Remove any code that adds `"input"` wrapper
- [ ] Update parameter name mappings
- [ ] Test agent interactions with all tools
- [ ] Update agent prompts if they reference old parameter names

## Common Migration Patterns

### Pattern 1: Simple Database Operation
```python
# Before
params = {"input": {"db_name": db_name}}

# After
params = {"database": db_name}
```

### Pattern 2: Collection Operation
```python
# Before
params = {
    "input": {
        "db_name": db_name,
        "collection_name": coll_name
    }
}

# After
params = {
    "database": db_name,
    "collection": coll_name
}
```

### Pattern 3: Document Operation
```python
# Before
params = {
    "input": {
        "db_name": db_name,
        "collection_name": coll_name,
        "doc_name": doc_name
    }
}

# After
params = {
    "database": db_name,
    "collection": coll_name,
    "document_name": doc_name
}
```

### Pattern 4: Query with Optional Collection
```python
# Before
params = {
    "input": {
        "db_name": db_name,
        "query": query_text,
        "limit": 10,
        "collection_name": coll_name  # Optional
    }
}

# After
params = {
    "database": db_name,
    "query": query_text,
    "limit": 10,
    "collection": coll_name  # Optional
}
```

## Automated Migration Script

For large codebases, consider using this Python script to help with migration:

```python
import re
import json

def migrate_tool_call(old_call: dict) -> dict:
    """Migrate a tool call from old to new format."""
    if "input" not in old_call:
        return old_call  # Already migrated
    
    # Extract parameters from input wrapper
    params = old_call["input"]
    
    # Rename parameters
    param_mapping = {
        "db_name": "database",
        "db_type": "database_type",
        "collection_name": "collection",
        "doc_name": "document_name"
    }
    
    new_params = {}
    for old_key, value in params.items():
        new_key = param_mapping.get(old_key, old_key)
        new_params[new_key] = value
    
    return new_params

# Example usage
old_call = {
    "input": {
        "db_name": "mydb",
        "collection_name": "docs",
        "query": "search term"
    }
}

new_call = migrate_tool_call(old_call)
print(json.dumps(new_call, indent=2))
```

## Troubleshooting

### Error: "input" parameter not found
**Cause:** You're still using the old nested format  
**Solution:** Remove the `"input"` wrapper and place parameters at the top level

### Error: Unknown parameter "db_name"
**Cause:** Using old parameter names  
**Solution:** Rename to new parameter names (e.g., `db_name` → `database`)

### Error: Tool schema validation failed
**Cause:** Mismatch between expected and provided parameters  
**Solution:** Check the tool reference section for correct parameter names

## Support

For questions or issues with migration:
- Check the [REFACTORING_PLAN.md](REFACTORING_PLAN.md) for detailed phase information
- Review [PHASE1_IMPLEMENTATION_PLAN.md](PHASE1_IMPLEMENTATION_PLAN.md) for implementation details
- See [PHASE1_REFACTORING_GUIDE.md](PHASE1_REFACTORING_GUIDE.md) for code examples

## Version Compatibility

- **Old Format:** Deprecated as of Phase 1 completion
- **New Format:** Required for all new integrations
- **Transition Period:** None - breaking change requires immediate migration