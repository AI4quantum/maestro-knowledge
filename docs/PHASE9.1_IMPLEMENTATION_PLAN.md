# Phase 9.1 Implementation Plan: Tool Consolidation

## Overview
Reduce tools from 22 → 14 by consolidating related operations.

## Tool Changes Summary

### Database Management (6 → 5 tools)
1. **register_database** → **create_database** (rename + merge setup_database)
2. ~~setup_database~~ → MERGED into create_database
3. **get_database_info** → KEEP (merge get_supported_embeddings)
4. **list_databases** → KEEP
5. **cleanup** → **delete_database** (rename)
6. **resync_databases_tool** → **refresh_databases** (rename)
7. ~~get_supported_embeddings~~ → MERGED into get_database_info

### Collection Management (5 → 4 tools)
1. **create_collection** → KEEP (merge get_supported_chunking_strategies)
2. **list_collections** → KEEP (merge list_documents variants)
3. **get_collection_info** → KEEP (merge count_documents)
4. **delete_collection** → KEEP
5. ~~count_documents~~ → MERGED into get_collection_info
6. ~~get_supported_chunking_strategies~~ → MERGED into create_collection

### Document Operations (9 → 3 tools)
1. **write_documents** → KEEP (merge write_document, write_document_to_collection)
2. ~~write_document~~ → MERGED into write_documents
3. ~~write_document_to_collection~~ → MERGED into write_documents
4. ~~list_documents~~ → MERGED into list_collections
5. ~~list_documents_in_collection~~ → MERGED into list_collections
6. **get_document** → KEEP
7. **delete_documents** → KEEP (merge delete_document, delete_document_from_collection)
8. ~~delete_document~~ → MERGED into delete_documents
9. ~~delete_document_from_collection~~ → MERGED into delete_documents

### Query Operations (2 → 2 tools)
1. **query** → KEEP
2. **search** → KEEP

## Implementation Steps

### Step 1: Rename Tools (No Logic Changes)
- register_database → create_database
- cleanup → delete_database  
- resync_databases_tool → refresh_databases

### Step 2: Merge Database Tools
- Merge setup_database into create_database
- Merge get_supported_embeddings into get_database_info

### Step 3: Merge Collection Tools
- Merge count_documents into get_collection_info
- Merge get_supported_chunking_strategies into create_collection
- Add include_documents parameter to list_collections

### Step 4: Merge Document Tools
- Merge write_document + write_document_to_collection into write_documents
- Merge delete_document + delete_document_from_collection into delete_documents
- Remove list_documents and list_documents_in_collection

### Step 5: Test After Each Step
Run tests after each major change to catch issues early.

## Testing Strategy

After each step:
```bash
uv run pytest tests/test_integration_mcp_server.py -v
```

After all changes:
```bash
uv run pytest tests/ -v -m "not e2e"
```

## Rollback Plan

If issues arise:
1. Git stash changes
2. Review error messages
3. Fix incrementally
4. Re-test

## Success Criteria

- [ ] Tool count reduced from 22 to 14
- [ ] All integration tests pass
- [ ] No functional regressions
- [ ] Server starts successfully