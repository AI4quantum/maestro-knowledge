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
| Phase 3 | ✅ COMPLETE | Fix reassembly bug | NO - Internal improvement |
| Phase 4 | ✅ COMPLETE | Add search quality controls | NO - Backward compatible |
| Phase 5 | ✅ COMPLETE | Improve citation format | NO - Additive only |
| Phase 6 | ✅ COMPLETE | Enhance error messages | NO - Backward compatible |
| Phase 7 | 📋 PLANNED | Update test suite | NO |
| Phase 8 | 📋 PLANNED | Update documentation | NO |
| Phase 9 | 📋 PLANNED | Add ownership metadata | NO |
| Phase 10 | 📋 PLANNED | Implement access control | NO |

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

### Phase 3: Fixed Document Reassembly Bug (COMPLETED)

**What Changed:**
- Fixed critical bug where overlapping text chunks were duplicated during document reassembly
- Implemented intelligent overlap detection using chunk metadata
- Added fallback text-based overlap detection when metadata unavailable
- No API changes - purely internal improvement

**Migration Required:** NO - Automatic improvement, no code changes needed

**Impact:** Documents with overlapping chunks (e.g., using Fixed chunking with `overlap > 0`) will now be correctly reassembled without text duplication.

#### The Problem

When documents were chunked with overlap (common with Fixed chunking strategy), the reassembly process would duplicate the overlapping text:

```python
# Example with overlap=10
Chunk 1: "The quick brown fox "
Chunk 2: "brown fox jumps over"  # "brown fox " overlaps

# Before Phase 3 (BUGGY):
Result: "The quick brown fox brown fox jumps over"  # ❌ Duplication!

# After Phase 3 (FIXED):
Result: "The quick brown fox jumps over"  # ✅ Correct!
```

#### The Solution

The fix uses a two-tier approach:

1. **Primary: Offset-based detection** - Uses `offset_start` and `offset_end` metadata to mathematically calculate overlap
2. **Fallback: Text-based detection** - Compares text strings when metadata unavailable

#### Benefits for Users

- **Automatic improvement** - No code changes required
- **Works with all chunking strategies** - Fixed, Sentence, and Semantic
- **Backward compatible** - Existing code continues to work
- **Better document quality** - No more duplicated text in retrieved documents

#### Technical Details

The reassembly logic now:
- Sorts chunks by sequence number
- Detects overlap using `offset_start`/`offset_end` metadata
- Skips overlapping portions when concatenating
- Falls back to text comparison if metadata missing
- Preserves all non-chunk-specific metadata

#### Example Scenarios

### Phase 4: Search Quality Controls (COMPLETED)

**What Changed:**
- Added `min_score` parameter to filter low-quality search results
- Added `metadata_filters` parameter to filter results by document metadata
- Both parameters are optional and backward compatible

**Migration Required:** NO - Existing code continues to work, new parameters are optional

**Benefits:**
- Filter out irrelevant results with `min_score` threshold
- Narrow searches by document properties with `metadata_filters`
- Improved search precision for LLM agents

#### New Parameters

**`min_score` (optional):**
- Type: `float` (0-1 range)
- Filters results below the specified similarity score
- Higher scores indicate better matches
- Example: `min_score=0.8` keeps only high-confidence results

**`metadata_filters` (optional):**
- Type: `dict[str, Any]`
- Filters results by metadata field values
- Only results matching ALL filters are returned
- Example: `{"language": "python", "level": "beginner"}`

#### Usage Examples

**Before Phase 4 (still works):**
```python
# Basic search without filters
results = await client.call_tool("search", {
    "database": "mydb",
    "query": "Python programming",
    "limit": 5
})
```

**After Phase 4 (with quality controls):**
```python
# Filter by minimum score
results = await client.call_tool("search", {
    "database": "mydb",
    "query": "Python programming",
    "limit": 10,
    "min_score": 0.8  # Only high-quality matches
})

# Filter by metadata
results = await client.call_tool("search", {
    "database": "mydb",
    "query": "programming tutorial",
    "limit": 10,
    "metadata_filters": {
        "language": "python",
        "level": "beginner"
    }
})

# Combine both filters
results = await client.call_tool("search", {
    "database": "mydb",
    "query": "advanced techniques",
    "limit": 10,
    "min_score": 0.7,
    "metadata_filters": {
        "language": "python",
        "level": "advanced"
    }
})
```

#### How It Works

1. **Score Filtering:** Applied after vector search, removes results with `score` or `similarity` below threshold
2. **Metadata Filtering:** Checks each result's metadata dictionary against all filter conditions
3. **Order:** Filters are applied in sequence (score first, then metadata)
4. **Re-ranking:** Results are re-ranked after filtering to maintain correct rank order

### Phase 5: Improved Citation Format (COMPLETED)

**What Changed:**
- Added `url` field at top level of search results (previously nested in metadata)
- Added `source_citation` field with formatted citation string
- Added `score` field as canonical similarity score (normalized 0-1)
- Improved result structure for LLM-friendly citation extraction

**Migration Required:** NO - Additive changes only, existing fields remain

**Benefits:**
- URLs are immediately visible at top level (no need to dig into metadata)
- Ready-to-use citation strings for LLM responses
- Consistent score field across all backends
- Easier for agents to cite sources correctly

#### New Result Format

**Before Phase 5:**
```json
{
  "text": "Python is a programming language...",
  "metadata": {
    "url": "https://example.com/python-guide",
    "doc_name": "Python Guide"
  },
  "similarity": 0.85,
  "rank": 1
}
```

