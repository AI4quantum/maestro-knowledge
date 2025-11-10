# Maestro Knowledge LLM-Friendly Refactoring Plan

## Executive Summary

This document outlines the implementation plan for making Maestro Knowledge more LLM-friendly by addressing critical compatibility issues and adding production-ready features. Based on the analysis in AGENT_FRIENDLY.md, we're implementing a **direct refactoring approach** without backwards compatibility, focusing on getting agents working correctly.

### Key Decisions
- ✅ **No backwards compatibility** - Direct refactoring on same port (8030)
- ✅ **Agent interaction is priority** - Focus on what helps agents use the tool effectively
- ✅ **Documentation-driven approach** - Better docs help agents understand capabilities and limitations
- ✅ **Working tests after each phase** - Enable agent testing at each milestone
- ✅ **Code-based changes** - Use automated refactoring to save tokens

### Implementation Philosophy
**Priority Order Based on Agent Needs:**
1. **Parameter compatibility** (Phase 1-2) - Remove barriers to agent interaction
2. **Documentation clarity** (Phase 3) - Help agents understand what tools can do
3. **Critical bugs & error handling** (Phase 4-5) - Fix serious issues, improve recovery
4. **Access control** (Phase 6) - Enable multi-tenant scenarios
5. **Refinements** (Phase 7-10) - Polish and optimize

---

## Phase 1: Remove 'input' Wrapper (CRITICAL)

### Problem
FastMCP generates nested schemas `{"input": {"database": "x"}}` but agents expect flat `{"database": "x"}`. This causes 100% failure rate for LLM agents.

### Solution
Refactor all tool definitions to use flat parameter structure.

### Implementation Steps

#### 1.1 Update Input Model Classes (24 classes)
**File**: `src/maestro_mcp/server.py`

Current structure:
```python
class CreateVectorDatabaseInput(BaseModel):
    db_name: str = Field(...)
    db_type: str = Field(...)
    collection_name: str = Field(...)
```

New structure (flat parameters):
```python
# Remove Input classes, use direct parameters in tool functions
@app.tool()
async def create_vector_database_tool(
    database: str = Field(..., description="Name of the vector database instance"),
    database_type: str = Field(..., description="Type of vector database"),
    collection: str = Field(..., description="Name of the collection")
) -> str:
    """Create a new vector database instance."""
```

**Classes to refactor** (lines 398-593):
- CreateVectorDatabaseInput
- SetupDatabaseInput
- GetSupportedEmbeddingsInput
- WriteDocumentsInput
- WriteDocumentInput
- WriteDocumentToCollectionInput
- ListDocumentsInput
- ListDocumentsInCollectionInput
- CountDocumentsInput
- DeleteDocumentsInput
- DeleteDocumentInput
- DeleteDocumentFromCollectionInput
- GetDocumentInput
- DeleteCollectionInput
- CleanupInput
- GetDatabaseInfoInput
- ListCollectionsInput
- GetCollectionInfoInput
- CreateCollectionInput
- QueryInput
- SearchInput

#### 1.2 Modify Tool Decorators
**File**: `src/maestro_mcp/server.py` (lines 653-1619)

For each tool function:
1. Remove `input: XxxInput` parameter
2. Add individual parameters with Field() descriptors
3. Update function body to use direct parameters instead of `input.field_name`

Example transformation:
```python
# BEFORE
@app.tool()
async def create_vector_database_tool(input: CreateVectorDatabaseInput) -> str:
    db_name = input.db_name
    db_type = input.db_type
    
# AFTER
@app.tool()
async def create_vector_database_tool(
    database: str = Field(..., description="Name of the vector database instance"),
    database_type: str = Field(..., description="Type of vector database"),
    collection: str = Field(..., description="Name of the collection")
) -> str:
    # Use parameters directly
```

#### 1.3 Test Schema Generation
Create test to verify MCP schema is flat:
```python
# Test that schema doesn't have nested 'input' wrapper
schema = app.get_tool_schema("create_vector_database_tool")
assert "input" not in schema["parameters"]
assert "database" in schema["parameters"]
```

---

## Phase 2: Rename Parameters for Clarity

### Problem
Current names like `db_name`, `collection_name` are verbose and inconsistent. Agents often guess wrong names.

