# Phase 9.3 Test Update Guide

## Overview
All 14 MCP tools now return standardized JSON responses. Tests need updating to parse and validate JSON instead of plain text.

## Standard JSON Response Format

### Success Response
```json
{
  "status": "success",
  "message": "Human-readable summary",
  "data": {
    // Tool-specific data
  },
  "metadata": {
    "timestamp": "2025-01-12T12:00:00Z",
    "operation": "tool_name",
    "database": "mydb",
    "collection": "docs"
  }
}
```

### Error Response
```json
{
  "status": "error",
  "error_code": "DB_NOT_FOUND",
  "message": "Database 'mydb' not found",
  "details": {
    "database": "mydb",
    "available_databases": ["other_db"]
  },
  "suggestion": "Create the database first: create_database(...)"
}
```

## Test Update Pattern

### Before (Plain Text)
```python
result = await tool_function(database="mydb")
assert "Successfully created" in result
assert "mydb" in result
```

### After (JSON)
```python
import json

result = await tool_function(database="mydb")
response = json.loads(result)

assert response["status"] == "success"
assert "created" in response["message"].lower()
assert response["data"]["database"] == "mydb"
assert response["metadata"]["operation"] == "create_database"
```

## Tool-Specific Test Updates

### 1. Database Tools

#### create_database
```python
result = await create_database(database="mydb", database_type="milvus")
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["database"] == "mydb"
assert response["data"]["database_type"] == "milvus"
assert response["data"]["connection_status"] == "connected"
assert response["data"]["collections_count"] == 0
```

#### delete_database
```python
# Test without force (should fail if not empty)
result = await delete_database(database="mydb", force=False)
response = json.loads(result)

if has_collections:
    assert response["status"] == "error"
    assert response["error_code"] == "DB_NOT_EMPTY"
    assert "force=True" in response["suggestion"]

# Test with force
result = await delete_database(database="mydb", force=True)
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["database"] == "mydb"
assert response["data"]["forced"] == True
```

#### get_database_info
```python
result = await get_database_info(database="mydb")
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["database"] == "mydb"
assert response["data"]["database_type"] in ["milvus", "weaviate"]
assert "collections_count" in response["data"]
```

### 2. Collection Tools

#### create_collection
```python
result = await create_collection(
    database="mydb",
    collection="docs",
    embedding="auto"
)
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["collection"] == "docs"
assert response["data"]["database"] == "mydb"
assert "embedding" in response["data"]
assert "chunking_strategy" in response["data"]
```

#### delete_collection
```python
# Test without force
result = await delete_collection(
    database="mydb",
    collection="docs",
    force=False
)
response = json.loads(result)

if has_documents:
    assert response["status"] == "error"
    assert response["error_code"] == "COLL_NOT_EMPTY"

# Test with force
result = await delete_collection(
    database="mydb",
    collection="docs",
    force=True
)
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["collection"] == "docs"
assert response["data"]["forced"] == True
```

#### list_collections
```python
result = await list_collections(database="mydb")
response = json.loads(result)

assert response["status"] == "success"
assert "collections" in response["data"]
assert response["data"]["total_collections"] >= 0
assert isinstance(response["data"]["collections"], list)
```

#### get_collection_info
```python
result = await get_collection_info(
    database="mydb",
    collection="docs"
)
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["name"] == "docs"
assert response["data"]["database"] == "mydb"
assert "embedding" in response["data"]
assert "chunking" in response["data"]
```

### 3. Document Tools

#### write_documents
```python
documents = [
    {"url": "doc1", "text": "content1"},
    {"url": "doc2", "text": "content2"}
]

result = await write_documents(
    database="mydb",
    documents=documents
)
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["documents_written"] == 2
assert response["data"]["chunks_created"] > 0
assert response["data"]["collection"] == "docs"
assert "embedding_model" in response["data"]
```

#### delete_documents
```python
# Test without force (should fail)
result = await delete_documents(
    database="mydb",
    collection="docs",
    document_ids=["doc1"],
    force=False
)
response = json.loads(result)

assert response["status"] == "error"
assert response["error_code"] == "DOC_DELETE_REQUIRES_FORCE"

# Test with force
result = await delete_documents(
    database="mydb",
    collection="docs",
    document_ids=["doc1", "doc2"],
    force=True
)
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["documents_deleted"] == 2
assert response["data"]["forced"] == True
```

#### get_document
```python
result = await get_document(
    database="mydb",
    collection="docs",
    document_id="doc1"
)
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["document_id"] == "doc1"
assert "document" in response["data"]
```

#### search
```python
result = await search(
    database="mydb",
    query="test query",
    limit=5
)
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["query"] == "test query"
assert response["data"]["results_count"] >= 0
assert isinstance(response["data"]["results"], list)
assert response["metadata"]["limit"] == 5
```

#### query
```python
result = await query(
    database="mydb",
    query="test query",
    limit=5
)
response = json.loads(result)

assert response["status"] == "success"
assert response["data"]["query"] == "test query"
assert "summary" in response["data"]
assert response["data"]["limit"] == 5
```

### 4. Utility Tools

#### list_databases
```python
result = await list_databases()
response = json.loads(result)

assert response["status"] == "success"
assert "databases" in response["data"]
assert response["data"]["total_databases"] >= 0
assert isinstance(response["data"]["databases"], list)
```

#### refresh_databases
```python
result = await refresh_databases()
response = json.loads(result)

assert response["status"] == "success"
assert "milvus" in response["data"]
assert "weaviate" in response["data"]
assert "total_added" in response["data"]
```

