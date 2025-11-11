# Access Control Feature Design (Phases 9-10)

**Status**: PLANNED - Future feature
**Target**: Post-Phase 8 (after documentation complete)

## Overview

This document describes the planned access control features for Maestro Knowledge, extracted from the main refactoring plan. These are future enhancements, not part of the current migration.

## Phase 9: Add Ownership Metadata

### Objective
Add ownership tracking to documents and collections without enforcing access control.

### Design

#### Document-Level Ownership
```python
# Metadata structure
{
    "doc_name": "my_document",
    "owner": "user@example.com",  # NEW
    "created_by": "user@example.com",  # NEW
    "created_at": "2025-01-11T10:00:00Z",  # NEW
    # ... other metadata
}
```

#### Collection-Level Ownership
```python
# Collection metadata
{
    "collection_name": "my_collection",
    "owner": "user@example.com",  # NEW
    "created_by": "user@example.com",  # NEW
    "created_at": "2025-01-11T10:00:00Z",  # NEW
    "embedding": "text-embedding-3-small",
    # ... other metadata
}
```

### Implementation Steps

1. **Add owner parameter to write operations**
   - `write_documents(database, documents, owner="user@example.com")`
   - `write_document(database, url, text, owner="user@example.com")`
   - `write_document_to_collection(database, collection, document_name, text, url, owner="user@example.com")`

2. **Add owner to collection creation**
   - `create_collection(database, collection, embedding, owner="user@example.com")`

3. **Store ownership metadata**
   - Milvus: Add to document metadata fields
   - Weaviate: Add to object properties

4. **Update list operations to show ownership**
   - `list_documents()` includes owner in results
   - `list_collections()` includes owner in results

### Migration Impact
- **Breaking**: NO - owner parameter is optional
- **Backward Compatible**: YES - defaults to "system" if not provided

---

## Phase 10: Implement Access Control

### Objective
Enforce access control based on ownership and permissions.

### Access Control Schema

```python
# Document access control
{
    "owner": "user@example.com",
    "visibility": "private" | "shared" | "public",
    "shared_with": ["user2@example.com", "user3@example.com"],  # For "shared"
    "permissions": {
        "read": ["user2@example.com"],
        "write": ["owner"],
        "delete": ["owner"]
    }
}
```

### Access Levels

| Visibility | Owner | Shared Users | Public |
|------------|-------|--------------|--------|
| `private` | Full access | No access | No access |
| `shared` | Full access | Read access | No access |
| `public` | Full access | Read access | Read access |

### Implementation Steps

1. **Add user parameter to query/search operations**
   ```python
   query(database, query, limit, user="user@example.com")
   search(database, query, limit, user="user@example.com")
   ```

2. **Implement access filtering**
   - Filter results based on user's permissions
   - Apply at database query level (not post-processing)

3. **Add permission checks to write/delete operations**
   - Verify user has write permission before allowing modifications
   - Verify user has delete permission before allowing deletions

4. **Milvus implementation**
   ```python
   # Filter expression for access control
   filter_expr = (
       f'owner == "{user}" OR '
       f'visibility == "public" OR '
       f'(visibility == "shared" AND "{user}" in shared_with)'
   )
   ```

5. **Weaviate implementation**
   ```python
   # Where filter for access control
   where_filter = {
       "operator": "Or",
       "operands": [
           {"path": ["owner"], "operator": "Equal", "valueText": user},
           {"path": ["visibility"], "operator": "Equal", "valueText": "public"},
           {
               "operator": "And",
               "operands": [
                   {"path": ["visibility"], "operator": "Equal", "valueText": "shared"},
                   {"path": ["shared_with"], "operator": "ContainsAny", "valueText": [user]}
               ]
           }
       ]
   }
   ```

### Error Messages

```python
# Access denied
"Access denied: You do not have permission to access document 'doc_name' in collection 'collection_name'."

# Insufficient permissions
"Insufficient permissions: You need 'write' permission to modify document 'doc_name'."

# Owner-only operation
"Owner-only operation: Only the owner can delete collection 'collection_name'."
```

### Migration Impact
- **Breaking**: NO - user parameter is optional
- **Backward Compatible**: YES - defaults to "system" user with full access
- **Default Behavior**: If no user specified, access control is not enforced

---

## Design Rationale

### Why Two Phases?