### Parameter Mapping

| Old Name | New Name | Occurrences | Rationale |
|----------|----------|-------------|-----------|
| `db_name` | `database` | 17 tools | Shorter, clearer |
| `collection_name` | `collection` | 10 tools | Shorter, clearer |
| `doc_name` | `document_name` | 3 tools | More explicit |
| `embedding` | `embed_model` | 6 tools | Clearer purpose |

### Implementation Steps

#### 2.1-2.4 Rename in Tool Functions
**File**: `src/maestro_mcp/server.py`

Systematic find-replace in all tool functions:
- `db_name` → `database`
- `collection_name` → `collection`
- `doc_name` → `document_name`
- `embedding` → `embed_model`

#### 2.5 Update Function Implementations
Update all references within function bodies:
```python
# BEFORE
db = get_database_by_name(input.db_name)

# AFTER
db = get_database_by_name(database)
```

#### 2.6 Update vector_databases Dictionary
**File**: `src/maestro_mcp/server.py` (line 48)

Update dictionary keys to use new naming convention:
```python
# Keys should use 'database' not 'db_name'
vector_databases: dict[str, VectorDatabase] = {}
```

---

## Phase 3: Fix Reassembly Bug (CRITICAL)

### Problem
Text with overlap gets duplicated during reassembly. Example:
```
Chunk 1: "The quick brown fox"
Chunk 2: "brown fox jumps over"
Result: "The quick brown fox brown fox jumps over" ❌
Expected: "The quick brown fox jumps over" ✅
```

### Root Cause
**File**: `src/db/vector_db_base.py` (lines 431-479)

Current implementation doesn't handle overlapping text properly:
```python
def _reassemble_chunks_into_document(self, chunks: list[dict[str, Any]]) -> str:
    # Simply concatenates without checking for overlap
    return " ".join([chunk.get("text", "") for chunk in sorted_chunks])
```

### Solution

#### 3.1 Analyze Overlap Handling
Review current logic in `_reassemble_chunks_into_document`:
- How chunks are sorted (by chunk_index)
- How text is concatenated
- Where overlap information is stored

#### 3.2 Implement Deduplication Logic
```python
def _reassemble_chunks_into_document(self, chunks: list[dict[str, Any]]) -> str:
    """Reassemble document from chunks, handling overlaps correctly."""
    if not chunks:
        return ""
    
    # Sort by chunk_index
    sorted_chunks = sorted(chunks, key=lambda x: x.get("chunk_index", 0))
    
    # Start with first chunk
    result = sorted_chunks[0].get("text", "")
    
    # Process remaining chunks
    for i in range(1, len(sorted_chunks)):
        current_text = sorted_chunks[i].get("text", "")
        
        # Check for overlap with previous text
        overlap_size = self._find_overlap(result, current_text)
        
        if overlap_size > 0:
            # Skip overlapping portion
            result += current_text[overlap_size:]
        else:
            # No overlap, add with space
            result += " " + current_text
    
    return result

def _find_overlap(self, text1: str, text2: str, min_overlap: int = 10) -> int:
    """Find the size of overlap between end of text1 and start of text2."""
    max_overlap = min(len(text1), len(text2))
    
    for overlap in range(max_overlap, min_overlap - 1, -1):
        if text1[-overlap:] == text2[:overlap]:
            return overlap
    
    return 0
```

#### 3.3 Add Unit Tests
**File**: `tests/test_reassembly.py` (new file)

```python
def test_reassembly_with_overlap():
    """Test that overlapping chunks are deduplicated."""
    chunks = [
        {"chunk_index": 0, "text": "The quick brown fox"},
        {"chunk_index": 1, "text": "brown fox jumps over"},
        {"chunk_index": 2, "text": "jumps over the lazy dog"}
    ]
    
    result = db._reassemble_chunks_into_document(chunks)
    
    # Should not have duplicated text
    assert "brown fox brown fox" not in result
    assert "jumps over jumps over" not in result
    
    # Should have complete text
    assert "The quick brown fox jumps over the lazy dog" in result
```

---

## Phase 4: Add Ownership Metadata

### Problem
No way to track who created documents or collections. Needed for access control and auditing.