## Error Response Testing

### Test Error Codes
```python
# Database not found
result = await some_tool(database="nonexistent")
response = json.loads(result)

assert response["status"] == "error"
assert response["error_code"] == "DB_NOT_FOUND"
assert "database" in response["details"]
assert "available_databases" in response["details"]
assert "suggestion" in response

# Collection not found
result = await some_tool(database="mydb", collection="nonexistent")
response = json.loads(result)

assert response["status"] == "error"
assert response["error_code"] == "COLL_NOT_FOUND"
assert "collection" in response["details"]
assert "available_collections" in response["details"]
```

## Files to Update

### Priority 1 - Integration Tests
1. `tests/test_integration_mcp_server.py` - Main MCP server tests
2. `tests/test_mcp_server.py` - MCP server unit tests
3. `tests/test_document_ingestion_integration.py` - Document ingestion tests

### Priority 2 - E2E Tests
4. `tests/e2e/test_mcp_milvus_e2e.py` - Milvus E2E tests
5. `tests/e2e/test_mcp_weaviate_simple.py` - Weaviate E2E tests
6. `tests/e2e/test_functions_simple.py` - Simple function tests

### Priority 3 - Specific Feature Tests
7. `tests/test_phase45_search_quality.py` - Search quality tests
8. `tests/test_query_integration.py` - Query integration tests
9. `tests/test_mcp_query.py` - MCP query tests

## Helper Function

Add this helper to `tests/helpers.py`:

```python
import json
from typing import Any

def parse_mcp_response(result: str) -> dict[str, Any]:
    """Parse MCP tool response as JSON.
    
    Args:
        result: JSON string response from MCP tool
        
    Returns:
        Parsed JSON response dict
        
    Raises:
        AssertionError: If response is not valid JSON
    """
    try:
        return json.loads(result)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON response: {result}") from e

def assert_success_response(response: dict[str, Any], operation: str | None = None) -> None:
    """Assert response is a successful MCP response.
    
    Args:
        response: Parsed JSON response
        operation: Expected operation name (optional)
    """
    assert response["status"] == "success", f"Expected success, got: {response}"
    assert "message" in response
    assert "data" in response
    
    if operation:
        assert response.get("metadata", {}).get("operation") == operation

def assert_error_response(
    response: dict[str, Any],
    error_code: str | None = None
) -> None:
    """Assert response is an error MCP response.
    
    Args:
        response: Parsed JSON response
        error_code: Expected error code (optional)
    """
    assert response["status"] == "error", f"Expected error, got: {response}"
    assert "error_code" in response
    assert "message" in response
    
    if error_code:
        assert response["error_code"] == error_code
```

## Testing Strategy

1. **Start with unit tests** - Update `test_integration_mcp_server.py` first
2. **Then integration tests** - Update document ingestion and query tests
3. **Finally E2E tests** - Update E2E tests last (require services running)
4. **Run tests incrementally** - Test each file after updating
5. **Use helper functions** - Add JSON parsing helpers to reduce duplication

## Common Pitfalls

1. **Forgetting to parse JSON** - Always `json.loads()` the result
2. **Checking wrong fields** - Use `response["data"]` not `response["result"]`
3. **Not checking status** - Always verify `response["status"]` first
4. **Ignoring error codes** - Check `error_code` for specific error types
5. **Missing metadata** - Some responses include `metadata` with timestamps

## Validation Checklist

For each updated test file:
- [ ] All tool calls parse JSON responses
- [ ] Success responses check `status == "success"`
- [ ] Error responses check `status == "error"` and `error_code`
- [ ] Data fields validated against tool-specific format
- [ ] Metadata fields checked where applicable
- [ ] Tests run and pass
- [ ] No plain text assertions remain

## Example Complete Test

```python
import json
import pytest
from tests.helpers import parse_mcp_response, assert_success_response

@pytest.mark.integration
async def test_create_and_query_database():
    """Test complete workflow with JSON responses."""
    
    # Create database
    result = await create_database(
        database="test_db",
        database_type="milvus",
        embedding="auto"
    )
    response = parse_mcp_response(result)
    assert_success_response(response, "create_database")
    assert response["data"]["database"] == "test_db"
    assert response["data"]["connection_status"] == "connected"
    
    # Create collection
    result = await create_collection(
        database="test_db",
        collection="docs"
    )
    response = parse_mcp_response(result)
    assert_success_response(response, "create_collection")
    assert response["data"]["collection"] == "docs"
    
    # Write documents
    documents = [{"url": "doc1", "text": "test content"}]
    result = await write_documents(
        database="test_db",
        documents=documents
    )
    response = parse_mcp_response(result)
    assert_success_response(response, "write_documents")
    assert response["data"]["documents_written"] == 1
    
    # Search
    result = await search(
        database="test_db",
        query="test",
        limit=5
    )
    response = parse_mcp_response(result)
    assert_success_response(response, "search")
    assert response["data"]["results_count"] >= 0
    
    # Cleanup
    result = await delete_database(database="test_db", force=True)
    response = parse_mcp_response(result)
    assert_success_response(response, "delete_database")
```

## Next Steps

1. Add helper functions to `tests/helpers.py`
2. Update `test_integration_mcp_server.py` first
3. Run tests: `uv run pytest tests/test_integration_mcp_server.py -v`
4. Continue with other test files systematically
5. Update E2E tests last (require running services)