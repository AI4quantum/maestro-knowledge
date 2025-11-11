# Agent Guide for Maestro Knowledge Development

This guide helps AI agents work effectively on this codebase.

## Quick Reference

### Current Status
**✅ Phases 1-8 COMPLETE** - All refactoring complete! 🎉

**Completed Phases:**
- **Phase 1** ✅: Flat parameters (no 'input' wrapper)
- **Phase 2** ✅: Embedding at collection level only
- **Phase 2.6** ✅: 3-step workflow (register → setup → create_collection)
- **Phase 3** ✅: Reassembly bug fixed (overlap deduplication)
- **Phase 4** ✅: Search quality controls (min_score, metadata_filters)
- **Phase 5** ✅: Improved citations (url, source_citation, score)
- **Phase 6** ✅: Enhanced error messages with actionable guidance
- **Phase 7** ✅: Test suite updated
- **Phase 8** ✅: Documentation updated

**Future Features:** Phases 9-10 (access control) - See `docs/FEATURES_ACCESS_CONTROL.md`

### Essential Documentation
1. **`README.md`** - Project overview and quick start
2. **`docs/MIGRATION_GUIDE.md`** - Complete API reference and migration guide
3. **`docs/REFACTORING_SUMMARY.md`** - Summary of all completed phases
4. **`tests/e2e/README.md`** - E2E testing guide (CRITICAL for testing)
5. **`docs/DESIGN_PRINCIPLES.md`** - LLM-friendly API design principles

## Common Tasks

### Running Tests

#### Unit/Integration Tests (Fast)
```bash
# Run all unit/integration tests
uv run pytest tests/ -v

# Exclude E2E tests (default behavior)
uv run pytest tests/ -v -m "not e2e"

# Run specific test file
uv run pytest tests/test_mcp_query.py -v
```

#### E2E Tests (Requires Services)
**IMPORTANT**: E2E tests require the `-m "e2e"` marker flag!

```bash
# ❌ WRONG - Will select 0 tests:
uv run pytest tests/e2e/test_mcp_milvus_e2e.py -v

# ✅ CORRECT - Includes E2E marker:
uv run pytest tests/e2e/test_mcp_milvus_e2e.py -v -m "e2e"
```

**Full E2E test command with environment:**
```bash
MILVUS_URI=http://localhost:19530 \
CUSTOM_EMBEDDING_URL=http://localhost:11434/api/embeddings \
CUSTOM_EMBEDDING_MODEL=nomic-embed-text \
CUSTOM_EMBEDDING_VECTORSIZE=768 \
E2E_BACKEND=milvus \
E2E_MILVUS=1 \
uv run pytest tests/e2e/test_mcp_milvus_e2e.py -v -m "e2e"
```

**Prerequisites for E2E tests:**
1. Milvus running on port 19530
2. Ollama running on port 11434 with nomic-embed-text model
3. MCP server running on port 8030

See `tests/e2e/README.md` for complete E2E testing guide.

### Starting/Restarting MCP Server

```bash
# Start server (uses uv run python)
./start.sh

# Stop server
pkill -f "maestro_mcp.server"

# Restart server
pkill -f "maestro_mcp.server" && sleep 2 && ./start.sh

# Check if server is running
ps aux | grep maestro_mcp.server

# View server logs
tail -f /tmp/mcp_server.log
```

**Server runs on port 8030 by default**

### Checking Service Status

```bash
# Check Milvus
curl http://localhost:19530

# Check Ollama
curl http://localhost:11434/api/tags

# Check MCP server health
curl http://localhost:8030/health

# Check if embedding model is loaded
curl -X POST http://localhost:11434/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"nomic-embed-text","prompt":"test"}'
```

## Project Structure

```
maestro-knowledge-forllm/
├── src/
│   ├── maestro_mcp/
│   │   └── server.py          # Main MCP server (22 tools)
│   ├── db/                     # Vector DB implementations
│   ├── chunking/               # Text chunking strategies
│   └── converters/             # Document format converters
├── tests/
│   ├── test_*.py              # Unit/integration tests
│   └── e2e/                   # E2E tests (require -m "e2e")
├── docs/
│   ├── REFACTORING_SUMMARY.md # Summary of completed phases
│   ├── MIGRATION_GUIDE.md     # API reference & migration
│   ├── FEATURES_ACCESS_CONTROL.md # Future features (Phases 9-10)
│   └── DESIGN_PRINCIPLES.md   # LLM-friendly API design
├── examples/                   # Usage examples
└── AGENTS.md                   # This file (AI agent guide)
```

## Key Concepts

### MCP Tools (22 total)
All tools now use **flat parameters** (Phase 1 complete):
- Database management: 6 tools
- Collection management: 5 tools  
- Document operations: 9 tools
- Query operations: 2 tools

