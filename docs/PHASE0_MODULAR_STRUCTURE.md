# Phase 0: Modular Server Structure

## Goal
Split `server.py` (1940 lines) into logical modules with NO functional changes.
This makes Phase 9 refactoring more manageable and token-efficient.

## Proposed Structure

```
src/maestro_mcp/
├── server.py                 # Main entry point (~200 lines)
├── config.py                 # Configuration & environment (~50 lines)
├── database_manager.py       # Database registry & sync (~150 lines)
├── response_formatter.py     # JSON response formatting (~100 lines)
├── tools/
│   ├── __init__.py
│   ├── database_tools.py     # Database management tools (~400 lines)
│   ├── collection_tools.py   # Collection management tools (~300 lines)
│   ├── document_tools.py     # Document operations tools (~600 lines)
│   └── query_tools.py        # Query/search tools (~200 lines)
└── error_messages.py         # Already exists
```

## Module Breakdown

### 1. `config.py`
- Environment variable loading
- Timeout configuration
- Constants (DEFAULT_TOOL_TIMEOUT, TIMEOUT_DEFAULTS)
- `load_env_file()`, `get_timeout()`

### 2. `database_manager.py`
- `vector_databases` dict
- `get_database_by_name()`
- `resync_milvus_databases()`
- `resync_weaviate_databases()`
- Database lifecycle management

### 3. `response_formatter.py`
- Standard JSON response format helpers
- `success_response()`, `error_response()`
- Response validation
- (Prepared for Phase 9.3)

### 4. `tools/database_tools.py`
Tools:
- register_database
- setup_database
- get_database_info
- list_databases
- cleanup
- resync_databases_tool
- get_supported_embeddings

### 5. `tools/collection_tools.py`
Tools:
- create_collection
- list_collections
- get_collection_info
- delete_collection
- count_documents
- get_supported_chunking_strategies

### 6. `tools/document_tools.py`
Tools:
- write_documents
- write_document
- write_document_to_collection
- list_documents
- list_documents_in_collection
- get_document
- delete_documents
- delete_document
- delete_document_from_collection

### 7. `tools/query_tools.py`
Tools:
- query
- search

### 8. `server.py` (main)
- FastMCP app creation
- Health check endpoint
- Tool registration (imports from tools/)
- Server startup

## Implementation Steps

1. Create new module files with extracted code
2. Update imports in server.py
3. Register tools from modules
4. Run tests to verify no functional changes
5. Commit as "Phase 0: Modularize server structure"

## Benefits

1. **Token Efficiency**: Edit only relevant modules during Phase 9
2. **Maintainability**: Logical separation of concerns
3. **Testability**: Can test modules independently
4. **Readability**: Easier to understand and navigate
5. **Future-proof**: Easier to add new tools or features

## Testing Strategy

After modularization:
```bash
# Run all tests to ensure no breakage
uv run pytest tests/ -v -m "not e2e"

# Run integration tests
uv run pytest tests/test_integration_mcp_server.py -v

# Verify server starts
./start.sh
curl http://localhost:8030/health
```

## Success Criteria

- [ ] All tests pass
- [ ] Server starts without errors
- [ ] Health check responds
- [ ] No functional changes (behavior identical)
- [ ] Code is more maintainable