### Solution
Add `owner` field to document and collection metadata.

### Implementation Steps

#### 4.1 Add Owner to Document Metadata
**Files**: 
- `src/maestro_mcp/server.py` (write_documents, write_document, write_document_to_collection)
- `src/db/vector_db_milvus.py` (write_documents)
- `src/db/vector_db_weaviate.py` (write_documents)

Add owner parameter:
```python
@app.tool()
async def write_document_to_collection(
    database: str,
    collection: str,
    document_name: str,
    text: str,
    url: str | None = None,
    metadata: dict[str, Any] | None = None,
    owner: str | None = Field(None, description="Owner of the document (email or user ID)"),
    embed_model: str | None = None
) -> str:
    """Write a single document to a specific collection."""
    
    # Add owner to metadata
    if metadata is None:
        metadata = {}
    if owner:
        metadata["owner"] = owner
```

#### 4.2 Add Owner to Collection Metadata
**Files**:
- `src/db/vector_db_milvus.py` (get_collection_info, setup)
- `src/db/vector_db_weaviate.py` (get_collection_info, setup)

Store owner in collection properties:
```python
async def setup(
    self,
    embedding: str = "openai",
    chunking_config: dict[str, Any] | None = None,
    owner: str | None = None
) -> tuple[bool, str]:
    """Set up database with owner information."""
    
    # Store owner in collection metadata
    meta = {
        "embedding_model": embedding,
        "owner": owner or "system",
        "created_at": datetime.now().isoformat()
    }
```

#### 4.3-4.4 Update Write Operations
Ensure all document write operations accept and store owner:
- write_documents
- write_document
- write_document_to_collection

---

## Phase 5: Implement Access Control

### Problem
No way to restrict document access by user or group. Can't build multi-tenant RAG systems.

### Solution
Metadata-based access control with visibility levels.

### Access Control Schema

```python
{
    "access_control": {
        "visibility": "private",  # public | private | restricted
        "allowed_users": ["alice@example.com", "bob@example.com"],
        "allowed_groups": ["hr", "executives", "managers"],
        "owner": "hr-team@example.com"
    }
}
```

### Implementation Steps

#### 5.1 Define Schema
**File**: `src/db/access_control.py` (new file)

```python
from typing import Literal
from pydantic import BaseModel, Field

class AccessControl(BaseModel):
    """Access control metadata for documents."""
    visibility: Literal["public", "private", "restricted"] = Field(
        default="public",
        description="Visibility level of the document"
    )
    allowed_users: list[str] = Field(
        default_factory=list,
        description="List of user emails/IDs with access"
    )
    allowed_groups: list[str] = Field(
        default_factory=list,
        description="List of group names with access"
    )
    owner: str | None = Field(
        default=None,
        description="Owner of the document"
    )

def check_access(
    access_control: dict,
    user: str | None,
    user_groups: list[str] | None = None
) -> bool:
    """Check if user has access to document."""
    visibility = access_control.get("visibility", "public")
    
    # Public documents: always accessible
    if visibility == "public":
        return True
    
    # No user provided: deny access to non-public
    if not user:
        return False
    
    # Owner always has access
    owner = access_control.get("owner")
    if owner and user == owner:
        return True
    
    # Check allowed users
    allowed_users = access_control.get("allowed_users", [])
    if user in allowed_users:
        return True
    
    # Check allowed groups
    if user_groups:
        allowed_groups = access_control.get("allowed_groups", [])
        if any(group in allowed_groups for group in user_groups):
            return True
    
    return False
```

#### 5.2 Add User Parameter to Query/Search
**File**: `src/maestro_mcp/server.py`

```python
@app.tool()
async def query(
    database: str,
    query: str,
    limit: int = 5,
    collection: str | None = None,
    user: str | None = Field(None, description="User email/ID for access control"),
    user_groups: list[str] | None = Field(None, description="User's group memberships")
) -> str:
    """Query with access control filtering."""
    
    kwargs = {
        "query": query,
        "limit": limit,
        "user": user,
        "user_groups": user_groups
    }
```

#### 5.3 Implement Filtering in Milvus
**File**: `src/db/vector_db_milvus.py` (_search_documents)

