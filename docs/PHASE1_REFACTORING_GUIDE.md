# Phase 1 Refactoring Guide: Tool-by-Tool Transformations

## Quick Reference

This guide provides exact transformations for each of the 24 tool functions in `src/maestro_mcp/server.py`.

## Transformation Pattern

### General Pattern
```python
# BEFORE
class XxxInput(BaseModel):
    param1: type = Field(..., description="desc1")
    param2: type = Field(default=value, description="desc2")

@app.tool()
async def tool_name(input: XxxInput) -> str:
    value1 = input.param1
    value2 = input.param2
    # ... implementation

# AFTER
@app.tool()
async def tool_name(
    param1: type = Field(..., description="desc1"),
    param2: type = Field(default=value, description="desc2")
) -> str:
    # Use param1, param2 directly
    # ... implementation
```

## Tool Transformations

### 1. create_vector_database_tool (Line 654)

**Input Class to Remove** (lines 398-409):
```python
class CreateVectorDatabaseInput(BaseModel):
    db_name: str = Field(..., description="Unique name for the vector database instance")
    db_type: str = Field(..., description="Type of vector database to create", json_schema_extra={"enum": ["weaviate", "milvus"]})
    collection_name: str = Field(default="MaestroDocs", description="Name of the collection to use")
```

**New Function Signature**:
```python
@app.tool()
async def create_vector_database_tool(
    database: str = Field(..., description="Unique name for the vector database instance"),
    database_type: str = Field(..., description="Type of vector database to create", json_schema_extra={"enum": ["weaviate", "milvus"]}),
    collection: str = Field(default="MaestroDocs", description="Name of the collection to use")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.db_type` → `database_type`
- `input.collection_name` → `collection`

---

### 2. setup_database (Line 686)

**Input Class to Remove** (lines 412-418):
```python
class SetupDatabaseInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance to set up")
    embedding: str = Field(default="default", description="Embedding model to use for the collection")
```

**New Function Signature**:
```python
@app.tool()
async def setup_database(
    database: str = Field(..., description="Name of the vector database instance to set up"),
    embedding: str = Field(default="default", description="Embedding model to use for the collection")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.embedding` → `embedding`

---

### 3. get_supported_embeddings (Line 721)

**Input Class to Remove** (lines 421-422):
```python
class GetSupportedEmbeddingsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
```

**New Function Signature**:
```python
@app.tool()
async def get_supported_embeddings(
    database: str = Field(..., description="Name of the vector database instance")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`

---

### 4. get_supported_chunking_strategies (Line 729)

**No changes needed** - Already has no input parameter.

---

### 5. write_documents (Line 785)

**Input Class to Remove** (lines 425-451):
```python
class WriteDocumentsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    documents: list[dict[str, Any]] = Field(..., description="...")
    embedding: str = Field(default="default", description="(DEPRECATED) Embedding strategy to use; ignored at write time")
```

**New Function Signature**:
```python
@app.tool()
async def write_documents(
    database: str = Field(..., description="Name of the vector database instance"),
    documents: list[dict[str, Any]] = Field(
        ...,
        description=(
            "List of documents to write. Each document is a dict with:\n"
            "- 'url' (required): Document identifier or URL to fetch from\n"
            "- 'text' (optional): Direct text content (backwards compatible)\n"
            "- 'metadata' (optional): Additional metadata dict\n\n"
            "URL Fetching: If 'url' starts with http:// or https://, the system will:\n"
            "1. Fetch the content from the URL\n"
            "2. Auto-detect format (HTML, PDF, Markdown, Text)\n"
            "3. Convert to plain text\n"
            "4. Enrich metadata with fetch details\n\n"
            "Supported formats: HTML (converted via html2text), PDF (requires PyPDF2), "
            "Markdown (.md), Plain text (.txt)\n\n"
            "Security: Only HTTP/HTTPS URLs allowed. File paths (file://) restricted to "
            "current working directory and subdirectories.\n\n"
            "Backwards Compatible: Providing 'text' directly still works. If both 'url' and 'text' "
            "are provided, 'text' takes precedence (no fetching occurs)."
        ),
    ),
    embedding: str = Field(
        default="default",
        description="(DEPRECATED) Embedding strategy to use; ignored at write time",
    )
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.documents` → `documents`
- `input.embedding` → `embedding`

---

### 6. write_document (Line 913)

**Input Class to Remove** (lines 454-469):
```python
class WriteDocumentInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    url: str = Field(..., description="URL of the document")
    text: str = Field(..., description="Text content of the document")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the document")
    vector: list[float] | None = Field(default=None, description="Pre-computed vector embedding (optional, for Milvus)")
    embedding: str = Field(default="default", description="(DEPRECATED) Embedding strategy to use; ignored at write time")
```

**New Function Signature**:
```python
@app.tool()
async def write_document(
    database: str = Field(..., description="Name of the vector database instance"),
    url: str = Field(..., description="URL of the document"),
    text: str = Field(..., description="Text content of the document"),
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the document"),
    vector: list[float] | None = Field(default=None, description="Pre-computed vector embedding (optional, for Milvus)"),
    embedding: str = Field(default="default", description="(DEPRECATED) Embedding strategy to use; ignored at write time")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.url` → `url`