**After Phase 5:**
```json
{
  "text": "Python is a programming language...",
  "url": "https://example.com/python-guide",
  "source_citation": "Source: Python Guide (https://example.com/python-guide)",
  "score": 0.85,
  "metadata": {
    "doc_name": "Python Guide"
  },
  "rank": 1
}
```

#### Field Descriptions

- **`url`** (top-level): Direct link to source document, easy to extract
- **`source_citation`**: Formatted string ready for LLM responses: `"Source: {doc_name} ({url})"`
- **`score`**: Canonical similarity score (0-1), normalized across backends
- **`metadata`**: Still contains all metadata, including `doc_name` and other fields

#### Usage in LLM Responses

The new format makes it trivial for LLMs to cite sources:

```python
# Agent can easily extract and cite sources
for result in results:
    print(f"Content: {result['text']}")
    print(f"Citation: {result['source_citation']}")
    print(f"Direct link: {result['url']}")
    print(f"Relevance: {result['score']:.2f}")
```

Example LLM response:
```
Python is a high-level programming language known for its simplicity and readability.

Source: Python Guide (https://example.com/python-guide)
```

#### Backward Compatibility

- All existing fields remain unchanged
- `url` is still in metadata (for backward compatibility)
- `similarity` field still present alongside `score`
- Old code continues to work without modification
### Phase 6: Enhanced Error Messages (COMPLETED)

**Status**: COMPLETE
**Date**: 2025-01-11

**What Changed:**
- Created centralized error message module with actionable guidance
- Enhanced error handling in all tool functions
- Improved tool documentation with prerequisites and common errors
- Added parameter validation with helpful error messages

**Migration Required:** NO - Backward compatible improvement

**Benefits:**
- LLM agents get actionable error messages with recovery steps
- Clear guidance on what went wrong and how to fix it
- Better parameter validation catches errors early
- Improved tool documentation helps agents understand requirements

#### New Error Message Format

**Before Phase 6:**
```
Error: Database 'mydb' not found
```

**After Phase 6:**
```
Database 'mydb' not found.

Available databases: 'docs', 'knowledge', 'support'

To create a new database:
1. Register: register_database(database="mydb", database_type="milvus", collection="default")
2. Initialize: setup_database(database="mydb", embedding="default")
3. Create collection: create_collection(database="mydb", collection="default")
```

#### Error Types Covered

1. **Database Not Found** - Lists available databases and shows creation steps
2. **Collection Not Found** - Lists available collections and shows creation command
3. **Collection Already Exists** - Suggests using existing or deleting first
4. **Database Already Exists** - Suggests using existing or cleanup
5. **Invalid Embedding** - Lists supported embeddings with descriptions
6. **Invalid Database Type** - Shows supported types (milvus, weaviate)
7. **Document Not Found** - Suggests listing documents or writing new one
8. **Invalid Parameters** - Clear validation messages for limit, min_score, etc.
9. **Operation Timeout** - Troubleshooting steps for timeouts
10. **Generic Failures** - Contextual error with troubleshooting guidance

#### Enhanced Tool Documentation

All tool functions now include:
- **Prerequisites**: What must be done before calling this tool
- **Next steps**: What to do after successful execution
- **Common errors**: Typical failure scenarios and solutions
- **Parameter descriptions**: Clear explanation of each parameter

Example from `create_collection`:
```python
"""
Create a new collection in a vector database.

Creates a collection with specified embedding model and optional chunking configuration.
All documents in the collection will use this embedding model.

Prerequisites:
1. Database registered: register_database(database="name", database_type="milvus")
2. Connection initialized: setup_database(database="name", embedding="default")

Next steps:
- Write documents: write_documents(database="name", documents=[...])

Common errors:
- Database not found: Register and initialize it first
- Collection already exists: Use delete_collection() to remove it first
- Invalid embedding: Use get_supported_embeddings() to see options
- Database not initialized: Call setup_database() first
"""
```

#### Implementation Details

**New Module**: `src/maestro_mcp/error_messages.py`
- Centralized error message templates
- Consistent formatting across all errors
- Actionable guidance for recovery

**Updated Functions**:
- `register_database` - Database type validation, existence checks
- `setup_database` - Database validation, embedding error detection
- `create_collection` - Comprehensive error handling with specific guidance
- `query` - Parameter validation, collection existence checks
- `search` - Parameter validation, result filtering, helpful suggestions
- `delete_document_from_collection` - Clear error messages for missing resources

**Parameter Validation**:
- `limit`: Must be 1-100
- `min_score`: Must be 0.0-1.0
- `database_type`: Must be 'milvus' or 'weaviate'
- `embedding`: Validated against supported models

#### Backward Compatibility

- All existing code continues to work
- Error messages are more helpful but don't change API
- No breaking changes to function signatures
- Additive improvement only

---



**Scenario 1: Fixed Chunking with Overlap**
```python
# Chunking config
{
    "strategy": "Fixed",
    "chunk_size": 512,
    "overlap": 50  # 50 character overlap
}

# Before Phase 3: Duplicated 50 characters between each chunk
# After Phase 3: Clean reassembly with no duplication
```

**Scenario 2: Sentence Chunking**
```python
# Sentence chunking may create natural overlaps
# Phase 3 handles these correctly regardless of overlap size
```

**Scenario 3: Missing Metadata**
```python
# If offset metadata is missing (legacy data)
# Falls back to text-based overlap detection
# Still produces correct results
```

#### No Action Required

This is a **transparent improvement**. Your existing code will automatically benefit from the fix:

```python
# Your existing code works unchanged
doc = await db.get_document("my_document")
# Now returns correctly reassembled text without duplication
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