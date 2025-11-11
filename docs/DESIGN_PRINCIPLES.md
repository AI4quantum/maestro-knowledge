# Design Principles for LLM-Friendly APIs

**Source**: Extracted from original AGENT_FRIENDLY.md proposal
**Status**: Living document - principles guide ongoing development

## Core Principles

### 1. Flat Parameter Structures ✅ IMPLEMENTED

**Principle**: LLM agents expect flat parameter structures, not nested objects.

**Why**: 
- FastMCP and similar frameworks validate schemas before execution
- Agents can't work around nested structures at runtime
- Flat structures are more intuitive for natural language → API translation

**Implementation**: Phase 1 removed all `input` wrappers

**Example**:
```python
# ❌ Nested (breaks agents)
{"input": {"database": "mydb", "query": "search"}}

# ✅ Flat (works with agents)
{"database": "mydb", "query": "search"}
```

### 2. Clear, Consistent Parameter Names ✅ IMPLEMENTED

**Principle**: Use full, descriptive names that agents won't misinterpret.

**Why**:
- Agents guess parameter names from natural language
- Abbreviations cause confusion (db_name → name? database_name?)
- Consistency across similar parameters reduces errors

**Implementation**: Phase 1 renamed parameters

**Guidelines**:
- Use `database` not `db_name` or `db`
- Use `collection` not `collection_name` or `coll`
- Use `document_name` not `doc_name` or `name`
- Be consistent: if one tool uses `database`, all tools use `database`

### 3. Configuration at Creation Time ✅ IMPLEMENTED

**Principle**: Configure resources once at creation, not per-operation.

**Why**:
- Reduces cognitive load for agents
- Prevents configuration drift
- Enforces consistency (e.g., all docs in collection use same embedding)
- Fewer parameters = fewer errors

**Implementation**: Phase 2 moved embedding to collection creation

**Example**:
```python
# ✅ Configure once
create_collection(database="mydb", collection="docs", embedding="text-embedding-3-small")

# ✅ Use without reconfiguration
write_documents(database="mydb", documents=[...])  # Uses collection's embedding
```

### 4. Quality Controls for Search ✅ IMPLEMENTED

**Principle**: Provide filters to improve result quality and relevance.

**Why**:
- Raw similarity scores include low-quality matches
- Agents need to filter by document properties
- Better results = fewer hallucinations

**Implementation**: Phase 4 added min_score and metadata_filters

**Guidelines**:
- `min_score`: Filter by similarity threshold (0-1)
- `metadata_filters`: Filter by document properties
- Both optional (backward compatible)
- Applied at database level (efficient)

### 5. LLM-Friendly Citations ✅ IMPLEMENTED

**Principle**: Make source attribution easy for LLMs to extract and use.

**Why**:
- URLs buried in metadata are hard to find
- Technical metadata (offsets, chunk numbers) adds noise
- Ready-to-use citations reduce hallucination risk

**Implementation**: Phase 5 added top-level url and source_citation

**Format**:
```python
{
    "text": "Content...",
    "url": "https://example.com/doc",  # Top-level, easy to find
    "source_citation": "Source: Doc Name (https://example.com/doc)",  # Ready to use
    "score": 0.85,  # Normalized similarity
    "metadata": {...}  # Additional context
}
```

### 6. Actionable Error Messages ✅ IMPLEMENTED

**Principle**: Errors should tell agents what went wrong AND how to fix it.

**Why**:
- Generic errors don't help agents recover
- Agents need available options and next steps
- Good errors reduce retry loops

**Implementation**: Phase 6 created error_messages.py module

**Format**:
```
[What went wrong]

[Current state / Available options]

[How to fix it - specific steps]
```

**Example**:
```
Database 'mydb' not found.

Available databases: 'docs', 'knowledge', 'support'

To create a new database:
1. Register: register_database(database="mydb", database_type="milvus")
2. Initialize: setup_database(database="mydb", embedding="default")
3. Create collection: create_collection(database="mydb", collection="default")
```

### 7. Explicit Multi-Step Workflows ✅ IMPLEMENTED

**Principle**: Break complex operations into clear, sequential steps.

**Why**:
- Agents understand step-by-step better than implicit operations
- Each step can be verified before proceeding
- Clearer error recovery (know which step failed)

**Implementation**: Phase 2.6 separated setup into 3 steps

**Pattern**:
```python
# Step 1: Register (create registry entry)
register_database(database="mydb", database_type="milvus", collection="docs")

# Step 2: Initialize (connect and configure)
setup_database(database="mydb", embedding="text-embedding-3-small")

# Step 3: Create resources (make collection)
create_collection(database="mydb", collection="docs", embedding="text-embedding-3-small")
```

### 8. Backward Compatibility Through Defaults

**Principle**: New features should be additive with sensible defaults.

**Why**:
- Existing code continues to work
- Users can adopt features gradually
- Reduces migration friction

**Implementation**: All Phase 4-6 features are optional

**Guidelines**:
- New parameters should be optional
- Defaults should match previous behavior
- Breaking changes only when necessary (Phases 1-2)

## Design Decisions

### Decision: Breaking Changes vs Dual-Port

**Original Proposal**: Dual-port architecture (8030 legacy, 8031 new)

**Actual Implementation**: Breaking changes with migration guide

**Rationale**:
- Simpler architecture (one server, not two)
- Clearer migration path (update or don't)
- Less maintenance burden
- Users had time to migrate (phases rolled out over time)

**Trade-off**: Required user migration vs automatic compatibility

### Decision: Embedding at Collection Level

**Principle**: All documents in a collection must use the same embedding model.

**Rationale**:
- Technical requirement for vector search
- Prevents user errors (mixing embeddings)
- Simpler API (configure once)
- Better performance (no per-write lookup)

### Decision: Flat Parameters Only

**Principle**: No nested structures in tool parameters.

**Rationale**:
- FastMCP validates before execution (can't transform at runtime)
- Agents expect flat structures
- Simpler for humans too
- Industry standard (most APIs use flat params)

## Future Considerations

### Access Control (Phases 9-10)

**Principle**: Security should be explicit but optional.

**Planned Approach**:
- `owner` parameter for tracking
- `visibility` for access control
- `user` parameter for filtering
- Default to open (backward compatible)

See `docs/FEATURES_ACCESS_CONTROL.md` for details.

### Additional Quality Controls

**Potential Features**:
- Reranking by relevance
- Diversity filtering (avoid duplicate results)
- Temporal filtering (recent documents only)
- Language filtering

**Principle**: Add as optional parameters, maintain backward compatibility

## Testing Principles

### For LLM-Friendly Features

1. **Test with actual agents** - Not just unit tests
2. **Test error recovery** - Agents should be able to fix errors
3. **Test parameter guessing** - Common mistakes should fail clearly
4. **Test incremental adoption** - New features shouldn't break old code

### Error Message Testing

1. **Verify actionability** - Can agent recover from error?
2. **Verify completeness** - Are all options listed?
3. **Verify clarity** - Is the fix obvious?

## References

- Original proposal: AGENT_FRIENDLY.md (historical)
- Implementation: docs/REFACTORING_PLAN.md
- Migration guide: docs/MIGRATION_GUIDE.md
- Access control: docs/FEATURES_ACCESS_CONTROL.md