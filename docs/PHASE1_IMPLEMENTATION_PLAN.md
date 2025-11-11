# Phase 1 Implementation Plan: Remove 'input' Wrapper

## Overview
This document provides a detailed implementation plan for Phase 1 of the Maestro Knowledge refactoring, which removes the nested 'input' wrapper from MCP tool schemas to enable LLM agent compatibility.

## Problem Statement
FastMCP currently generates nested schemas like `{"input": {"database": "x"}}`, but LLM agents expect flat schemas like `{"database": "x"}`. This causes 100% failure rate for agent interactions.

## Success Criteria
- [ ] All 21 Input model classes removed from server.py
- [ ] All 24 tool functions refactored to use flat parameters
- [ ] MCP schema generation produces flat parameter structures
- [ ] All existing tests pass with updated parameter structure
- [ ] E2E tests updated to use flat parameters
- [ ] Schema validation tests added

## Implementation Strategy

### Step 1: Inventory and Analysis

#### Input Model Classes to Remove (21 classes)
Located in `src/maestro_mcp/server.py` lines 398-593:

1. `CreateVectorDatabaseInput` (lines 398-409)
2. `SetupDatabaseInput` (lines 412-418)
3. `GetSupportedEmbeddingsInput` (lines 421-422)
4. `WriteDocumentsInput` (lines 425-451)
5. `WriteDocumentInput` (lines 454-469)
6. `WriteDocumentToCollectionInput` (lines 472-489)
7. `ListDocumentsInput` (lines 492-495)
8. `ListDocumentsInCollectionInput` (lines 498-504)
9. `CountDocumentsInput` (lines 507-508)
10. `DeleteDocumentsInput` (lines 511-513)
11. `DeleteDocumentInput` (lines 516-518)
12. `DeleteDocumentFromCollectionInput` (lines 521-526)
13. `GetDocumentInput` (lines 529-534)
14. `DeleteCollectionInput` (lines 537-541)
15. `CleanupInput` (lines 544-547)
16. `GetDatabaseInfoInput` (lines 550-551)
17. `ListCollectionsInput` (lines 554-555)
18. `GetCollectionInfoInput` (lines 558-563)
19. `CreateCollectionInput` (lines 566-575)
20. `QueryInput` (lines 578-584)
21. `SearchInput` (lines 587-593)

#### Tool Functions to Refactor (24 functions)

| # | Function Name | Line | Input Class | Parameters |
|---|---------------|------|-------------|------------|
| 1 | `create_vector_database_tool` | 654 | CreateVectorDatabaseInput | db_name, db_type, collection_name |
| 2 | `setup_database` | 686 | SetupDatabaseInput | db_name, embedding |
| 3 | `get_supported_embeddings` | 721 | GetSupportedEmbeddingsInput | db_name |
| 4 | `get_supported_chunking_strategies` | 729 | None | (no params) |
| 5 | `write_documents` | 785 | WriteDocumentsInput | db_name, documents, embedding |
| 6 | `write_document` | 913 | WriteDocumentInput | db_name, url, text, metadata, vector, embedding |
| 7 | `write_document_to_collection` | 1016 | WriteDocumentToCollectionInput | db_name, collection_name, doc_name, text, url, metadata, vector, embedding |
| 8 | `list_documents` | 1118 | ListDocumentsInput | db_name, limit, offset |
| 9 | `list_documents_in_collection` | 1135 | ListDocumentsInCollectionInput | db_name, collection_name, limit, offset |
| 10 | `count_documents` | 1172 | CountDocumentsInput | db_name |
| 11 | `delete_documents` | 1183 | DeleteDocumentsInput | db_name, document_ids |
| 12 | `delete_document` | 1195 | DeleteDocumentInput | db_name, document_id |
| 13 | `delete_document_from_collection` | 1207 | DeleteDocumentFromCollectionInput | db_name, collection_name, doc_name |
| 14 | `get_document` | 1268 | GetDocumentInput | db_name, collection_name, doc_name |
| 15 | `delete_collection` | 1304 | DeleteCollectionInput | db_name, collection_name |
| 16 | `cleanup` | 1356 | CleanupInput | db_name |
| 17 | `get_database_info` | 1385 | GetDatabaseInfoInput | db_name |
| 18 | `list_collections` | 1404 | ListCollectionsInput | db_name |
| 19 | `get_collection_info` | 1420 | GetCollectionInfoInput | db_name, collection_name |
| 20 | `create_collection` | 1447 | CreateCollectionInput | db_name, collection_name, embedding, chunking_config |
| 21 | `query` | 1530 | QueryInput | db_name, query, limit, collection_name |
| 22 | `search` | 1550 | SearchInput | db_name, query, limit, collection_name |
| 23 | `list_databases` | 1570 | None | (no params) |
| 24 | `resync_databases_tool` | 1601 | None | (no params) |

