# Phase 9.1 Progress: Tool Consolidation

## Step 1: Rename Tools ✅ COMPLETE

### Changes Made
1. **register_database → create_database**
   - File: `src/maestro_mcp/server.py` line 459
   - Updated docstring to "Create and initialize..."
   
2. **cleanup → delete_database**
   - File: `src/maestro_mcp/server.py` line 1452
   - Updated docstring to "Delete a vector database..."
   
3. **resync_databases_tool → refresh_databases**
   - File: `src/maestro_mcp/server.py` line 1838
   - Updated docstring to include Weaviate

### Test Updates
Updated test files to use new tool names:
- `tests/test_phase26_workflow.py` - All references to `register_database` → `create_database`
- `tests/e2e/test_functions.py` - `resync_databases_tool` → `refresh_databases`
- `tests/e2e/test_mcp_weaviate_simple.py` - `resync_databases_tool` → `refresh_databases`
- `tests/e2e/test_functions_simple.py` - `resync_databases_tool` → `refresh_databases`
- `tests/test_phase1_schema_validation.py` - `resync_databases_tool` → `refresh_databases`

### Testing Status
**Ready for testing**: Please run:
```bash
uv run pytest tests/test_phase26_workflow.py -v
```

## Next Steps

### Step 2: Remove setup_database (READY)
- Tool is already marked DEPRECATED
- Logic already merged into create_database
- Just need to delete the function

### Step 3: Merge get_supported_embeddings into get_database_info
### Step 4: Merge count_documents into get_collection_info
### Step 5: Merge write_document variants into write_documents
### Step 6: Merge delete_document variants into delete_documents
### Step 7: Remove list_documents variants, enhance list_collections
### Step 8: Merge get_supported_chunking_strategies into create_collection

## Tool Count Progress
- **Starting**: 24 tools
- **After Step 1**: 24 tools (renames only, no removals yet)
- **Target**: 14 tools
- **Remaining**: 10 tools to remove/merge