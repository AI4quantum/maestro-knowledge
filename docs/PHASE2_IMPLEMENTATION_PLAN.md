# Phase 2 Implementation Plan: Remove Embedding Parameter from Write Operations

## Overview

Phase 2 removes the deprecated `embedding` parameter from all write operations and establishes that embedding models are configured at collection creation time only.

## Rationale

**Problem**: The `embedding` parameter in write operations is confusing and error-prone:
- All documents in a collection must use the same embedding model for vector search to work
- Per-document embedding configuration doesn't make architectural sense
- The parameter was already deprecated with warnings

**Solution**: Remove `embedding` from write operations entirely. Configure embedding once during collection creation via `setup_database` or `create_collection`.

## Implementation Checklist

### ✅ Step 1: Update Base Class (COMPLETE)
**File**: `src/db/vector_db_base.py`

- [x] Remove `embedding` parameter from `write_documents()`
- [x] Remove `embedding` parameter from `write_documents_to_collection()`
- [x] Remove `embedding` parameter from `write_document()`
- [x] Update return types to `dict[str, Any]`
- [x] Fix all type hints to use `str | None`
- [x] Update docstrings

### ✅ Step 2: Update MCP Server (COMPLETE)
**File**: `src/maestro_mcp/server.py`

- [x] Remove `embedding` parameter from `write_documents` tool
- [x] Remove `embedding` parameter from `write_document` tool
- [x] Remove `embedding` parameter from `write_document_to_collection` tool
- [x] Remove deprecation warning code
- [x] Remove collection embedding lookup logic
- [x] Update docstrings
- [x] Keep `embedding` in `setup_database` and `create_collection`

### ✅ Step 3: Update Milvus Backend (COMPLETE)
**File**: `src/db/vector_db_milvus.py`

- [x] Update `write_documents()` signature
- [x] Remove embedding validation code
- [x] Remove deprecation warnings
- [x] Use `self.embedding_model` instead of parameter
- [x] Fix all type hints

### ✅ Step 4: Update Weaviate Backend (COMPLETE)
**File**: `src/db/vector_db_weaviate.py`

- [x] Update `write_documents()` signature
- [x] Update `write_documents_to_collection()` signature
- [x] Remove embedding validation code
- [x] Remove deprecation warnings
- [x] Fix all type hints

### ⏳ Step 5: Update Tests
**Status**: IN PROGRESS

#### 5.1 Unit Tests - Milvus
**File**: `tests/test_vector_db_milvus.py`

Pattern to apply:
```python
# BEFORE:
await db.write_documents(documents, embedding="default")
await db.write_documents(documents, embedding="text-embedding-ada-002")

# AFTER:
await db.write_documents(documents)
```

Occurrences: ~15

#### 5.2 Unit Tests - Weaviate
**File**: `tests/test_vector_db_weaviate.py`

Same pattern as Milvus.
Occurrences: ~12

#### 5.3 Unit Tests - Base
**File**: `tests/test_vector_db_base.py`

Same pattern.
Occurrences: ~8

#### 5.4 Integration Tests
**Files**:
- `tests/test_document_ingestion_integration.py` (~6 occurrences)
- `tests/test_query_functionality.py` (~4 occurrences)

#### 5.5 E2E Tests
**Files**:
- `tests/e2e/test_functions.py` (~12 occurrences)
- `tests/e2e/test_chunking_e2e.py` (~2 occurrences)
- `tests/e2e/test_document_ingestion_e2e.py` (~2 occurrences)

**Note**: E2E test files may be deprecated/unused based on Phase 1 results.

### ⏳ Step 6: Create Phase 2 Validation Tests
**File**: `tests/test_phase2_embedding_removal.py` (NEW)

Tests to create:
```python
@pytest.mark.asyncio
async def test_write_documents_no_embedding_parameter():
    """Verify write_documents doesn't accept embedding parameter."""
    db = MilvusVectorDatabase()
    await db.setup(embedding="text-embedding-3-small")
    
    # Should work without embedding
    result = await db.write_documents([{"url": "test", "text": "test"}])
    assert result is not None

@pytest.mark.asyncio  
async def test_embedding_configured_at_collection_level():
    """Verify embedding is set during setup and used for all writes."""
    db = MilvusVectorDatabase()
    await db.setup(embedding="text-embedding-3-small")
    
    assert db.embedding_model == "text-embedding-3-small"
    
    # Write should use collection-level embedding
    await db.write_documents([{"url": "test", "text": "test"}])

@pytest.mark.asyncio
async def test_collection_info_includes_embedding():
    """Verify collection info returns embedding model."""
    db = MilvusVectorDatabase()
    await db.setup(embedding="text-embedding-3-small")
    
    info = await db.get_collection_info()
    assert info.get("embedding") == "text-embedding-3-small"
```

### ⏳ Step 7: Update Documentation

#### 7.1 Migration Guide
**File**: `docs/MIGRATION_GUIDE.md`