### Step 2: Parameter Naming Convention

Following Phase 2 naming conventions (for consistency):

| Current Name | New Name | Rationale |
|--------------|----------|-----------|
| `db_name` | `database` | More intuitive for LLMs |
| `db_type` | `database_type` | Clearer meaning |
| `collection_name` | `collection` | Shorter, clearer |
| `doc_name` | `document_name` | More explicit |
| `document_ids` | `document_ids` | Keep as-is (already clear) |
| `document_id` | `document_id` | Keep as-is (already clear) |

### Step 3: Refactoring Template

#### Before (Current Structure)
```python
class CreateVectorDatabaseInput(BaseModel):
    db_name: str = Field(..., description="Unique name for the vector database instance")
    db_type: str = Field(..., description="Type of vector database to create")
    collection_name: str = Field(default="MaestroDocs", description="Name of the collection to use")

@app.tool()
async def create_vector_database_tool(input: CreateVectorDatabaseInput) -> str:
    """Create a new vector database instance."""
    logger.info(f"Creating vector database: {input.db_name} of type {input.db_type}")
    # ... rest of implementation using input.field_name
```

#### After (Flat Structure)
```python
@app.tool()
async def create_vector_database_tool(
    database: str = Field(..., description="Unique name for the vector database instance"),
    database_type: str = Field(..., description="Type of vector database to create", json_schema_extra={"enum": ["weaviate", "milvus"]}),
    collection: str = Field(default="MaestroDocs", description="Name of the collection to use")
) -> str:
    """Create a new vector database instance."""
    logger.info(f"Creating vector database: {database} of type {database_type}")
    # ... rest of implementation using direct parameters
```

### Step 4: Detailed Refactoring Plan

#### 4.1 Create Backup Branch
```bash
git checkout -b phase1-remove-input-wrapper
git push -u origin phase1-remove-input-wrapper
```

#### 4.2 Refactor Each Tool Function

For each of the 24 tool functions:

1. **Extract Field definitions** from Input class
2. **Add parameters** directly to function signature
3. **Update function body** to use direct parameters instead of `input.field_name`
4. **Preserve all Field attributes** (description, default, json_schema_extra)
5. **Keep docstrings** intact

#### 4.3 Remove Input Classes

After all tool functions are refactored:
- Delete lines 398-593 in `src/maestro_mcp/server.py`
- Remove unused `BaseModel` import if no longer needed

### Step 5: Test Strategy

#### 5.1 Schema Validation Tests

Create `tests/test_phase1_schema_validation.py`:

```python
"""Test that MCP schemas are flat (no 'input' wrapper)."""
import pytest
from src.maestro_mcp.server import create_mcp_server

@pytest.mark.asyncio
async def test_flat_schema_structure():
    """Verify all tool schemas use flat parameters."""
    server = await create_mcp_server()
    
    # Test a sample of tools
    tools_to_test = [
        "create_vector_database_tool",
        "write_documents",
        "query",
        "search"
    ]
    
    for tool_name in tools_to_test:
        schema = server.get_tool_schema(tool_name)
        
        # Assert no 'input' wrapper
        assert "input" not in schema.get("parameters", {}), \
            f"Tool {tool_name} has nested 'input' wrapper"
        
        # Assert expected parameters are at top level
        params = schema.get("parameters", {})
        assert len(params) > 0, f"Tool {tool_name} has no parameters"

@pytest.mark.asyncio
async def test_create_vector_database_schema():
    """Test create_vector_database_tool has correct flat schema."""
    server = await create_mcp_server()
    schema = server.get_tool_schema("create_vector_database_tool")
    
    params = schema.get("parameters", {})
    assert "database" in params
    assert "database_type" in params
    assert "collection" in params
    assert "input" not in params
```

