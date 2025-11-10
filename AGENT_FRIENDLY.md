# 🚀 Proposal: Making Maestro Knowledge LLM-Friendly

Make the MCP server agent-friendly while maintaining backward compatibility



## Summary

### The Problem

AI agents (specifically kagent with Granite4 models) fail to use our MCP server due to multiple usability issues:

1. **Parameter Format Incompatibility** - FastMCP generates nested schemas `{"input": {...}}` but agents expect flat `{...}`
2. **Confusing Parameter Names** - `db_name`, `collection_name` cause agents to guess wrong names
3. **No Search Quality Controls** - Can't filter irrelevant results or search by metadata
4. **Poor Citation Support** - URLs buried in technical metadata, hard for LLMs to extract
5. **Data Corruption Bug** - Text with overlap gets duplicated during reassembly
6. **No Access Control** - Can't build multi-tenant RAG systems
7. **Cryptic Errors** - Generic messages don't help agents recover

### The Solution

**Dual-port architecture** with progressive enhancements:
- **Port 8031**: New flat parameter format for agents (primary)
- **Port 8030**: Legacy compatibility proxy (backward compatible)
- **Enhanced API**: Quality controls, better citations, access control, clearer errors

### Impact

- ✅ Unblocks all agent workflows
- ✅ Maintains 100% backward compatibility
- ✅ Enables production multi-tenant deployments
- ✅ Fixes critical data integrity bug

---

## Table of Contents