```python
async def _search_documents(
    self,
    query: str,
    limit: int = 5,
    user: str | None = None,
    user_groups: list[str] | None = None
) -> list[dict[str, Any]]:
    """Search with access control filtering."""
    
    # Get search results
    results = await self.client.search(...)
    
    # Filter by access control
    filtered_results = []
    for result in results:
        metadata = result.get("metadata", {})
        access_control = metadata.get("access_control", {})
        
        if check_access(access_control, user, user_groups):
            filtered_results.append(result)
    
    return filtered_results[:limit]
```

#### 5.4 Implement Filtering in Weaviate
**File**: `src/db/vector_db_weaviate.py` (search)

Similar implementation as Milvus.

#### 5.5 Add Helper Functions
Create utility functions for access control validation and filtering.

---

## Phase 6: Add Search Quality Controls

### Problem
No way to filter low-quality results or search by metadata. Agents get irrelevant results.

### Solution
Add `min_score` threshold and `metadata_filters` parameters.

### Implementation Steps

#### 6.1 Add min_score Parameter
**File**: `src/maestro_mcp/server.py`

```python
@app.tool()
async def search(
    database: str,
    query: str,
    limit: int = 5,
    collection: str | None = None,
    min_score: float | None = Field(None, description="Minimum similarity score (0-1)"),
    metadata_filters: dict[str, Any] | None = Field(None, description="Filter by metadata fields")
) -> str:
    """Search with quality controls."""
```

#### 6.2 Add metadata_filters Parameter
Support filtering by metadata fields:
```python
metadata_filters = {
    "doc_type": "technical",
    "language": "python",
    "version": "3.11"
}
```

#### 6.3-6.4 Implement Score Filtering
**Files**: 
- `src/db/vector_db_milvus.py` (_search_documents)
- `src/db/vector_db_weaviate.py` (search)

```python
# Filter by minimum score
if min_score is not None:
    filtered_results = [
        r for r in results 
        if r.get("score", 0) >= min_score
    ]
```

#### 6.5 Implement Metadata Filtering
```python
# Filter by metadata
if metadata_filters:
    filtered_results = [
        r for r in results
        if all(
            r.get("metadata", {}).get(k) == v
            for k, v in metadata_filters.items()
        )
    ]
```

---

## Phase 7: Improve Citation Format

### Problem
URLs buried in technical metadata, hard for LLMs to extract.

### Current Format
```json
{
    "text": "...",
    "metadata": {
        "url": "https://example.com/doc",
        "doc_name": "example"
    },
    "score": 0.85
}
```

### New Format
```json
{
    "text": "...",
    "url": "https://example.com/doc",
    "source_citation": "Source: example (https://example.com/doc)",
    "score": 0.85,
    "metadata": {
        "doc_name": "example"
    }
}
```

### Implementation Steps

#### 7.1 Restructure Result Format
**Files**:
- `src/db/vector_db_milvus.py` (_process_hit in _search_documents)
- `src/db/vector_db_weaviate.py` (search result processing)

#### 7.2 Add source_citation Field
```python
def format_result(result: dict) -> dict:
    """Format search result with LLM-friendly citations."""
    url = result.get("metadata", {}).get("url")
    doc_name = result.get("metadata", {}).get("doc_name", "Unknown")
    
    formatted = {
        "text": result.get("text", ""),
        "score": result.get("score", 0),
        "metadata": result.get("metadata", {})
    }
    
    # Add top-level URL
    if url:
        formatted["url"] = url
        formatted["source_citation"] = f"Source: {doc_name} ({url})"
    else:
        formatted["source_citation"] = f"Source: {doc_name}"
    
    return formatted
```

#### 7.3 Update Result Processing
Apply formatting to all search results in both database implementations.

---

## Phase 8: Enhance Error Messages

### Problem
Generic error messages don't help agents recover. Example:
```
Error: Database not found
```

### Solution
Provide actionable guidance in error messages.

### Better Error Messages
```
Error: Database 'mydb' not found.

Available databases: ['docs', 'knowledge', 'support']

To create a new database, use:
create_vector_database_tool(database="mydb", database_type="milvus", collection="default")
```

### Implementation Steps

#### 8.1 Create Error Templates
**File**: `src/maestro_mcp/errors.py` (new file)