#### 5.2 Update E2E Tests

Files to update:
- `tests/e2e/test_functions_simple.py`
- `tests/e2e/test_functions.py`
- `tests/e2e/test_mcp_milvus_e2e.py`
- `tests/e2e/test_mcp_weaviate_e2e.py`

Change from:
```python
res = await client.call_tool(
    "create_vector_database_tool",
    {"input": {"db_name": db_name, "db_type": "milvus"}}
)
```

To:
```python
res = await client.call_tool(
    "create_vector_database_tool",
    {"database": db_name, "database_type": "milvus"}
)
```

#### 5.3 Run Test Suite

```bash
# Run unit tests
pytest tests/test_mcp_server.py -v

# Run schema validation tests
pytest tests/test_phase1_schema_validation.py -v

# Run E2E tests
pytest tests/e2e/ -v

# Run full test suite
pytest tests/ -v
```

### Step 6: Implementation Order

Execute refactoring in this order to minimize risk:

1. **Simple tools first** (no parameters or single parameter)
   - `get_supported_chunking_strategies` (no params)
   - `list_databases` (no params)
   - `resync_databases_tool` (no params)
   - `count_documents` (1 param)
   - `get_supported_embeddings` (1 param)

2. **Medium complexity** (2-3 parameters)
   - `setup_database`
   - `list_documents`
   - `delete_document`
   - `cleanup`

3. **Complex tools** (4+ parameters)
   - `create_vector_database_tool`
   - `write_document`
   - `write_document_to_collection`
   - `create_collection`

4. **Query/Search tools** (critical functionality)
   - `query`
   - `search`

### Step 7: Validation Checklist

After each tool refactoring:
- [ ] Function signature has flat parameters
- [ ] All Field() descriptors preserved
- [ ] Function body uses direct parameters
- [ ] No references to `input.field_name`
- [ ] Docstring intact
- [ ] Type hints correct

After all refactoring:
- [ ] All Input classes removed
- [ ] No compilation errors
- [ ] Schema validation tests pass
- [ ] E2E tests updated and passing
- [ ] Manual testing with MCP client

### Step 8: Risk Mitigation

#### Risk: Breaking Changes
**Mitigation**: 
- Work in feature branch
- Test each function individually
- Keep comprehensive test coverage
- Document all changes

#### Risk: Missed References
**Mitigation**:
- Search for `input.` pattern after refactoring
- Use IDE refactoring tools
- Run full test suite

#### Risk: Schema Generation Issues
**Mitigation**:
- Add schema validation tests early
- Test with actual MCP client
- Verify with LLM agent integration

### Step 9: Documentation Updates

Files to update:
- `docs/REFACTORING_PLAN.md` - Mark Phase 1 complete
- `src/maestro_mcp/README.md` - Update examples
- `examples/mcp_example.py` - Update tool calls
- Create `docs/PHASE1_MIGRATION_GUIDE.md`

### Step 10: Completion Criteria

Phase 1 is complete when:
- [ ] All 21 Input classes removed
- [ ] All 24 tool functions use flat parameters
- [ ] Schema validation tests pass
- [ ] All existing tests pass
- [ ] E2E tests updated and passing
- [ ] Documentation updated
- [ ] Code reviewed and approved
- [ ] Merged to main branch

## Timeline

- **Day 1**: Refactor simple tools (1-3 params) + tests
- **Day 2**: Refactor medium complexity tools + tests
- **Day 3**: Refactor complex tools + query/search + tests
- **Day 4**: E2E test updates + documentation + review
- **Day 5**: Final testing + merge

## Next Steps

After Phase 1 completion:
1. Review Phase 2 plan (parameter renaming)
2. Consider combining Phase 1 & 2 if beneficial
3. Proceed with Phase 3 (reassembly bug fix)