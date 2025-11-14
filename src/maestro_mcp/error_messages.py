# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""
Helpful error messages for MCP server operations.

This module provides actionable error messages that help LLM agents understand
what went wrong and how to fix it.
"""

from typing import Any


class ErrorMessages:
    """Helpful error messages for common issues."""

    @staticmethod
    def database_not_found(db_name: str, available: list[str]) -> str:
        """Error when collection doesn't exist (database is internal concept)."""
        available_str = (
            ", ".join(f"'{db}'" for db in available) if available else "none"
        )
        return f"""Collection '{db_name}' not found.

Available collections: {available_str}

To create a new collection:
create_collection(collection="{db_name}", embedding="auto")"""

    @staticmethod
    def collection_not_found(
        collection: str, database: str, available: list[str]
    ) -> str:
        """Error when collection doesn't exist."""
        available_str = ", ".join(f"'{c}'" for c in available) if available else "none"
        return f"""Collection '{collection}' not found.

Available collections: {available_str}

To create this collection:
create_collection(collection="{collection}", embedding="auto")"""

    @staticmethod
    def collection_already_exists(collection: str, database: str) -> str:
        """Error when trying to create a collection that already exists."""
        return f"""Collection '{collection}' already exists.

To use this collection, write documents directly:
write_documents(collection="{collection}", documents=[...])

To delete and recreate:
delete_collection(collection="{collection}", force=True)"""

    @staticmethod
    def database_already_exists(database: str) -> str:
        """Error when trying to register a collection that already exists."""
        return f"""Collection '{database}' is already registered.

To use this collection:
- Write documents: write_documents(collection="{database}", documents=[...])
- Query: search(collection="{database}", query="...")

To remove and recreate:
delete_collection(collection="{database}", force=True)"""

    @staticmethod
    def database_not_initialized(database: str) -> str:
        """Error when collection is registered but not initialized."""
        return f"""Collection '{database}' is registered but not properly initialized.

Try refreshing the collections registry:
refresh_databases()

Or recreate the collection:
delete_collection(collection="{database}", force=True)
create_collection(collection="{database}", embedding="auto")"""

    @staticmethod
    def invalid_embedding(embed_model: str, supported: list[str]) -> str:
        """Error when embedding model is not supported."""
        supported_str = ", ".join(f"'{e}'" for e in supported)
        return f"""Embedding model '{embed_model}' not supported.

Supported models: {supported_str}

Common options:
- 'auto' (auto-detects from environment, recommended)
- 'text-embedding-ada-002' (OpenAI default)
- 'text-embedding-3-small' (OpenAI, faster)
- 'text-embedding-3-large' (OpenAI, more accurate)
- 'custom_local' (requires CUSTOM_EMBEDDING_URL env var)

To see all supported embeddings:
get_config(include_embeddings=True)"""

    @staticmethod
    def invalid_database_type(db_type: str) -> str:
        """Error when database type is not supported."""
        return f"""Database type '{db_type}' not supported.

Supported types: 'milvus', 'weaviate'

Note: Database type is auto-detected from environment. Ensure MILVUS_URI or WEAVIATE_URL is set."""

    @staticmethod
    def document_not_found(document_name: str, collection: str, database: str) -> str:
        """Error when document doesn't exist."""
        return f"""Document '{document_name}' not found in collection '{collection}'.

To write a new document:
write_documents(collection="{collection}", documents=[{{"text": "...", "url": "{document_name}"}}])"""

    @staticmethod
    def invalid_limit(limit: int, min_val: int = 1, max_val: int = 100) -> str:
        """Error when limit parameter is out of range."""
        return f"""Invalid limit value: {limit}

Limit must be between {min_val} and {max_val}.

Example:
search(collection="docs", query="...", limit=10)"""

    @staticmethod
    def invalid_min_score(min_score: float) -> str:
        """Error when min_score is out of range."""
        return f"""Invalid min_score value: {min_score}

min_score must be between 0.0 and 1.0 (inclusive).
- 0.0 = include all results
- 0.5 = moderate similarity threshold
- 0.8 = high similarity threshold
- 1.0 = exact matches only

Example:
search(collection="docs", query="...", min_score=0.7)"""

    @staticmethod
    def empty_documents_list() -> str:
        """Error when documents list is empty."""
        return """Documents list cannot be empty.

Provide at least one document with 'text' field:
write_documents(collection="docs", documents=[
    {"text": "Document content here", "url": "https://example.com/doc1"},
    {"text": "Another document", "metadata": {"type": "article"}}
])"""

    @staticmethod
    def missing_required_field(field: str, context: str = "") -> str:
        """Error when required field is missing."""
        context_str = f" in {context}" if context else ""
        return f"""Required field '{field}' is missing{context_str}.

Each document must include:
- 'text' (required): Document content
- 'url' (optional): Document identifier or URL (auto-generated if empty)
- 'metadata' (optional): Additional metadata dict"""

    @staticmethod
    def operation_timeout(operation: str, timeout: int) -> str:
        """Error when operation times out."""
        env_var = f"MCP_TIMEOUT_{operation.upper().replace(' ', '_')}"
        return f"""Operation '{operation}' timed out after {timeout} seconds.

Possible causes:
- Database server not responding or not running
- Network connectivity issues
- Operation too complex (try reducing limit or simplifying query)
- Backend initialization taking longer than expected

Troubleshooting:
1. Check database server status (Milvus: http://localhost:19530, Weaviate: http://localhost:8080)
2. Verify network connectivity
3. Try a simpler operation first (e.g., list_collections)
4. Increase timeout via environment variable: export {env_var}=120  # 2 minutes
5. Check server logs for errors: tail -f /tmp/mcp_server.log"""

    @staticmethod
    def generic_operation_failed(operation: str, database: str, details: str) -> str:
        """Generic error for failed operations."""
        return f"""Failed to {operation} in collection '{database}'.

Error details: {details}

Troubleshooting:
1. Verify collection exists: list_collections()
2. Check collection info: get_collection(collection="{database}")
3. Review error details above for specific issues"""

    @staticmethod
    def no_results_found(query: str, suggestions: list[str] | None = None) -> str:
        """Error when search returns no results."""
        msg = f"""No results found for query: "{query}"

Possible reasons:
- Collection is empty (no documents written yet)
- Query doesn't match any documents
- min_score threshold too high
- metadata_filters too restrictive"""

        if suggestions:
            msg += "\n\nSuggestions:\n"
            for suggestion in suggestions:
                msg += f"- {suggestion}\n"

        return msg

    @staticmethod
    def format_error_with_context(
        error: Exception, operation: str, context: dict[str, Any]
    ) -> str:
        """Format an error with operation context."""
        context_str = ", ".join(f"{k}={v}" for k, v in context.items())
        return f"""Error during {operation}: {str(error)}

Operation context: {context_str}

This is an unexpected error. Please check:
1. Input parameters are valid
2. Database is properly initialized
3. Network connectivity is stable"""


# Made with Bob