```python
class ErrorMessages:
    """Helpful error messages for common issues."""
    
    @staticmethod
    def database_not_found(db_name: str, available: list[str]) -> str:
        return f"""Database '{db_name}' not found.

Available databases: {available}

To create a new database, use:
create_vector_database_tool(database="{db_name}", database_type="milvus", collection="default")
"""
    
    @staticmethod
    def collection_not_found(collection: str, database: str, available: list[str]) -> str:
        return f"""Collection '{collection}' not found in database '{database}'.

Available collections: {available}

To create a new collection, use:
create_collection(database="{database}", collection="{collection}", embed_model="openai")
"""
    
    @staticmethod
    def invalid_embedding(embed_model: str, supported: list[str]) -> str:
        return f"""Embedding model '{embed_model}' not supported.

Supported models: {supported}

To see all supported embeddings, use:
get_supported_embeddings(database="your_database")
"""
```

#### 8.2 Update Try-Except Blocks
**File**: `src/maestro_mcp/server.py`

Replace generic error messages with helpful ones:
```python
# BEFORE
except Exception as e:
    return f"Error: {str(e)}"

# AFTER
except KeyError:
    available = list(vector_databases.keys())
    return ErrorMessages.database_not_found(database, available)
except ValueError as e:
    if "embedding" in str(e):
        supported = db.supported_embeddings
        return ErrorMessages.invalid_embedding(embed_model, supported)
    return str(e)
```

#### 8.3 Add Validation Errors
Add parameter validation with clear requirements:
```python
if not database:
    return "Error: 'database' parameter is required. Provide the name of your vector database."

if limit < 1 or limit > 100:
    return "Error: 'limit' must be between 1 and 100. Adjust your query limit."
```

---

## Phase 9: Update Test Suite

### Problem
Tests use old parameter names and don't cover new features.

### Implementation Steps

#### 9.1 Update Test Files
**Files to update**:
- `tests/test_*.py` (all test files)
- `tests/e2e/test_*.py` (all e2e tests)

Find and replace:
- `db_name` → `database`
- `collection_name` → `collection`
- `doc_name` → `document_name`
- `embedding` → `embed_model`

#### 9.2 Update E2E Tests
**Files**:
- `tests/e2e/test_mcp_milvus_e2e.py`
- `tests/e2e/test_mcp_weaviate_e2e.py`

Update test cases to use new parameter names and verify flat schema.

#### 9.3 Add Access Control Tests
**File**: `tests/test_access_control.py` (new file)

```python
async def test_public_document_access():
    """Public documents accessible to all users."""
    # Create public document
    # Query without user - should succeed
    # Query with user - should succeed

async def test_private_document_access():
    """Private documents only accessible to owner."""
    # Create private document with owner
    # Query without user - should fail
    # Query with wrong user - should fail
    # Query with owner - should succeed

async def test_restricted_document_access():
    """Restricted documents accessible to allowed users/groups."""
    # Create restricted document
    # Query with allowed user - should succeed
    # Query with allowed group - should succeed
    # Query with disallowed user - should fail
```

#### 9.4 Add Search Quality Tests
**File**: `tests/test_search_quality.py` (new file)

```python
async def test_min_score_filtering():
    """Test that min_score filters low-quality results."""
    # Search with min_score=0.8
    # Verify all results have score >= 0.8

async def test_metadata_filtering():
    """Test that metadata_filters work correctly."""
    # Search with metadata_filters={"doc_type": "technical"}
    # Verify all results match filter
```

#### 9.5 Add Reassembly Tests
**File**: `tests/test_reassembly.py` (new file)

Test cases for overlap handling (see Phase 3.3).

---

## Phase 10: Update Documentation

### Implementation Steps

#### 10.1 Update README.md
**File**: `README.md`

- Update all code examples with new parameter names
- Add examples of new features (access control, search quality)
- Update API reference

#### 10.2 Update Examples
**Files**: `examples/*.py`

Update all example scripts:
- `examples/document_ingestion_example.py`
- `examples/mcp_example.py`
- `examples/milvus_example.py`
- `examples/weaviate_example.py`

#### 10.3 Create Migration Guide
**File**: `docs/MIGRATION.md` (new file)