- `input.text` → `text`
- `input.metadata` → `metadata`
- `input.vector` → `vector`
- `input.embedding` → `embedding`

---

### 7. write_document_to_collection (Line 1016)

**Input Class to Remove** (lines 472-489):
```python
class WriteDocumentToCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(..., description="Name of the collection to write to")
    doc_name: str = Field(..., description="Name of the document")
    text: str = Field(..., description="Text content of the document")
    url: str = Field(..., description="URL of the document")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the document")
    vector: list[float] | None = Field(default=None, description="Pre-computed vector embedding (optional, for Milvus)")
    embedding: str = Field(default="default", description="(DEPRECATED) Embedding strategy to use; ignored at write time")
```

**New Function Signature**:
```python
@app.tool()
async def write_document_to_collection(
    database: str = Field(..., description="Name of the vector database instance"),
    collection: str = Field(..., description="Name of the collection to write to"),
    document_name: str = Field(..., description="Name of the document"),
    text: str = Field(..., description="Text content of the document"),
    url: str = Field(..., description="URL of the document"),
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the document"),
    vector: list[float] | None = Field(default=None, description="Pre-computed vector embedding (optional, for Milvus)"),
    embedding: str = Field(default="default", description="(DEPRECATED) Embedding strategy to use; ignored at write time")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.collection_name` → `collection`
- `input.doc_name` → `document_name`
- `input.text` → `text`
- `input.url` → `url`
- `input.metadata` → `metadata`
- `input.vector` → `vector`
- `input.embedding` → `embedding`

---

### 8. list_documents (Line 1118)

**Input Class to Remove** (lines 492-495):
```python
class ListDocumentsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    limit: int = Field(default=10, description="Maximum number of documents to return")
    offset: int = Field(default=0, description="Number of documents to skip")
```

**New Function Signature**:
```python
@app.tool()
async def list_documents(
    database: str = Field(..., description="Name of the vector database instance"),
    limit: int = Field(default=10, description="Maximum number of documents to return"),
    offset: int = Field(default=0, description="Number of documents to skip")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.limit` → `limit`
- `input.offset` → `offset`

---

### 9. list_documents_in_collection (Line 1135)

**Input Class to Remove** (lines 498-504):
```python
class ListDocumentsInCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(..., description="Name of the collection to list documents from")
    limit: int = Field(default=10, description="Maximum number of documents to return")
    offset: int = Field(default=0, description="Number of documents to skip")
```

**New Function Signature**:
```python
@app.tool()
async def list_documents_in_collection(
    database: str = Field(..., description="Name of the vector database instance"),
    collection: str = Field(..., description="Name of the collection to list documents from"),
    limit: int = Field(default=10, description="Maximum number of documents to return"),
    offset: int = Field(default=0, description="Number of documents to skip")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.collection_name` → `collection`
- `input.limit` → `limit`
- `input.offset` → `offset`

---

### 10. count_documents (Line 1172)

**Input Class to Remove** (lines 507-508):
```python
class CountDocumentsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
```

**New Function Signature**:
```python
@app.tool()
async def count_documents(
    database: str = Field(..., description="Name of the vector database instance")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`

---

### 11. delete_documents (Line 1183)

**Input Class to Remove** (lines 511-513):
```python
class DeleteDocumentsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    document_ids: list[str] = Field(..., description="List of document IDs to delete")
```

**New Function Signature**:
```python
@app.tool()
async def delete_documents(
    database: str = Field(..., description="Name of the vector database instance"),
    document_ids: list[str] = Field(..., description="List of document IDs to delete")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.document_ids` → `document_ids`

---

### 12. delete_document (Line 1195)

**Input Class to Remove** (lines 516-518):
```python
class DeleteDocumentInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    document_id: str = Field(..., description="Document ID to delete")
```

**New Function Signature**:
```python
@app.tool()
async def delete_document(
    database: str = Field(..., description="Name of the vector database instance"),
    document_id: str = Field(..., description="Document ID to delete")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.document_id` → `document_id`

---

### 13. delete_document_from_collection (Line 1207)

**Input Class to Remove** (lines 521-526):
```python
class DeleteDocumentFromCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(..., description="Name of the collection containing the document")
    doc_name: str = Field(..., description="Name of the document to delete")
```

**New Function Signature**:
```python
@app.tool()
async def delete_document_from_collection(
    database: str = Field(..., description="Name of the vector database instance"),
    collection: str = Field(..., description="Name of the collection containing the document"),
    document_name: str = Field(..., description="Name of the document to delete")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.collection_name` → `collection`
- `input.doc_name` → `document_name`

---

### 14. get_document (Line 1268)

**Input Class to Remove** (lines 529-534):
```python
class GetDocumentInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(..., description="Name of the collection containing the document")
    doc_name: str = Field(..., description="Name of the document to retrieve")
```

**New Function Signature**:
```python
@app.tool()
async def get_document(
    database: str = Field(..., description="Name of the vector database instance"),
    collection: str = Field(..., description="Name of the collection containing the document"),
    document_name: str = Field(..., description="Name of the document to retrieve")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.collection_name` → `collection`
