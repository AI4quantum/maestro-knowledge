# Query vs Search Analysis

## Current State

The system has two similar but distinct operations:

### `query` Tool
- **Purpose**: Conversational Q&A interface
- **Returns**: LLM-generated natural language summary (string)
- **Use Case**: End-user questions, chatbots, conversational interfaces
- **Processing**: Vector search → LLM summarization
- **Parameters**: query, limit, collection
- **Limitations**: No metadata filtering, no min_score control

### `search` Tool
- **Purpose**: Programmatic document retrieval
- **Returns**: Raw results with scores, metadata, citations (list)
- **Use Case**: Agents, custom ranking, detailed analysis
- **Processing**: Vector search only (no LLM)
- **Parameters**: query, limit, collection, min_score, metadata_filters
- **Advantages**: Full control over filtering and scoring

## Recommendation: Keep Separate

### Rationale

1. **Different Use Cases**
   - `query`: Human-readable answers ("What is X?")
   - `search`: Structured data for processing ("Find all Python docs")

2. **Performance Characteristics**
   - `query`: Slower (LLM overhead), but more user-friendly
   - `search`: Faster, suitable for batch operations

3. **Return Type Semantics**
   - `query`: Single coherent answer
   - `search`: Multiple ranked results

4. **API Clarity**
   - Clear naming indicates intent
   - Users know what to expect from each

### Proposed Enhancements

#### 1. Add Filtering to `query`
```python
async def query(
    query: str,
    limit: int = 5,
    collection: str | None = None,
    min_score: float | None = None,  # NEW
    metadata_filters: dict[str, Any] | None = None,  # NEW
) -> str:
```

**Benefit**: Allows filtering before LLM summarization, improving answer quality

#### 2. Clarify Documentation
Update docstrings to emphasize:
- `query`: "Use when you want a natural language answer"
- `search`: "Use when you need structured results with scores"

#### 3. Future: Unified Interface (Optional)
If needed, could add a `format` parameter:
```python
async def retrieve(
    query: str,
    format: Literal["summary", "results"] = "results",
    ...
) -> str | list[dict]:
```

But this adds complexity without clear benefit given current use cases.

## Metadata Filtering Enhancement

### Current State
- `list_documents`: Has `name_filter` and `url_filter` only
- `search`: Has arbitrary `metadata_filters`

### Recommendation: Add to `list_documents`

```python
async def list_documents(
    collection: str,
    name_filter: str | None = None,  # Keep for convenience
    url_filter: str | None = None,   # Keep for convenience
    metadata_filters: dict[str, Any] | None = None,  # NEW
) -> str:
```

**Logic**: Apply ALL filters (name AND url AND metadata)

**Benefits**:
1. Consistency with `search` API
2. Supports custom metadata fields
3. Enables complex document discovery workflows

## Implementation Priority

1. **High**: Add `metadata_filters` to `list_documents`
2. **Medium**: Add `min_score` and `metadata_filters` to `query`
3. **Low**: Consider unified interface (only if user demand exists)

## Conclusion

Keep `query` and `search` as separate tools with distinct purposes. Enhance both with consistent filtering capabilities while maintaining their core differences in return types and processing.