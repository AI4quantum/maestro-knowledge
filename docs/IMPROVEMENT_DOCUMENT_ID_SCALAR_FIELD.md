# Improvement: Add document_id as Scalar Field

## Problem
Currently, `document_id` is embedded in the `metadata` VARCHAR field as a JSON string:
```json
{"document_id": "abc123", "doc_name": "...", ...}
```

This causes several issues:
1. **Inefficient filtering**: LIKE pattern matching on VARCHAR requires full collection scans
2. **Two-step deletion**: `delete()` doesn't support LIKE filters, requiring query-then-delete
3. **Poor performance**: No indexing possible on JSON string contents
4. **Complex syntax**: Awkward filter expressions with escaped quotes

## Solution
Add `document_id` as a separate scalar field in the schema.

### Schema Changes

**Current schema:**
- `id` (INT64, primary key)
- `url` (VARCHAR)
- `text` (VARCHAR)
- `metadata` (VARCHAR - JSON string)
- `vector` (FLOAT_VECTOR)

**Proposed schema:**
- `id` (INT64, primary key)
- `document_id` (VARCHAR, max_length=64, **indexed**)  ← NEW
- `url` (VARCHAR)
- `text` (VARCHAR)
- `metadata` (VARCHAR - JSON string, still contains document_id for compatibility)
- `vector` (FLOAT_VECTOR)

### Implementation Steps

#### 1. Update `create_collection()`
```python
await self.client.create_collection(
    collection_name=collection_name,
    dimension=dimension,
    primary_field_name="id",
    vector_field_name="vector",
    # Add document_id field definition
    schema=MilvusSchema([
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="url", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dimension),
    ])
)

# Create index on document_id for fast filtering
await self.client.create_index(
    collection_name,
    "document_id",
    index_params={"index_type": "INVERTED"}  # or "marisa-trie" for string keys
)
```

#### 2. Update `write_documents()`
```python
# When inserting chunks, include document_id as top-level field
data.append({
    "id": id_counter,
    "document_id": document_id,  # ← NEW: Top-level field
    "url": doc.get("url", ""),
    "text": chunk_text_content,
    "metadata": json.dumps(new_meta, ensure_ascii=False),  # Still includes document_id
    "vector": doc_vector,
})
```

#### 3. Update `get_document_chunks()`
```python
# OLD (slow LIKE filter):
filter=f'metadata LIKE \'%"document_id": "{document_id}"%\''

# NEW (fast indexed filter):
filter=f'document_id == "{document_id}"'
```

#### 4. Update `delete_documents()`
```python
# OLD (two-step query-then-delete):
query_expr = f'metadata LIKE \'%"document_id": "{doc_id}"%\''
results = await self.client.query(...)
ids_to_delete = [item['id'] for item in results]
delete_expr = f"id in {ids_to_delete}"

# NEW (single-step direct delete):
await self.client.delete(
    collection_name=self.collection_name,
    filter=f'document_id == "{doc_id}"'
)
```

#### 5. Update `list_documents()`
```python
# Aggregation logic remains the same, but can optionally use document_id field
# for faster grouping if needed
```

### Benefits

1. **10-100x faster filtering**: Indexed scalar field vs VARCHAR LIKE scan
2. **Simpler code**: Single-step deletion instead of query-then-delete
3. **Better scalability**: Performs well with millions of chunks
4. **Cleaner syntax**: `document_id == "abc"` vs `metadata LIKE '%"document_id": "abc"%'`

### Migration Strategy

**For new collections:**
- Implement immediately - breaking change is acceptable for new collections

**For existing collections:**
- Option A: Drop and recreate (data loss)
- Option B: Create new collection, copy data with new field
- Option C: Keep old collections as-is, only new ones use new schema

### Testing Checklist

- [ ] Create collection with new schema
- [ ] Write documents and verify document_id field is populated
- [ ] Test get_document() with new filter
- [ ] Test delete_documents() with single-step deletion
- [ ] Test list_documents() aggregation still works
- [ ] Benchmark performance improvement (query and delete times)
- [ ] Update E2E tests for new schema

### Estimated Impact

- **Development time**: 4-6 hours
- **Testing time**: 2-3 hours
- **Performance improvement**: 10-100x for filtered operations
- **Breaking change**: Yes (requires collection recreation)

## Related Issues

- Original issue: `list_documents()` returning 0 results (fixed with `id >= 0` filter)
- Delete not working: Required two-step workaround (this improvement eliminates need)
- Performance concerns: Addressed by indexed scalar field

## References

- Milvus documentation on scalar field indexing
- Milvus INVERTED index for VARCHAR fields
- `docs/DESIGN_PRINCIPLES.md` - LLM-friendly API design