Add Phase 2 section:
```markdown
## Phase 2: Remove Embedding Parameter (COMPLETE)

### Breaking Changes
1. `embedding` parameter removed from:
   - `write_documents`
   - `write_document`
   - `write_document_to_collection`

2. Embedding model must be configured at collection creation

### Migration Steps

**Before (Phase 1):**
```python
await write_documents(database, docs, embedding="text-embedding-ada-002")
```

**After (Phase 2):**
```python
# 1. Configure embedding during setup (once):
await setup_database(database, embedding="text-embedding-ada-002")

# 2. Write without embedding parameter:
await write_documents(database, docs)
```

### Why This Change?

- All documents in a collection must use the same embedding model
- Per-document embedding was confusing and error-prone
- Simpler API with clearer semantics
- Aligns with vector database best practices
```

#### 7.2 Refactoring Plan
**File**: `docs/REFACTORING_PLAN.md`

Update Phase 2 status:
```markdown
## Phase 2: Remove Embedding Parameter (COMPLETE) ✅

**Status**: COMPLETE
**Date**: 2025-01-11

### Changes Made
- Removed `embedding` parameter from all write operations
- Embedding now configured at collection creation time only
- Updated all backends (Milvus, Weaviate)
- Updated all tests
- Created validation tests

### Success Criteria
- [x] No write operations accept `embedding` parameter
- [x] Embedding configured via `setup_database` or `create_collection`
- [x] All tests pass
- [x] Documentation updated
```

#### 7.3 README
**File**: `README.md`

Add section on embedding configuration:
```markdown
## Embedding Model Configuration

Embedding models are configured at collection creation time:

```python
# Configure embedding when creating database
await setup_database("mydb", embedding="text-embedding-3-small")

# Or when creating a collection
await create_collection("mydb", "mycollection", embedding="text-embedding-3-small")

# All subsequent writes use the collection's embedding
await write_documents("mydb", documents)  # No embedding parameter needed
```

### Supported Embedding Models

**Milvus:**
- `default` - Basic embedding
- `text-embedding-ada-002` - OpenAI Ada v2
- `text-embedding-3-small` - OpenAI v3 Small
- `text-embedding-3-large` - OpenAI v3 Large
- `custom_local` - Local embedding server

**Weaviate:**
- `default` - Weaviate's text2vec-weaviate
- `text2vec-openai` - OpenAI embeddings
- `text2vec-huggingface` - HuggingFace models
```

### ⏳ Step 8: Run Full Test Suite

Commands to run:
```bash
# Unit tests
pytest tests/test_vector_db_milvus.py -v
pytest tests/test_vector_db_weaviate.py -v
pytest tests/test_vector_db_base.py -v

# Integration tests
pytest tests/test_document_ingestion_integration.py -v
pytest tests/test_query_functionality.py -v

# Phase 2 validation
pytest tests/test_phase2_embedding_removal.py -v

# Full suite
pytest tests/ -v
```

Expected results:
- All tests pass
- No deprecation warnings about embedding parameter
- Collection-level embedding works correctly

## Implementation Order

1. ✅ Base class updates
2. ✅ MCP server updates
3. ✅ Backend updates (Milvus, Weaviate)
4. ⏳ Test updates (systematic search/replace)
5. ⏳ Validation tests (new file)
6. ⏳ Documentation updates
7. ⏳ Full test suite run

## Search/Replace Patterns for Tests

### Pattern 1: Direct write_documents calls
```python
# Find:
await db.write_documents(documents, embedding="[^"]*")

# Replace:
await db.write_documents(documents)
```

### Pattern 2: write_document calls
```python
# Find:
await db.write_document(document, embedding="[^"]*")

# Replace:
await db.write_document(document)
```

### Pattern 3: Keyword argument style
```python
# Find:
, embedding="[^"]*"

# Replace:
# (empty - just remove)
```

## Validation Checklist

Before marking Phase 2 complete:

- [ ] All backend code updated
- [ ] All test files updated
- [ ] New validation tests created
- [ ] All tests pass
- [ ] No deprecation warnings
- [ ] Documentation updated
- [ ] Migration guide complete
- [ ] README updated with examples

## Breaking Changes Summary

**For API Users:**
- Remove `embedding` parameter from all `write_*` calls
- Configure embedding once during `setup_database` or `create_collection`
- No other changes required

**For Backend Developers:**
- `write_documents()` signature changed
- Use `self.embedding_model` instead of parameter
- Type hints updated to modern Python 3.10+ syntax

## Success Metrics

- ✅ Cleaner API (3 fewer parameters across all write operations)
- ✅ Prevents user errors (can't mix embedding models)
- ✅ Better performance (no per-write embedding lookup)
- ✅ Clearer semantics (embedding is collection property)
- ✅ Reduced token usage in LLM interactions

## Timeline

- **Day 1**: Core implementation (base class, backends) - COMPLETE
- **Day 2**: Test updates and validation - IN PROGRESS
- **Day 3**: Documentation and final verification - PENDING

## Notes

- This implementation is superior to the original plan (which only renamed the parameter)
- User feedback confirmed this architectural approach is correct
- All type checking passes
- Ready for systematic test updates