1. [Why LLMs Struggle Today](#part-1-why-llms-struggle-today)
2. [Technical Implementation](#part-2-technical-implementation)
3. [Priority 0: Critical Blockers](#priority-0-critical-blockers)
4. [Priority 1: High-Value Enhancements](#priority-1-high-value-enhancements)
5. [Priority 2: Production Features](#priority-2-production-features)
6. [Priority 3: Polish](#priority-3-polish)
7. [Implementation Roadmap](#implementation-roadmap)
8. [Testing Strategy](#testing-strategy)
9. [Backward Compatibility](#backward-compatibility)
10. [Open Questions & Decisions](#open-questions--decisions)

---

## Part 1: Why LLMs Struggle Today

### Real-World Failure Example

Agent (kagent with Granite4) attempted:
```
Create a database called 'db', add a collection 'library', 
then add 10 test documents.
```

**Result**: ❌ Complete failure across multiple issues

### Root Problems

#### 1. Parameter Format Incompatibility (CRITICAL)

**Problem**: FastMCP generates nested schema requiring `{"input": {"db_name": "x"}}` but agents send flat `{"db_name": "x"}`

**Why it happens**: FastMCP validates schemas **before** tool execution, preventing any runtime workarounds

**Impact**: Tool calls fail completely - agents can't use the server at all

#### 2. Confusing Parameter Names (CRITICAL)

**Current**: `db_name`, `collection_name`, `doc_name` (verbose, inconsistent)

**Agent behavior**: Guesses `name` instead → validation errors

**Impact**: Even when format works, wrong names cause failures

#### 3. No Search Quality Control (HIGH)

**Problem**: Returns all N results even if last ones have similarity 0.15 (nearly random)

**Missing features**:
- No similarity threshold filtering
- No metadata-based filtering (e.g., "only security docs")

**Impact**: Unreliable answers with irrelevant context

#### 4. Citations Not LLM-Friendly (MEDIUM)

**Problem**: 
- URLs buried in chunk-level metadata
- Technical noise (offset_start, chunk_sequence_number) mixed with useful metadata
- No document-level grouping

**Impact**: Hard to cite sources properly, increases hallucination risk

#### 5. Data Corruption Bug (CRITICAL)

**Problem**: Reassembly concatenates chunks naively

**Example with overlap**:
- Chunk 1: "The quick brown fox" (offset 0-19)
- Chunk 2: "brown fox jumps" (offset 10-25, overlap=10)
- Current: "The quick brown foxbrown fox jumps" ❌
- Expected: "The quick brown fox jumps" ✅

**Impact**: Wrong embeddings → bad search results

#### 6. No Access Control (MEDIUM)

**Problem**: All documents visible to everyone

**Impact**: Can't build multi-tenant RAG systems or handle sensitive data

#### 7. Cryptic Errors (MEDIUM)

**Current**: `"Error: Failed to search vector database 'db'"`

**What agents need**: Available options and next steps

**Impact**: Agents don't know how to recover from errors

---

## Part 2: Technical Implementation

### Overall Architecture

**Dual-Port Solution**:
```
┌─────────────────────────────────────────┐
│         Single Python Process           │
├─────────────────────────────────────────┤
│                                          │
│  Port 8031 (NEW - Primary)              │
│  ┌────────────────────────────────────┐ │
│  │ FastMCP Server                      │ │
│  │ - Flat parameters                   │ │
│  │ - New names (database, collection)  │ │
│  │ - All new features                  │ │
│  └────────────────────────────────────┘ │
│                                          │
│  Port 8030 (Legacy Proxy)               │
│  ┌────────────────────────────────────┐ │
│  │ Starlette App                       │ │
│  │ - Accepts nested format             │ │
│  │ - Translates old→new names          │ │
│  │ - Forwards to 8031                  │ │
│  │ - Logs for migration tracking       │ │
│  └────────────────────────────────────┘ │
│                                          │
└─────────────────────────────────────────┘
```

---

## Priority 0: Critical Blockers

**Goal**: Make agents able to use the server

### P0.1 - Dual-Port Architecture for Parameter Format

**Technical Constraint**: FastMCP validates schemas before tool execution, making runtime parameter transformation impossible.

**Solution**: Two ports with format translation

#### Implementation Steps

**1. Refactor all 24 tools to flat parameters**

File: `src/maestro_mcp/server.py` lines 398-1630

Change FROM:
```python
@app.tool()
async def create_database(input: CreateDatabaseInput) -> str:
    # implementation
```

Change TO:
```python
@app.tool()
async def create_database(
    database: str,
    collection: str = "MaestroDocs",
    database_type: str = "milvus",
    embed_model: str | None = None
) -> str:
    # implementation
```

**2. Parameter Rename Mapping**

| Old Name | New Name | Affected Models | Reason |
|----------|----------|----------------|--------|
| `db_name` | `database` | 17 models | Shorter, clearer |
| `collection_name` | `collection` | 10 models | Shorter, clearer |
| `doc_name` | `document_name` | 3 models | More explicit |
| `embedding` | `embed_model` | 3 models | Clearer purpose |
| `type` | `database_type` | 1 model | Less ambiguous |

**3. Create compatibility proxy**

File: `src/maestro_mcp/compatibility_proxy.py` (NEW)

```python
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
import httpx

# Parameter translation map
PARAM_MAP = {
    "db_name": "database",
    "collection_name": "collection",
    "doc_name": "document_name",
    "embedding": "embed_model",
    "type": "database_type"
}

app = Starlette()

@app.route("/{path:path}", methods=["POST"])
async def proxy(request: Request):
    """Translate nested format to flat and forward to port 8031."""
    body = await request.json()
    
    # Extract from nested format
    if "input" in body:
        flat_params = body["input"]
        
        # Translate parameter names
        translated = {}
        for old_name, value in flat_params.items():
            new_name = PARAM_MAP.get(old_name, old_name)
            translated[new_name] = value
        
        # Forward to port 8031
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"http://localhost:8031/{request.path_params['path']}",
                json=translated
            )
            return JSONResponse(response.json())
```

**4. Update deployment**

File: `start.sh` (lines 163-202):
```bash
# Launch both servers in single process
python -c "
import asyncio
from src.maestro_mcp.server import run_http_server
from src.maestro_mcp.compatibility_proxy import run_proxy_server

async def main():
    await asyncio.gather(
        run_http_server('localhost', 8031),  # Primary
        run_proxy_server('localhost', 8030)  # Legacy
    )

asyncio.run(main())
"
```

File: `Dockerfile` (line 24):
```dockerfile
EXPOSE 8030 8031
```

#### Files Modified
- `src/maestro_mcp/server.py` - All 24 tools refactored
- `src/maestro_mcp/compatibility_proxy.py` - NEW
- `src/maestro_mcp/parameter_translation.py` - NEW (translation map)
- `start.sh` - Dual-port launch
- `Dockerfile` - Expose both ports

---

### P0.2 - Fix Reassembly Bug (Data Corruption)

**Bug Location**: `src/db/vector_db_base.py` line 442

**Current Code** (BROKEN):
```python
full_text = "".join(chunk["text"] for chunk in sorted_chunks)
```

**Fixed Code**:
```python
def _reassemble_chunks_into_document(self, chunks):
    """Reassemble chunks into original document, handling overlap correctly."""
    if not chunks:
        return None
    
    # Sort by sequence number
    sorted_chunks = sorted(
        chunks, 
        key=lambda x: x.get("metadata", {}).get("chunk_sequence_number", 0)
    )
    
    # Use offset metadata to skip overlapped portions
    full_text_parts = []
    last_end = 0
    
    for chunk in sorted_chunks:
        metadata = chunk.get("metadata", {})
        start = metadata.get("offset_start")
        end = metadata.get("offset_end")
        text = chunk["text"]
        
        # If no offset info, fall back to simple concatenation
        if start is None or end is None:
            full_text_parts.append(text)
            last_end = len(text) if last_end == 0 else last_end + len(text)
            continue
        
        # Skip overlapped portion
        if start < last_end:
            overlap_size = last_end - start
            text = text[overlap_size:] if overlap_size < len(text) else ""
        
        full_text_parts.append(text)
        last_end = end
    
    full_text = "".join(full_text_parts)
    
    # Clean up chunk-specific metadata
    reassembled_doc = sorted_chunks[0].copy()
    reassembled_doc["text"] = full_text
    
    for key in ["chunk_sequence_number", "total_chunks", "offset_start", "offset_end", "chunk_size"]:
        if key in reassembled_doc.get("metadata", {}):
            del reassembled_doc["metadata"][key]
    
    return reassembled_doc
```

**Why Critical**: Corrupted text leads to wrong embeddings and unreliable search

**Files Modified**:
- `src/db/vector_db_base.py` - Fixed `_reassemble_chunks_into_document()` method

---

## Priority 1: High-Value Enhancements

**Goal**: Make search results high-quality and well-attributed

### P1.1 - Search Quality Controls

**Add two new parameters to all search/query tools**:

```python
class SearchInput(BaseModel):
    database: str
    query: str
    limit: int = 5
    collection: str | None = None
    
    # NEW: Quality threshold
    min_similarity: float | None = Field(
        default=None,
        description="Minimum similarity score (0-1). Results below this are excluded. "
                    "Recommended: 0.7+ for high-quality results, 0.5+ for moderate quality."
    )
    
    # NEW: Metadata filtering
    metadata_filter: dict | None = Field(
        default=None,
        description="Filter by metadata fields. "
                    "Example: {'doc_type': 'security', 'author': 'platform-team'}"
    )
```

**Implementation** (in vector DB classes):

```python
async def search(self, query, limit=5, collection=None, min_similarity=None, metadata_filter=None):
    # Overfetch to account for filtering
    raw_limit = limit * 3 if (min_similarity or metadata_filter) else limit
    results = await self._vector_search(query, limit=raw_limit, collection=collection)
    
    # Filter by similarity threshold
    if min_similarity is not None:
        results = [r for r in results if r.get("similarity", 0) >= min_similarity]
    
    # Filter by metadata
    if metadata_filter:
        results = [
            r for r in results
            if all(
                r.get("metadata", {}).get(k) == v
                for k, v in metadata_filter.items()
            )
        ]
    
    return results[:limit]
```

**Files Modified**:
- `src/maestro_mcp/server.py` - Updated SearchInput and QueryInput models
- `src/db/vector_db_base.py` - Updated abstract method signatures
- `src/db/vector_db_milvus.py` - Implemented filtering
- `src/db/vector_db_weaviate.py` - Implemented filtering

---

### P1.2 - Improve Citations & Metadata Clarity

**Problem**: Technical metadata mixed with useful metadata

**Solution 1: Separate system vs user metadata**

Change FROM:
```json
{
  "metadata": {
    "doc_name": "auth-guide",
    "chunk_sequence_number": 3,
    "offset_start": 1500,
    "author": "security-team"
  }
}
```

Change TO:
```json
{
  "document_name": "auth-guide",
  "metadata": {
    "author": "security-team",
    "doc_type": "security"
  },
  "_system": {
    "chunk_sequence_number": 3,
    "total_chunks": 12,
    "offset_start": 1500,
    "offset_end": 2000
  }
}
```

**Solution 2: Add citation helper tool**

```python
@app.tool()
async def get_citations(
    database: str, 
    query: str, 
    limit: int = 5,
    min_similarity: float = 0.7
) -> str:
    """Extract unique source URLs from search results for proper citation.
    
    Returns document-level citations (deduplicates chunks from same document).
    Includes document names and best similarity scores.
    
    Example result:
    [
      {
        "url": "https://docs.example.com/auth.html",
        "document_name": "authentication-guide",
        "similarity": 0.92
      },
      {
        "url": "https://docs.example.com/api.html",
        "document_name": "api-reference",
        "similarity": 0.85
      }
    ]
    """
    results = await db.search(query, limit=limit * 2, min_similarity=min_similarity)
    
    # Group by document, keep best chunk per doc
    citations = {}
    for r in results:
        url = r.get("url", "")
        doc_name = r.get("metadata", {}).get("doc_name", "")
        similarity = r.get("similarity", 0)
        
        key = url or doc_name
        if key not in citations or similarity > citations[key]["similarity"]:
            citations[key] = {
                "url": url,
                "document_name": doc_name,
                "similarity": similarity
            }
    
    # Sort by similarity
    sorted_citations = sorted(
        citations.values(), 
        key=lambda x: x["similarity"], 
        reverse=True
    )
    
    return json.dumps(sorted_citations[:limit], indent=2)
```

**Solution 3: Add document grouping option**

```python
group_by_document: bool = Field(
    default=False,
    description="If True, group chunks by document and return best chunks per document"
)
```

**Files Modified**:
- `src/maestro_mcp/server.py` - Added `get_citations` tool, added `group_by_document` parameter
- `src/db/vector_db_base.py` - Modified result formatting
- `src/db/vector_db_milvus.py` - Updated result structure
- `src/db/vector_db_weaviate.py` - Updated result structure

---

### P1.3 - Better Error Messages

**Pattern**: Include available options and next steps

**Example Implementation**:

```python
@app.tool()
async def search(database: str, query: str, limit: int = 5, **kwargs) -> str:
    """Search for documents using vector similarity.
    
    📋 Prerequisites (in order):
    1. Database exists: create_database(database='name')
    2. Collection exists: create_collection(database='name', collection='docs')
    3. Documents written: write_documents(database='name', documents=[...])
    
    💡 Search Quality Tips:
    - Use min_similarity=0.7 for high-quality results only
    - Filter by metadata: metadata_filter={'doc_type': 'api', 'version': '2.1'}
    
    🔍 Similarity Score Guide:
    - 0.9-1.0: Excellent match
    - 0.7-0.9: Good match (recommended threshold)
    - 0.5-0.7: Moderate match
    - <0.5: Weak match (consider excluding)
    """
    try:
        db = get_database_by_name(database)
    except KeyError:
        available = list(vector_databases.keys())
        if available:
            return (
                f"❌ Database '{database}' not found.\n\n"
                f"📚 Available databases: {json.dumps(available)}\n\n"
                f"💡 To create it:\n"
                f"   create_database(database='{database}', collection='docs')"
            )
        else:
            return (
                f"❌ No databases exist yet.\n\n"
                f"💡 Create your first database:\n"
                f"   create_database(\n"
                f"       database='{database}',\n"
                f"       collection='docs',\n"
                f"       database_type='milvus',\n"
                f"       embed_model='text-embedding-3-small'\n"
                f"   )"
            )
    
    try:
        results = await db.search(query, limit=limit, **kwargs)
        return json.dumps(results, indent=2)
    except Exception as e:
        return (
            f"❌ Search failed: {str(e)}\n\n"
            f"💡 Common fixes:\n"
            f"   • Check collection: list_collections(database='{database}')\n"
            f"   • Verify documents: count_documents(database='{database}')\n"
            f"   • Check embeddings: get_collection_info(database='{database}')"
        )
```

**Files Modified**:
- `src/maestro_mcp/server.py` - Enhanced error messages in all 24 tools

---

## Priority 2: Production Features

**Goal**: Enable multi-tenant production deployments

### P2.1 - Document-Level Access Control

**Real-World Scenarios**:
- Public marketing docs → everyone
- HR policies → HR team + executives only
- Engineering docs → engineering group
- Personal notes → owner only

**Solution: Metadata-Based Access Control**

#### Access Control Schema

Store access rules in document metadata (leverages existing JSON field):

```json
{
  "url": "https://internal.example.com/hr-handbook.pdf",
  "text": "Employee handbook content...",
  "metadata": {
    "doc_type": "hr_policy",
    "department": "human-resources",
    "author": "hr-team",
    "access_control": {
      "visibility": "private",
      "allowed_users": ["alice@example.com", "bob@example.com"],
      "allowed_groups": ["hr", "executives", "managers"],
      "owner": "hr-team@example.com"
    }
  }
}
```

#### Write Time (Storing Access Rules)

```python
write_documents(
    database="corp-kb",
    documents=[
        {
            "url": "https://internal.example.com/hr-handbook.pdf",
            "metadata": {
                "doc_type": "hr_policy",
                "department": "human-resources",
                "access_control": {
                    "visibility": "private",
                    "allowed_groups": ["hr", "executives", "managers"]
                }
            }
        },
        {
            "url": "https://example.com/public-announcement.pdf",
            "metadata": {
                "doc_type": "announcement",
                "access_control": {
                    "visibility": "public"
                }
            }
        }
    ]
)
```

#### Query Time (Filtering by User)

**Enhanced SearchInput**:

```python
class SearchInput(BaseModel):
    database: str
    query: str
    limit: int = 5
    collection: str | None = None
    min_similarity: float | None = None
    metadata_filter: dict | None = None
    
    # NEW: Access control parameters
    requesting_user: str | None = Field(
        default=None,
        description="Email/ID of user making request. If None, only public documents returned."
    )
    user_groups: list[str] | None = Field(
        default=None,
        description="Groups user belongs to (e.g., ['engineering', 'employees']). "
                    "Used for group-based access control."
    )
```

**Filtering Implementation**:

```python
async def search(self, query, limit=5, requesting_user=None, user_groups=None, **kwargs):
    """Search with access control filtering."""
    # Overfetch to account for access control filtering
    raw_limit = limit * 3
    raw_results = await self._vector_search(query, limit=raw_limit, **kwargs)
    
    # Apply access control filtering
    filtered = []
    for result in raw_results:
        access = result.get("metadata", {}).get("access_control", {})
        visibility = access.get("visibility", "public")
        
        # Public documents: always accessible
        if visibility == "public":
            filtered.append(result)
            continue
        
        # No user specified: skip private/restricted docs
        if not requesting_user:
            continue
        
        # Check user-level access
        allowed_users = access.get("allowed_users", [])
        if requesting_user in allowed_users:
            filtered.append(result)
            continue
        
        # Check group-level access
        allowed_groups = access.get("allowed_groups", [])
        if user_groups and any(g in allowed_groups for g in user_groups):
            filtered.append(result)
            continue
    
    return filtered[:limit]
```

#### Access Control Behavior Table

| Visibility | No User Provided | User (not authorized) | User (authorized) |
|-----------|------------------|----------------------|-------------------|
| `public` | ✅ Show | ✅ Show | ✅ Show |
| `private` | ❌ Hide | ❌ Hide | ✅ Show (if in allowed_users or allowed_groups) |
| `restricted` | ❌ Hide | ❌ Hide | ✅ Show (if in allowed_users or allowed_groups) |

#### Design Rationale

**Why metadata-based?**
- ✅ Flexible: Document-level granularity
- ✅ Simple: Leverages existing JSON metadata field
- ✅ No schema changes required
- ✅ Works with both Milvus and Weaviate

**Why post-search filtering?**
- Vector DBs don't natively support complex ACLs
- Overfetching (3x limit) minimizes performance impact
- Simpler to implement and maintain
- Easier to debug and test

**Why caller provides groups?**
- Keeps server stateless and simple
- Allows flexible external authentication systems
- No need to integrate with LDAP/OAuth/etc.

**Files Modified**:
- `src/maestro_mcp/server.py` - Added `requesting_user` and `user_groups` to SearchInput/QueryInput
- `src/db/vector_db_base.py` - Updated abstract search method signature
- `src/db/vector_db_milvus.py` - Implemented access control filtering
- `src/db/vector_db_weaviate.py` - Implemented access control filtering

---

### P2.2 - Upsert Support

**Problem**: Writing same URL twice creates duplicates. Agents can't safely update documents.

**Solution**: Add upsert parameters to write operations

```python
class WriteDocumentsInput(BaseModel):
    database: str
    documents: list[dict]
    collection: str = "MaestroDocs"
    
    # NEW: Upsert behavior
    upsert_by: str | None = Field(
        default=None,
        description="Field to check for duplicates. Common values: 'url' or 'document_name'. "
                    "If None, always inserts (default behavior)."
    )
    upsert_mode: str = Field(
        default="replace",
        description="How to handle duplicates: 'replace' (update), 'skip' (ignore), 'error' (fail)"
    )
```

**Implementation**:

```python
async def write_documents(self, documents, upsert_by=None, upsert_mode="replace"):
    """Write documents with optional upsert behavior."""
    if not upsert_by:
        # Original behavior: always insert
        return await self._bulk_insert(documents)
    
    results = {"written": 0, "updated": 0, "skipped": 0, "errors": []}
    
    for doc in documents:
        # Get identifier value
        identifier = doc.get(upsert_by) or doc.get("metadata", {}).get(upsert_by)
        if not identifier:
            results["errors"].append(f"Document missing '{upsert_by}' field")
            continue
        
        # Check if document exists
        existing_chunks = await self._find_chunks_by_identifier(upsert_by, identifier)
        
        if existing_chunks:
            if upsert_mode == "skip":
                results["skipped"] += 1
            elif upsert_mode == "error":
                results["errors"].append(f"Duplicate found: {identifier}")
            else:  # replace
                # Delete old chunks
                chunk_ids = [c["id"] for c in existing_chunks]
                await self.delete_documents(chunk_ids)
                # Insert new version
                await self._insert_document(doc)
                results["updated"] += 1
        else:
            await self._insert_document(doc)
            results["written"] += 1
    
    return results
```

**Helper Method**:

```python
async def _find_chunks_by_identifier(self, field: str, value: str) -> list:
    """Find all chunks where metadata[field] == value."""
    # Milvus: use filter expression
    # filter=f'metadata["{field}"] == "{value}"'
    
    # Weaviate: use where filter
    # where filter with metadata contains
    pass
```

**Add Document Fingerprinting**:

```python
import hashlib

def _add_fingerprint(self, doc: dict) -> dict:
    """Add SHA256 hash of original text for external tracking."""
    if "text" in doc:
        text_hash = hashlib.sha256(doc["text"].encode()).hexdigest()
        if "metadata" not in doc:
            doc["metadata"] = {}
        doc["metadata"]["content_fingerprint"] = text_hash
    return doc
```

**Files Modified**:
- `src/maestro_mcp/server.py` - Added upsert parameters to write tools
- `src/db/vector_db_base.py` - Added `_find_chunks_by_identifier()` and `_add_fingerprint()`
- `src/db/vector_db_milvus.py` - Implemented upsert logic
- `src/db/vector_db_weaviate.py` - Implemented upsert logic

---

## Priority 3: Polish

**Goal**: Nice-to-have improvements for completeness

### P3.1 - Delete by Name

Add convenience tool for deleting by document name:

```python
@app.tool()
async def delete_document_by_name(
    database: str,
    document_name: str,
    collection: str | None = None
) -> str:
    """Delete document by its name (easier than finding internal ID).
    
    More convenient than delete_document which requires the internal chunk ID.
    """
    db = get_database_by_name(database)
    chunks = await db.get_document_chunks(document_name, collection)
    
    if not chunks:
        return f"❌ No document found with name '{document_name}'"
    
    chunk_ids = [c["id"] for c in chunks]
    await db.delete_documents(chunk_ids)
    
    return f"✅ Deleted document '{document_name}' ({len(chunk_ids)} chunks)"
```

### P3.2 - Document Exists Check

```python
@app.tool()
async def document_exists(
    database: str,
    document_name: str,
    collection: str | None = None
) -> str:
    """Check if document exists (useful before upsert operations)."""
    db = get_database_by_name(database)
    chunks = await db.get_document_chunks(document_name, collection)
    
    return json.dumps({
        "exists": len(chunks) > 0,
        "document_name": document_name,
        "chunk_count": len(chunks)
    })
```

### P3.3 - List Metadata Fields

```python
@app.tool()
async def list_metadata_fields(
    database: str,
    collection: str | None = None,
    limit: int = 100
) -> str:
    """Discover available metadata fields (useful for metadata_filter)."""
    db = get_database_by_name(database)
    docs = await db.list_documents(limit=limit, collection=collection)
    
    # Collect all metadata keys and sample values
    fields = {}
    for doc in docs:
        metadata = doc.get("metadata", {})
        for key, value in metadata.items():
            if key == "access_control":
                continue  # Skip internal field
            if key not in fields:
                fields[key] = {"type": type(value).__name__, "examples": []}
            if len(fields[key]["examples"]) < 3 and value not in fields[key]["examples"]:
                fields[key]["examples"].append(value)
    
    return json.dumps(fields, indent=2)
```

### P3.4 - Enhanced Collection Stats

```python
@app.tool()
async def get_collection_stats(
    database: str,
    collection: str | None = None
) -> str:
    """Get detailed statistics about a collection."""
    db = get_database_by_name(database)
    
    stats = {
        "collection_name": collection or db.collection_name,
        "document_count": await db.count_documents(),
        "embedding_model": db.embedding_model,
        "chunking_strategy": db.chunking_config.strategy if db.chunking_config else "none",
    }
    
    # Sample documents for metadata analysis
    sample_docs = await db.list_documents(limit=10)
    if sample_docs:
        metadata_fields = set()
        for doc in sample_docs:
            metadata_fields.update(doc.get("metadata", {}).keys())
        stats["common_metadata_fields"] = sorted(metadata_fields)
    
    return json.dumps(stats, indent=2)
```

**Files Modified**:
- `src/maestro_mcp/server.py` - Added 4 new helper tools

---

## Implementation Roadmap

### Phase 1: Critical Fixes (Week 1) - P0

**Deliverable**: Agents can successfully use all tools

**Tasks**:
- [ ] Create dual-port architecture
  - [ ] Refactor 24 tools to flat parameters
  - [ ] Rename parameters (db_name→database, etc.)
  - [ ] Create compatibility proxy for port 8030
  - [ ] Update start.sh for dual-port launch
  - [ ] Update Dockerfile to expose both ports
- [ ] Fix reassembly bug
  - [ ] Update `_reassemble_chunks_into_document()` in vector_db_base.py
  - [ ] Add tests for overlap handling
- [ ] Test with kagent/Granite4
  - [ ] Verify flat format works on port 8031
  - [ ] Verify proxy translation works on port 8030

**Success Criteria**:
- ✅ All 24 tools callable from agents
- ✅ Both ports functional
- ✅ Reassembly produces correct text with overlap
- ✅ Parameter naming clear and consistent

---

### Phase 2: Search Enhancements (Week 2) - P1

**Deliverable**: High-quality, well-attributed search results

**Tasks**:
- [ ] Add quality controls
  - [ ] Add `min_similarity` parameter to search/query
  - [ ] Add `metadata_filter` parameter to search/query
  - [ ] Implement filtering in Milvus backend
  - [ ] Implement filtering in Weaviate backend
- [ ] Improve citations
  - [ ] Separate system vs user metadata
  - [ ] Add `get_citations` tool
  - [ ] Add `group_by_document` option
- [ ] Better errors
  - [ ] Enhanced error messages with available options
  - [ ] Add workflow prerequisites to all docstrings
  - [ ] Add similarity score interpretation guide

**Success Criteria**:
- ✅ Can filter search results by quality threshold
- ✅ Can filter by metadata fields
- ✅ Citations easy to extract
- ✅ Error messages actionable

---

### Phase 3: Production Features (Week 3) - P2

**Deliverable**: Production-ready multi-tenant system

**Tasks**:
- [ ] Access control
  - [ ] Add `requesting_user` and `user_groups` parameters
  - [ ] Implement access control filtering in Milvus
  - [ ] Implement access control filtering in Weaviate
  - [ ] Document access control schema
- [ ] Upsert support
  - [ ] Add `upsert_by` and `upsert_mode` parameters
  - [ ] Implement `_find_chunks_by_identifier()` helper
  - [ ] Add document fingerprinting
  - [ ] Return detailed write stats

**Success Criteria**:
- ✅ Can filter documents by user/group
- ✅ Public/private/restricted visibility works
- ✅ Upsert prevents duplicates
- ✅ Can update existing documents

---

### Phase 4: Polish (Week 4) - P3

**Deliverable**: Fully polished API

**Tasks**:
- [ ] Convenience tools
  - [ ] Add `delete_document_by_name`
  - [ ] Add `document_exists`
  - [ ] Add `list_metadata_fields`
  - [ ] Add `get_collection_stats`

**Success Criteria**:
- ✅ All convenience tools implemented
- ✅ Agents have full discovery capabilities

---

## Testing Strategy

### Test Matrix: Compatibility

Test all parameter format combinations:

| Port | Format | Parameters | Expected |
|------|--------|-----------|----------|
| 8030 | Nested `{"input": {...}}` | Old (`db_name`) | ✅ Works (translated) |
| 8030 | Nested | New (`database`) | ✅ Works |
| 8031 | Flat `{...}` | New (`database`) | ✅ Works (primary) |
| 8031 | Flat | Old (`db_name`) | ❌ Error (migration needed) |

### Test Cases: Access Control

- [ ] Public docs visible to everyone (with/without user)
- [ ] Private docs hidden when no user provided
- [ ] Private docs visible to allowed users
- [ ] Private docs visible to users in allowed groups
- [ ] Private docs hidden from unauthorized users
- [ ] Multiple groups work correctly (OR logic)
- [ ] Owner always has access

### Test Cases: Data Integrity

- [ ] Reassembly with overlap=0 (no change expected)
- [ ] Reassembly with overlap=50 (deduplicated correctly)
- [ ] Reassembly with overlap=100 (deduplicated correctly)
- [ ] All chunking strategies: Fixed, Sentence, Semantic, None
- [ ] Missing offset metadata falls back gracefully

### Test Cases: Upsert

- [ ] `upsert_by=None` always inserts (default)
- [ ] `upsert_by="url"` + `mode="replace"` updates existing
- [ ] `upsert_by="url"` + `mode="skip"` ignores duplicates
- [ ] `upsert_by="url"` + `mode="error"` fails on duplicates
- [ ] Returns accurate stats (written/updated/skipped/errors)

### Test Cases: Search Quality

- [ ] `min_similarity=0.7` filters low-quality results
- [ ] `metadata_filter={'doc_type': 'security'}` works
- [ ] Multiple metadata filters work (AND logic)
- [ ] Empty results when no matches above threshold

### E2E Test Updates

Files to update:
- `tests/e2e/common.py` - Add fixture for port 8031
- `tests/e2e/test_mcp_milvus_e2e.py` - Test both ports
- `tests/e2e/test_mcp_weaviate_e2e.py` - Test both ports
- `tests/e2e/test_functions.py` - Update parameter names
- `tests/e2e/test_functions_simple.py` - Update parameter names
- `tests/e2e/test_compatibility_proxy.py` - NEW (test proxy translation)
- `tests/e2e/test_search_enhancements.py` - NEW (test quality controls)
- `tests/test_reassembly_fix.py` - NEW (test overlap handling)
- `tests/test_access_control.py` - NEW (test ACL filtering)
- `tests/test_upsert.py` - NEW (test upsert modes)

---

## Backward Compatibility

### Port 8030 (Legacy)

**Guarantees**:
- ✅ Nested `{"input": {...}}` format continues working indefinitely
- ✅ Old parameter names (`db_name`, `collection_name`) automatically translated
- ✅ All existing clients unaffected
- ✅ No breaking changes to existing workflows

**Migration Support**:
- Every request to port 8030 logged (for tracking adoption)
- No forced migration timeline (community is small)
- Documentation clearly marks port 8031 as recommended

### Port 8031 (Primary)

**Features**:
- ✅ Flat `{...}` format for agents
- ✅ New parameter names (`database`, `collection`)
- ✅ All new features available first
- ✅ Cleaner, more intuitive API
- ✅ Recommended for all new integrations

### Migration Strategy

**For users**:
1. Deploy new version (both ports available)
2. Test new format on port 8031 at your convenience
3. Update clients when ready (no deadline)
4. Continue using port 8030 as long as needed

**For maintainers**:
1. Monitor proxy logs to track adoption
2. After sufficient adoption, consider deprecation (but no rush given small community)
3. Provide advance notice before any removal

---

## Open Questions & Decisions

### Q1: Access Control Enforcement Point

**Question**: Should access control be enforced at search time only, or also at write time?

**Decision**: **Search time only** (keep it simple)

**Rationale**:
- ✅ Simpler implementation
- ✅ More flexible (users control who writes what via application logic)
- ✅ Vector DBs handle storage, application handles authorization
- ✅ Easier to test and debug

### Q2: Default Visibility

**Question**: What should be the default visibility for documents without `access_control` metadata?

**Decision**: **Public** (accessible to everyone)

**Rationale**:
- ✅ Backward compatible (existing documents remain accessible)
- ✅ Safe default for most use cases
- ✅ Explicit opt-in for sensitive data (mark as `private`)
- ✅ Matches common expectations

### Q3: User Group Resolution

**Question**: How should user→groups mapping be resolved?

**Decision**: **Caller's responsibility** (pass `user_groups` explicitly)

**Rationale**:
- ✅ Keeps server stateless and simple
- ✅ Allows flexible external authentication (LDAP, OAuth, custom)
- ✅ No need to integrate with specific auth systems
- ✅ Caller has full control over group membership

### Q4: Deprecation Timeline

**Question**: When should port 8030 be deprecated?

**Decision**: **No specific timeline** (small community, no pressure)

**Rationale**:
- ✅ Community is small, no urgent need to deprecate
- ✅ Maintenance burden is low (simple proxy)
- ✅ Better to support users indefinitely than force migration
- ✅ Can reevaluate if adoption metrics show clear preference for 8031

### Q5: Access Control Schema Validation

**Question**: Should we validate `access_control` metadata structure at write time?

**Decision**: **No** (keep it flexible)

**Rationale**:
- ✅ Flexible: Schema can evolve without breaking changes
- ✅ Simple: No validation logic needed
- ✅ Graceful: Invalid access_control simply treated as public
- ✅ Can warn at query time if malformed (non-blocking)

---

## Documentation Updates

### For Agents (LLM-Readable)

Files to update:
- All tool docstrings in `src/maestro_mcp/server.py`
  - Add workflow prerequisites ("Step 1: Create database, Step 2: ...")
  - Add similarity score interpretation (0.9-1.0 excellent, 0.7-0.9 good, etc.)
  - Document metadata_filter syntax with examples
  - Add access control examples
  - Explain upsert modes

### For Humans (Developers)

Files to create/update:
- `README.md` - Add dual-port explanation and quick start
- `docs/MIGRATION_GUIDE.md` - NEW (old→new format)
- `docs/ACCESS_CONTROL.md` - NEW (design and examples)
- `docs/API_REFERENCE.md` - NEW (comprehensive API docs)
- `docs/LLM_BEST_PRACTICES.md` - NEW (guide for agent developers)
- `src/maestro_mcp/README.md` - Update with all changes

### Architecture Diagrams

Add visual explanations:
- Dual-port architecture diagram
- Access control decision tree
- Search quality filtering flow
- Parameter translation mapping

---

## File Summary

### Files Modified (Existing)

**Core Server**:
- `src/maestro_mcp/server.py` - All 24 tools refactored
- `src/db/vector_db_base.py` - Fixed reassembly, added ACL support
- `src/db/vector_db_milvus.py` - Quality controls, ACL, upsert
- `src/db/vector_db_weaviate.py` - Quality controls, ACL, upsert

**Deployment**:
- `start.sh` - Dual-port launch
- `Dockerfile` - Expose both ports

**Tests**:
- `tests/e2e/common.py` - Add port 8031 fixture
- `tests/e2e/test_mcp_milvus_e2e.py` - Update parameters
- `tests/e2e/test_mcp_weaviate_e2e.py` - Update parameters
- `tests/e2e/test_functions.py` - Update parameters
- `tests/e2e/test_functions_simple.py` - Update parameters

### Files Created (New)

**Server**:
- `src/maestro_mcp/compatibility_proxy.py` - Port 8030 proxy
- `src/maestro_mcp/parameter_translation.py` - Translation map

**Tests**:
- `tests/e2e/test_compatibility_proxy.py` - Proxy tests
- `tests/e2e/test_search_enhancements.py` - Quality control tests
- `tests/test_reassembly_fix.py` - Overlap handling tests
- `tests/test_access_control.py` - ACL tests
- `tests/test_upsert.py` - Upsert tests

**Documentation**:
- `docs/MIGRATION_GUIDE.md` - Migration instructions
- `docs/ACCESS_CONTROL.md` - ACL design and examples
- `docs/API_REFERENCE.md` - Comprehensive API docs
- `docs/LLM_BEST_PRACTICES.md` - Guide for agent developers

---

## Success Metrics

### Phase 1 (P0) Success

- ✅ kagent/Granite4 can successfully call all 24 tools
- ✅ Zero breaking changes to existing clients
- ✅ Text reassembly correct with all overlap values
- ✅ Both ports operational

### Phase 2 (P1) Success

- ✅ Can filter search results by similarity threshold
- ✅ Can filter by metadata fields
- ✅ Citation extraction is straightforward
- ✅ Error messages lead to successful recovery

### Phase 3 (P2) Success

- ✅ Multi-tenant RAG deployments possible
- ✅ Private/public document separation works
- ✅ Documents can be safely updated (upsert)
- ✅ Production-ready security

### Phase 4 (P3) Success

- ✅ All convenience tools available
- ✅ Full metadata discovery
- ✅ Comprehensive statistics

### Overall Success

- ✅ Agents use server confidently without human intervention
- ✅ Search results are high-quality and well-attributed
- ✅ Production deployments with sensitive data are safe
- ✅ 100% backward compatibility maintained
- ✅ Community adoption of new format

---

## Appendix: Parameter Rename Reference

Complete mapping for all affected models:

| Model | Old Parameters | New Parameters |
|-------|---------------|----------------|
| CreateVectorDatabaseInput | `db_name`, `collection_name`, `type` | `database`, `collection`, `database_type` |
| SetupDatabaseInput | `db_name`, `embedding` | `database`, `embed_model` |
| GetSupportedEmbeddingsInput | `db_name` | `database` |
| WriteDocumentsInput | `db_name`, `embedding` | `database`, `embed_model` |
| WriteDocumentInput | `db_name`, `collection_name`, `embedding` | `database`, `collection`, `embed_model` |
| WriteDocumentToCollectionInput | `db_name`, `collection_name`, `doc_name`, `embedding` | `database`, `collection`, `document_name`, `embed_model` |
| ListDocumentsInput | `db_name` | `database` |
| ListDocumentsInCollectionInput | `db_name`, `collection_name` | `database`, `collection` |
| CountDocumentsInput | `db_name` | `database` |
| DeleteDocumentsInput | `db_name`, `document_ids` | `database`, `document_ids` (no change) |
| DeleteDocumentInput | `db_name` | `database` |
| DeleteDocumentFromCollectionInput | `db_name`, `collection_name`, `doc_name` | `database`, `collection`, `document_name` |
| GetDocumentInput | `db_name`, `collection_name`, `doc_name` | `database`, `collection`, `document_name` |
| DeleteCollectionInput | `db_name`, `collection_name` | `database`, `collection` |
| CleanupInput | `db_name` | `database` |
| GetDatabaseInfoInput | `db_name` | `database` |
| ListCollectionsInput | `db_name` | `database` |
| GetCollectionInfoInput | `db_name`, `collection_name` | `database`, `collection` |
| CreateCollectionInput | `db_name`, `collection_name`, `embedding` | `database`, `collection`, `embed_model` |
| QueryInput | `db_name`, `collection_name` | `database`, `collection` |
| SearchInput | `db_name`, `collection_name` | `database`, `collection` |