### Key API Changes

**Phase 1 - Parameter Names:**
- `database` (was `db_name`)
- `database_type` (was `db_type`)
- `collection` (was `collection_name`)
- `document_name` (was `doc_name`)
- No `input` wrapper - all parameters at top level

**Phase 2 - Embedding Architecture:**
- NO `embedding` parameter in write operations
- Embedding configured ONCE at collection creation
- All documents in collection use same embedding model

**Phase 2.6 - 3-Step Workflow:**
```python
# 1. Register database
register_database(database="mydb", database_type="milvus", collection="docs")

# 2. Initialize connection
setup_database(database="mydb", embedding="text-embedding-3-small")

# 3. Create collection
create_collection(database="mydb", collection="docs", embedding="text-embedding-3-small")
```

**Phase 4 - Search Quality:**
- `min_score` parameter (0-1) filters low-quality results
- `metadata_filters` dict filters by document metadata

**Phase 5 - Citations:**
- `url` at top level (not just in metadata)
- `source_citation` ready-to-use citation string
- `score` normalized 0-1 similarity score

See `docs/MIGRATION_GUIDE.md` for complete API reference.

### Testing Strategy
1. **Unit tests**: Fast, no external services
2. **Integration tests**: Test tool functions with mocks
3. **E2E tests**: Full stack with real services (Milvus/Weaviate)

## Common Pitfalls

### 1. E2E Tests Not Running
**Problem**: Running E2E tests without `-m "e2e"` marker
**Solution**: Always use `-m "e2e"` flag for E2E tests

### 2. Server Not Restarting
**Problem**: Old server process still running
**Solution**: Use `pkill -f "maestro_mcp.server"` before starting

### 3. Wrong Parameter Names
**Problem**: Using old parameter names (db_name, db_type, etc.)
**Solution**: Check `docs/MIGRATION_GUIDE.md` for current names

### 4. Missing Environment Variables
**Problem**: E2E tests fail due to missing env vars
**Solution**: Set all required vars (see E2E command above)

### 5. Services Not Running
**Problem**: E2E tests fail because Milvus/Ollama not running
**Solution**: Check service status (see commands above)

## Debugging Tips

### Enable Verbose Logging
```bash
LOG_LEVEL=debug VDB_LOG_LEVEL=debug uv run pytest tests/e2e/ -v -s --tb=long -m "e2e"
```

### Check Test Output
```bash
# Run with output capture disabled
uv run pytest tests/test_file.py -v -s

# Show full traceback
uv run pytest tests/test_file.py -v --tb=long
```

### Verify Tool Schemas
```bash
# Check generated schemas match expectations
uv run pytest tests/test_phase1_schema_validation.py -v
```

## Migration Progress Tracking

### Phase 1-8: ✅ COMPLETE
All refactoring phases complete! See `docs/REFACTORING_SUMMARY.md` for details.

### Future Features: Phases 9-10
See `docs/FEATURES_ACCESS_CONTROL.md` for ownership metadata and access control planning.

## Getting Help

1. **Read the docs first**: Check relevant doc files above
2. **Check test examples**: Look at existing tests for patterns
3. **Review migration guide**: See what changed in Phase 1
4. **Check E2E README**: For testing issues

## Quick Commands Cheat Sheet

```bash
# Run unit tests
uv run pytest tests/ -v -m "not e2e"

# Run E2E tests (with services running)
E2E_MILVUS=1 MILVUS_URI=http://localhost:19530 \
CUSTOM_EMBEDDING_URL=http://localhost:11434/api/embeddings \
CUSTOM_EMBEDDING_MODEL=nomic-embed-text \
CUSTOM_EMBEDDING_VECTORSIZE=768 \
uv run pytest tests/e2e/test_mcp_milvus_e2e.py -v -m "e2e"

# Restart MCP server
pkill -f "maestro_mcp.server" && sleep 2 && ./start.sh

# Check server status
ps aux | grep maestro_mcp.server

# View server logs
tail -f /tmp/mcp_server.log

# Check services
curl http://localhost:19530  # Milvus
curl http://localhost:11434/api/tags  # Ollama
curl http://localhost:8030/health  # MCP server
```

## Notes for Future Agents

- Always check `docs/MIGRATION_GUIDE.md` for current API reference
- E2E tests MUST use `-m "e2e"` marker
- Server must be restarted after code changes to server.py
- Use `uv run python` not just `python` (see start.sh)
- All 8 refactoring phases are complete - see `docs/REFACTORING_SUMMARY.md`
- Future features (Phases 9-10) are in `docs/FEATURES_ACCESS_CONTROL.md`