```markdown
# Migration Guide: v1.x to v2.0

## Breaking Changes

### Parameter Renames
- `db_name` → `database`
- `collection_name` → `collection`
- `doc_name` → `document_name`
- `embedding` → `embed_model`

### Schema Changes
- Removed nested `{"input": {...}}` wrapper
- All parameters are now flat

### Migration Steps
1. Update all tool calls to use new parameter names
2. Remove `input` wrapper from tool calls
3. Update any stored references to old parameter names

## New Features

### Access Control
Documents now support access control metadata...

### Search Quality Controls
Search now supports min_score and metadata_filters...
```

#### 10.4 Update MCP Server README
**File**: `src/maestro_mcp/README.md`

- Document new flat parameter structure
- Add examples of access control
- Add examples of search quality controls
- Update configuration examples

---

## Testing Strategy

### Unit Tests
- Test each phase independently
- Focus on parameter marshalling correctness
- Test bug fixes (reassembly)

### Integration Tests
- Test end-to-end workflows with new parameters
- Test access control enforcement
- Test search quality filtering

### E2E Tests
- Test MCP server with real agents
- Verify flat schema generation
- Test all new features

### Test Coverage Goals
- Maintain >80% code coverage
- 100% coverage for new features
- All critical paths tested

---

## Implementation Timeline

### Week 1: Critical Fixes
- **Days 1-2**: Phase 1 (Remove 'input' wrapper)
- **Days 3-4**: Phase 2 (Rename parameters)
- **Day 5**: Phase 3 (Fix reassembly bug)

### Week 2: Core Features
- **Days 1-2**: Phase 4 (Add ownership)
- **Days 3-5**: Phase 5 (Access control)

### Week 3: Quality & Polish
- **Days 1-2**: Phase 6 (Search quality)
- **Days 3-4**: Phase 7 (Citations) + Phase 8 (Errors)
- **Day 5**: Phase 9 (Update tests)

### Week 4: Documentation & Release
- **Days 1-3**: Phase 10 (Documentation)
- **Days 4-5**: Final testing and release prep

---

## Success Criteria

### Phase 1 Success
- ✅ All 24 tools use flat parameters
- ✅ MCP schema has no 'input' wrapper
- ✅ Agents can call tools successfully

### Phase 2 Success
- ✅ All parameters renamed consistently
- ✅ No references to old parameter names
- ✅ Tests pass with new names

### Phase 3 Success
- ✅ Reassembly handles overlaps correctly
- ✅ No text duplication in results
- ✅ Unit tests verify fix

### Phase 4 Success
- ✅ Documents have owner metadata
- ✅ Collections have owner metadata
- ✅ Owner tracked in all write operations

### Phase 5 Success
- ✅ Access control filtering works
- ✅ Public/private/restricted visibility enforced
- ✅ User/group permissions respected

### Phase 6 Success
- ✅ min_score filters low-quality results
- ✅ metadata_filters work correctly
- ✅ Search quality improved

### Phase 7 Success
- ✅ URLs at top level of results
- ✅ source_citation field present
- ✅ LLMs can extract citations easily

### Phase 8 Success
- ✅ Error messages are actionable
- ✅ Suggestions provided for common errors
- ✅ Agents can recover from errors

### Phase 9 Success
- ✅ All tests updated for new parameters
- ✅ New features have test coverage
- ✅ Test suite passes completely

### Phase 10 Success
- ✅ Documentation updated
- ✅ Examples work with new API
- ✅ Migration guide complete

---

## Risk Mitigation

### Risk: Breaking Existing Integrations
**Mitigation**: 
- Document all breaking changes clearly
- Provide migration guide
- Version bump to 2.0 to signal breaking changes

### Risk: Test Failures
**Mitigation**:
- Update tests incrementally with each phase
- Run tests after each change
- Fix issues immediately

### Risk: Performance Degradation
**Mitigation**:
- Profile access control filtering
- Optimize metadata filtering
- Benchmark before/after

### Risk: Incomplete Migration
**Mitigation**:
- Use grep/search to find all occurrences
- Systematic file-by-file review
- Automated testing to catch misses

---

## Files Modified Summary

