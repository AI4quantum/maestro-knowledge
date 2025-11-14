l# Timeout Configuration Guide

## Overview

The MCP server implements configurable timeouts for all operations to prevent hanging when the backend is unavailable or slow to respond. This document explains the timeout system and how to configure it.

## Default Timeouts

All operations have sensible defaults based on their expected duration:

| Operation Category | Default Timeout | Environment Variable |
|-------------------|-----------------|---------------------|
| Health checks | 30s | `MCP_TIMEOUT_HEALTH` |
| List operations | 15s | `MCP_TIMEOUT_LIST_DATABASES`, `MCP_TIMEOUT_LIST_COLLECTIONS` |
| Get info operations | 15-30s | `MCP_TIMEOUT_GET_DATABASE_INFO`, `MCP_TIMEOUT_GET_COLLECTION_INFO` |
| Collection creation | 60s | `MCP_TIMEOUT_CREATE_COLLECTION` |
| Database setup | 60s | `MCP_TIMEOUT_SETUP_DATABASE` |
| Document counting | 15s | `MCP_TIMEOUT_COUNT_DOCUMENTS` |
| Document listing | 30s | `MCP_TIMEOUT_LIST_DOCUMENTS` |
| Single document write | 15 min | `MCP_TIMEOUT_WRITE_SINGLE` |
| Bulk document write | 60 min | `MCP_TIMEOUT_WRITE_BULK` |
| Query/Search | 30s | `MCP_TIMEOUT_QUERY`, `MCP_TIMEOUT_SEARCH` |
| Delete operations | 60s | `MCP_TIMEOUT_DELETE` |
| Cleanup | 60s | `MCP_TIMEOUT_CLEANUP` |
| Resync | 60s | `MCP_TIMEOUT_RESYNC` |

## Configuration

### Global Timeout

Set a default timeout for all operations:

```bash
export MCP_TOOL_TIMEOUT=30  # 30 seconds for all operations
```

### Per-Operation Timeouts

Override specific operation timeouts:

```bash
# Increase timeout for collection creation (useful for slow backends)
export MCP_TIMEOUT_CREATE_COLLECTION=120  # 2 minutes

# Increase timeout for bulk writes (useful for large datasets)
export MCP_TIMEOUT_WRITE_BULK=7200  # 2 hours

# Increase timeout for queries (useful for complex searches)
export MCP_TIMEOUT_QUERY=60  # 1 minute
```

### Configuration File

Add to your `.env` file:

```bash
# Global default
MCP_TOOL_TIMEOUT=30

# Operation-specific overrides
MCP_TIMEOUT_CREATE_COLLECTION=120
MCP_TIMEOUT_LIST_COLLECTIONS=30
MCP_TIMEOUT_WRITE_BULK=7200
MCP_TIMEOUT_QUERY=60
```

## Common Scenarios

### Scenario 1: Backend Not Running

**Symptom**: Operations timeout immediately or after 15 seconds

**Solution**: 
1. Check if your vector database is running:
   ```bash
   # Milvus
   curl http://localhost:19530
   
   # Weaviate
   curl http://localhost:8080/v1/.well-known/ready
   ```

2. Start your vector database if needed

3. The `list_collections` tool now provides better error messages:
   - `BACKEND_UNAVAILABLE`: Backend not responding
   - `BACKEND_CONNECTION_FAILED`: Cannot connect to backend
   - `NO_COLLECTIONS`: Backend is running but no collections exist

### Scenario 2: Slow Backend Initialization

**Symptom**: `create_collection` times out after 60 seconds

**Solution**: Increase the timeout:
```bash
export MCP_TIMEOUT_CREATE_COLLECTION=180  # 3 minutes
```

### Scenario 3: Large Bulk Writes

**Symptom**: `write_documents` times out during large imports

**Solution**: Increase bulk write timeout:
```bash
export MCP_TIMEOUT_WRITE_BULK=10800  # 3 hours
```

### Scenario 4: Complex Queries

**Symptom**: Query operations timeout on large collections

**Solution**: Increase query timeout:
```bash
export MCP_TIMEOUT_QUERY=120  # 2 minutes
export MCP_TIMEOUT_SEARCH=120  # 2 minutes
```

## Timeout Error Messages

When an operation times out, you'll receive a structured error response:

```json
{
  "status": "error",
  "error_code": "OPERATION_TIMEOUT",
  "message": "Operation 'create_collection' timed out after 60 seconds",
  "details": {
    "operation": "create_collection",
    "timeout": 60
  },
  "suggestion": "Increase timeout via environment variable: export MCP_TIMEOUT_CREATE_COLLECTION=120"
}
```

The error message includes:
- The operation that timed out
- The timeout duration used
- Troubleshooting steps
- The specific environment variable to adjust

## Backend Health Detection

The `list_collections` tool now performs backend health checks when no collections are registered:

1. **Backend Unavailable**: Returns `BACKEND_UNAVAILABLE` error with connection troubleshooting
2. **Backend Connection Failed**: Returns `BACKEND_CONNECTION_FAILED` with configuration guidance
3. **No Collections**: Returns `NO_COLLECTIONS` with instructions to create a collection

This helps distinguish between:
- Backend not running (connection error)
- Backend running but empty (no collections)
- Backend running with collections (normal operation)

## Best Practices

1. **Start with defaults**: The default timeouts work for most scenarios
2. **Monitor logs**: Check `/tmp/mcp_server.log` for timeout patterns
3. **Adjust incrementally**: Increase timeouts by 2x when needed, not 10x
4. **Consider backend**: Slower backends (network, cloud) need higher timeouts
5. **Test changes**: Verify timeout changes work before committing to `.env`

## Debugging Timeouts

### Check Current Configuration

```bash
# View all timeout-related environment variables
env | grep MCP_TIMEOUT
```

### Enable Debug Logging

```bash
export LOG_LEVEL=debug
export VDB_LOG_LEVEL=debug
```

### Monitor Server Logs

```bash
tail -f /tmp/mcp_server.log
```

### Test Backend Connectivity

```bash
# Milvus
curl -v http://localhost:19530

# Weaviate
curl -v http://localhost:8080/v1/.well-known/ready

# Custom embedding endpoint
curl -X POST http://localhost:11434/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model":"nomic-embed-text","prompt":"test"}'
```

## Implementation Details

### Timeout Mechanism

The server uses `asyncio.wait_for()` with proper task cancellation:

```python
task = asyncio.create_task(operation())
try:
    result = await asyncio.wait_for(task, timeout=timeout_seconds)
except asyncio.TimeoutError:
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass  # Expected
    return timeout_error_response()
```

This ensures:
- Operations are properly cancelled on timeout
- No orphaned tasks or resource leaks
- Clean error messages returned to client

### Timeout Resolution Order

1. Operation-specific environment variable (e.g., `MCP_TIMEOUT_CREATE_COLLECTION`)
2. Global timeout environment variable (`MCP_TOOL_TIMEOUT`)
3. Operation-specific default from `TIMEOUT_DEFAULTS` dict
4. Global default (15 seconds)

## Related Documentation

- [MCP API Reference](MCP_API_REFERENCE.md) - Complete API documentation
- [Testing Guide](TESTING_GUIDE.md) - Testing with different timeout scenarios
- [README](../src/maestro_mcp/README.md) - Server configuration and usage