**Phase 9 (Ownership):**
- Establishes data model without enforcement
- Allows gradual adoption
- No breaking changes
- Users can start tracking ownership

**Phase 10 (Access Control):**
- Adds enforcement layer
- Requires user authentication integration
- More complex implementation
- Can be adopted when needed

### Default Visibility

**Decision**: Default to `"public"` for backward compatibility

**Rationale:**
- Existing documents without visibility metadata should remain accessible
- Users can explicitly set `"private"` or `"shared"` when needed
- Matches current behavior (no access control)

### User Format

**Decision**: Use email addresses as user identifiers

**Rationale:**
- Universally unique
- Human-readable
- Standard format
- Easy to integrate with authentication systems

### Performance Considerations

1. **Indexing**: Add indexes on `owner` and `visibility` fields
2. **Caching**: Cache user permissions for frequently accessed documents
3. **Batch Operations**: Apply access control filters at query level, not per-document

---

## Testing Strategy

### Phase 9 Tests

1. **Ownership Storage**
   - Verify owner metadata is stored correctly
   - Verify owner is returned in list operations
   - Verify default owner is "system"

2. **Backward Compatibility**
   - Verify existing documents work without owner
   - Verify optional owner parameter works

### Phase 10 Tests

1. **Access Control Enforcement**
   - Verify private documents are not accessible to non-owners
   - Verify shared documents are accessible to shared users
   - Verify public documents are accessible to all

2. **Permission Checks**
   - Verify write operations require write permission
   - Verify delete operations require delete permission
   - Verify owner has full access

3. **Error Handling**
   - Verify access denied errors are clear
   - Verify insufficient permission errors are actionable

---

## API Examples

### Phase 9 - Ownership Tracking

```python
# Write document with owner
await write_document(
    database="mydb",
    url="https://example.com/doc",
    text="Content",
    owner="alice@example.com"
)

# Create collection with owner
await create_collection(
    database="mydb",
    collection="docs",
    embedding="text-embedding-3-small",
    owner="alice@example.com"
)

# List documents shows ownership
docs = await list_documents(database="mydb")
# Returns: [{"doc_name": "doc1", "owner": "alice@example.com", ...}]
```

### Phase 10 - Access Control

```python
# Query as specific user
results = await query(
    database="mydb",
    query="search term",
    user="bob@example.com"
)
# Only returns documents bob can access

# Write with visibility control
await write_document(
    database="mydb",
    url="https://example.com/private-doc",
    text="Confidential content",
    owner="alice@example.com",
    metadata={
        "visibility": "private"
    }
)

# Share document with specific users
await write_document(
    database="mydb",
    url="https://example.com/shared-doc",
    text="Shared content",
    owner="alice@example.com",
    metadata={
        "visibility": "shared",
        "shared_with": ["bob@example.com", "charlie@example.com"]
    }
)
```

---

## Open Questions

### Q1: User Authentication
**Question**: How should users be authenticated?
**Options**:
- API keys
- OAuth tokens
- JWT tokens
- External auth service

**Decision**: TBD - depends on deployment environment

### Q2: Group Support
**Question**: Should we support user groups?
**Options**:
- Individual users only
- Add group support (e.g., "team:engineering")
- Integrate with external directory service

**Decision**: TBD - start with individual users, add groups if needed

### Q3: Permission Inheritance
**Question**: Should collections inherit permissions to documents?
**Options**:
- Document-level only (current design)
- Collection-level with inheritance
- Both with override capability

**Decision**: TBD - current design is document-level only

---

## Timeline

- **Phase 9**: 1-2 weeks after Phase 8 complete
- **Phase 10**: 2-3 weeks after Phase 9 complete
- **Total**: 3-5 weeks for both phases

## Dependencies

- Phase 8 (Documentation) must be complete
- User authentication system (for Phase 10)
- Performance testing infrastructure

## Success Criteria

### Phase 9
- [ ] Owner metadata stored for all new documents
- [ ] Owner metadata stored for all new collections
- [ ] List operations return ownership information
- [ ] Backward compatible with existing documents
- [ ] Tests passing

### Phase 10
- [ ] Access control enforced for all query operations
- [ ] Permission checks enforced for write/delete operations
- [ ] Clear error messages for access denied scenarios
- [ ] Performance impact < 10% for filtered queries
- [ ] Tests passing
- [ ] Documentation complete