### Core Implementation
- `src/maestro_mcp/server.py` - All tool definitions
- `src/db/vector_db_base.py` - Reassembly fix
- `src/db/vector_db_milvus.py` - Access control, search quality
- `src/db/vector_db_weaviate.py` - Access control, search quality

### New Files
- `src/db/access_control.py` - Access control utilities
- `src/maestro_mcp/errors.py` - Error message templates
- `tests/test_access_control.py` - Access control tests
- `tests/test_search_quality.py` - Search quality tests
- `tests/test_reassembly.py` - Reassembly tests
- `docs/MIGRATION.md` - Migration guide

### Documentation
- `README.md` - Updated examples
- `src/maestro_mcp/README.md` - Updated MCP docs
- `examples/*.py` - All example files

### Tests
- `tests/test_*.py` - All test files
- `tests/e2e/test_*.py` - All e2e test files

---

## Next Steps

### Immediate Actions
1. ✅ Plan reviewed and approved with revised priorities
2. Begin Phase 1-2: Parameter Compatibility
   - Use automated refactoring for efficiency
   - Update tests incrementally
   - Verify agent can call tools after changes

### After Each Phase
1. Run full test suite to ensure nothing breaks
2. Test with actual agent to verify improvements
3. Document any issues or learnings
4. Adjust plan if needed based on findings

### Automation Checklist
- [ ] Create script for parameter renaming across all files
- [ ] Generate test updates programmatically
- [ ] Use batch operations for related changes
- [ ] Minimize manual token-heavy operations

### Testing Strategy Per Phase
Each phase must have:
- ✅ Unit tests passing
- ✅ Integration tests passing
- ✅ E2E tests passing
- ✅ Manual agent testing successful

---

## Questions & Decisions

### Q1: Default Visibility
**Decision**: Default to "public" for backwards compatibility. Users must explicitly set "private" or "restricted".

### Q2: Access Control Enforcement
**Decision**: Enforce at query/search time, not write time. This allows flexibility in changing access rules.

### Q3: Owner Format
**Decision**: Accept any string (email, user ID, username). No validation to keep it flexible.

### Q4: Metadata Filter Syntax
**Decision**: Simple key-value matching. Can extend to operators (>, <, etc.) in future.

### Q5: Error Message Verbosity
**Decision**: Verbose by default. Agents benefit from detailed guidance. Can add "verbose" flag later if needed.

---

## Appendix: Code Examples

### Example 1: Flat Parameter Tool
```python
@app.tool()
async def write_document_to_collection(
    database: str = Field(..., description="Name of the vector database instance"),
    collection: str = Field(..., description="Name of the collection"),
    document_name: str = Field(..., description="Unique name for the document"),
    text: str = Field(..., description="Document text content"),
    url: str | None = Field(None, description="Source URL of the document"),
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata"),
    owner: str | None = Field(None, description="Owner of the document"),
    embed_model: str | None = Field(None, description="Embedding model to use")
) -> str:
    """Write a single document to a specific collection."""
    # Implementation uses parameters directly
    db = get_database_by_name(database)
    # ... rest of implementation
```

### Example 2: Access Control Check
```python
from src.db.access_control import check_access

# In search function
for result in raw_results:
    access_control = result.get("metadata", {}).get("access_control", {})
    
    if check_access(access_control, user, user_groups):
        filtered_results.append(result)
```

### Example 3: Search with Quality Controls
```python
# Agent calls search with quality controls
results = await search(
    database="docs",
    query="Python async patterns",
    limit=10,
    min_score=0.75,  # Only high-quality results
    metadata_filters={"language": "python", "doc_type": "tutorial"},
    user="alice@example.com",
    user_groups=["developers"]
)
```

### Example 4: LLM-Friendly Citation
```python
# Result format
{
    "text": "Async functions in Python use the async/await syntax...",
    "url": "https://docs.python.org/3/library/asyncio.html",
    "source_citation": "Source: Python Asyncio Docs (https://docs.python.org/3/library/asyncio.html)",
    "score": 0.92,
    "metadata": {
        "doc_name": "asyncio-docs",
        "language": "python",
        "doc_type": "tutorial"
    }
}
```

---

**Document Version**: 1.0  
**Last Updated**: 2025-11-10  
**Status**: Ready for Implementation