- `input.doc_name` → `document_name`

---

### 15. delete_collection (Line 1304)

**Input Class to Remove** (lines 537-541):
```python
class DeleteCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str | None = Field(default=None, description="Name of the collection to delete")
```

**New Function Signature**:
```python
@app.tool()
async def delete_collection(
    database: str = Field(..., description="Name of the vector database instance"),
    collection: str | None = Field(default=None, description="Name of the collection to delete")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.collection_name` → `collection`

---

### 16. cleanup (Line 1356)

**Input Class to Remove** (lines 544-547):
```python
class CleanupInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance to clean up")
```

**New Function Signature**:
```python
@app.tool()
async def cleanup(
    database: str = Field(..., description="Name of the vector database instance to clean up")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`

---

### 17. get_database_info (Line 1385)

**Input Class to Remove** (lines 550-551):
```python
class GetDatabaseInfoInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
```

**New Function Signature**:
```python
@app.tool()
async def get_database_info(
    database: str = Field(..., description="Name of the vector database instance")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`

---

### 18. list_collections (Line 1404)

**Input Class to Remove** (lines 554-555):
```python
class ListCollectionsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
```

**New Function Signature**:
```python
@app.tool()
async def list_collections(
    database: str = Field(..., description="Name of the vector database instance")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`

---

### 19. get_collection_info (Line 1420)

**Input Class to Remove** (lines 558-563):
```python
class GetCollectionInfoInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str | None = Field(default=None, description="Name of the collection to get info for. If not provided, uses the default collection.")
```

**New Function Signature**:
```python
@app.tool()
async def get_collection_info(
    database: str = Field(..., description="Name of the vector database instance"),
    collection: str | None = Field(default=None, description="Name of the collection to get info for. If not provided, uses the default collection.")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.collection_name` → `collection`

---

### 20. create_collection (Line 1447)

**Input Class to Remove** (lines 566-575):
```python
class CreateCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(..., description="Name of the collection to create")
    embedding: str = Field(default="default", description="Embedding model to use for the collection")
    chunking_config: dict[str, Any] | None = Field(default=None, description="Optional chunking configuration for the collection. Example: {'strategy':'Sentence','parameters':{'chunk_size':256,'overlap':1}}")
```

**New Function Signature**:
```python
@app.tool()
async def create_collection(
    database: str = Field(..., description="Name of the vector database instance"),
    collection: str = Field(..., description="Name of the collection to create"),
    embedding: str = Field(default="default", description="Embedding model to use for the collection"),
    chunking_config: dict[str, Any] | None = Field(default=None, description="Optional chunking configuration for the collection. Example: {'strategy':'Sentence','parameters':{'chunk_size':256,'overlap':1}}")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.collection_name` → `collection`
- `input.embedding` → `embedding`
- `input.chunking_config` → `chunking_config`

---

### 21. query (Line 1530)

**Input Class to Remove** (lines 578-584):
```python
class QueryInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    query: str = Field(..., description="The query string to search for")
    limit: int = Field(default=5, description="Maximum number of results to consider")
    collection_name: str | None = Field(default=None, description="Optional collection name to search in")
```

**New Function Signature**:
```python
@app.tool()
async def query(
    database: str = Field(..., description="Name of the vector database instance"),
    query: str = Field(..., description="The query string to search for"),
    limit: int = Field(default=5, description="Maximum number of results to consider"),
    collection: str | None = Field(default=None, description="Optional collection name to search in")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.query` → `query`
- `input.limit` → `limit`
- `input.collection_name` → `collection`

---

### 22. search (Line 1550)

**Input Class to Remove** (lines 587-593):
```python
class SearchInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    query: str = Field(..., description="The query string to search for")
    limit: int = Field(default=5, description="Maximum number of results to consider")
    collection_name: str | None = Field(default=None, description="Optional collection name to search in")
```

**New Function Signature**:
```python
@app.tool()
async def search(
    database: str = Field(..., description="Name of the vector database instance"),
    query: str = Field(..., description="The query string to search for"),
    limit: int = Field(default=5, description="Maximum number of results to consider"),
    collection: str | None = Field(default=None, description="Optional collection name to search in")
) -> str:
```

**Body Changes**:
- `input.db_name` → `database`
- `input.query` → `query`
- `input.limit` → `limit`
- `input.collection_name` → `collection`

---

### 23. list_databases (Line 1570)

**No changes needed** - Already has no input parameter.

---

### 24. resync_databases_tool (Line 1601)

**No changes needed** - Already has no input parameter.

---

## Helper Function Updates

### get_database_by_name (Line 388)

This helper function is used throughout. After refactoring, calls will change from:
```python
db = get_database_by_name(input.db_name)
```

To:
```python
db = get_database_by_name(database)
```

## Summary

- **21 Input classes** to remove (lines 398-593)
- **22 tool functions** to refactor (2 already have no params)
- **Parameter renames**: `db_name` → `database`, `db_type` → `database_type`, `collection_name` → `collection`, `doc_name` → `document_name`
- **All Field() attributes** must be preserved
- **All docstrings** must be preserved