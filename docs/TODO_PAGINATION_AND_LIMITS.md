# TODO: Pagination and Query Limits

## Overview
This document tracks issues and future improvements related to query limits and pagination in the Maestro Knowledge MCP server.

## Current Issues

### 1. Query Limits Too Low for Document Retrieval
**Status**: 🔴 Critical - Needs immediate fix

**Problem**: 
- `list_documents()` internally queries ALL chunks (limit=16384) to aggregate by document_id
- However, other retrieval operations use much lower limits (e.g., 100)
- This creates inconsistency and can miss documents when collections are large

**Current Limits**:
- `list_documents()` internal query: 16384 chunks → groups by document_id
- Other query operations: varies, some as low as 100

**Impact**:
- In the agent session, only 2 of 4 documents appeared in `list_documents()`
- This was likely due to low internal limits or Milvus query behavior
- Collection shows 12 chunks but only 2 documents returned

**Solution Needed**:
1. **Short-term**: Raise all retrieval limits to 4096+ to match document query pattern
2. **Long-term**: Implement proper pagination (see below)

### 2. Lack of True Pagination
**Status**: 🟡 Enhancement - Medium priority

**Problem**:
- Current pagination is client-side: fetch ALL results, then slice [offset:offset+limit]
- This is inefficient for large collections
- Milvus supports server-side pagination but we're not using it properly

**Example**:
```python
# Current approach (inefficient)
results = await self.client.query(
    collection_name,
    filter="id >= 0",
    output_fields=["url", "metadata"],
    limit=16384,  # Fetch everything
)
# Then slice in memory
return all_docs[offset:offset+limit]
```

**Better Approach**:
```python
# Server-side pagination (not yet implemented)
results = await self.client.query(
    collection_name,
    filter="id >= 0",
    output_fields=["url", "metadata"],
    limit=limit,
    offset=offset  # Let Milvus handle pagination
)
```

**Challenges**:
- Need to group by `document_id` from chunks
- Server-side pagination at chunk level doesn't directly map to document-level pagination
- May need two-phase approach: 
  1. Get unique document_ids (possibly with higher limit)
  2. Paginate at document level

## Proposed Solutions

### Phase 1: Increase Limits (Immediate)
**Priority**: 🔴 High

**Changes Needed**:
1. Review all query operations in `vector_db_milvus.py` and `vector_db_weaviate.py`
2. Standardize internal query limits to 4096+ (matching or exceeding document aggregation needs)
3. Document the reasoning in code comments

**Files to Update**:
- `src/db/vector_db_milvus.py`
- `src/db/vector_db_weaviate.py`
- Search for patterns like `limit=100`, `limit=1000`, etc.

### Phase 2: Implement Proper Pagination (Future)
**Priority**: 🟡 Medium

**Design Considerations**:
1. **Document-level pagination**: 
   - Users want to paginate by documents, not chunks
   - Need to maintain document integrity across pages

2. **Efficient queries**:
   - Avoid fetching all chunks every time
   - Use cursor-based pagination if available
   - Consider caching document_id lists for large collections

3. **API Design**:
   - Current `offset`/`limit` parameters are good
   - Add `total_count` to responses so clients know total available
   - Consider `next_token` style pagination for very large collections

4. **Backward compatibility**:
   - Ensure existing code continues to work
   - Gradual migration path

### Phase 3: Performance Optimization (Future)
**Priority**: 🟢 Low

**Ideas**:
1. **Milvus scalar index on document_id**:
   - Speed up grouping operations
   - See `docs/IMPROVEMENT_DOCUMENT_ID_SCALAR_FIELD.md` for related work

2. **Caching**:
   - Cache document lists for recently-queried collections
   - Invalidate on writes

3. **Streaming results**:
   - For very large collections, support streaming document lists
   - Return results as they're found rather than all at once

## Related Documents
- `docs/IMPROVEMENT_DOCUMENT_ID_SCALAR_FIELD.md` - Document ID scalar field improvements
- `docs/FEATURE_DOCUMENT_IDS.md` - Document ID feature tracking
- `docs/REFACTORING_SUMMARY.md` - Overall refactoring status

## Investigation Notes

### Agent Session Issue (2025-11-14)
**Symptoms**:
- 4 documents written to "nigel" collection
- Only 2 documents returned by `list_documents()`
- Collection metadata shows 12 chunks total (correct)

**Possible Causes**:
1. ✅ Milvus query limit hit (16384 should be enough for 12 chunks though)
2. ❓ Milvus query behavior with filters
3. ❓ Race condition in document aggregation
4. ❓ Metadata corruption or missing document_id fields

**Action Items**:
- [x] Query Milvus directly to verify all 12 chunks exist
- [x] Check if all chunks have valid document_id in metadata (yes, they do)
- [x] Verify document_id generation is deterministic (yes)
- [x] Add debug logging to `list_documents()` to track aggregation (done)
- [x] **ROOT CAUSE FOUND**: `filter="id >= 0"` on primary key returns only 4/12 chunks
- [x] **SOLUTION IMPLEMENTED**: Changed to `filter='url != ""'` (scalar field filter)

**Resolution (2025-11-14)**:
- **ROOT CAUSE FOUND**: Write concurrency bug in Milvus Lite causes data loss
- `insert()` reports success but data doesn't persist due to race conditions
- `get_collection_stats()` shows incorrect counts (metadata corrupted)
- Multiple concurrent writes to Milvus Lite corrupt file-based storage
- **Query code works fine** - it correctly returns all chunks that actually exist
- Changed from `filter="id >= 0"` to `filter='text != ""'` for reliability

**Solution Implemented**:
1. **Write serialization**: Use `asyncio.Lock` to prevent concurrent writes (Milvus Lite only)
2. **Ground-truth verification**: Query by PK after flush, don't trust stats
3. **Explicit reload**: Call `load_collection()` after flush to see new segments
4. **Environment-based config**: `MILVUS_SERIALIZE_WRITES` env var (default: auto-detect)
   - Milvus Lite (file://): Enable serialization
   - Clustered Milvus (http://): Disable serialization (safe for concurrent writes)

## Timeline
- **Phase 1** (Immediate): Raise limits to 4096+
- **Phase 2** (Q1 2025): Design and implement proper pagination
- **Phase 3** (Q2 2025): Performance optimization

## Questions for Investigation
1. What is the actual Milvus query limit in practice? (Docs say 16384 but behavior unclear)
2. Does Milvus support cursor-based pagination?
3. What's the performance impact of querying 16K+ chunks per list operation?
4. Should we add a collection-level document count cache?

---

**Last Updated**: 2025-11-14
**Related Issues**: Agent session showing 2/4 documents
**Priority**: 🔴 High (Phase 1), 🟡 Medium (Phase 2)
