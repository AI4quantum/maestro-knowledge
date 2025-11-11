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
        """Error when database doesn't exist."""
        available_str = (
            ", ".join(f"'{db}'" for db in available) if available else "none"
        )
        return f"""Database '{db_name}' not found.

Available databases: {available_str}

To create a new database:
1. Register: register_database(database="{db_name}", database_type="milvus", collection="default")
2. Initialize: setup_database(database="{db_name}", embedding="default")
3. Create collection: create_collection(database="{db_name}", collection="default")"""

    @staticmethod
    def collection_not_found(
        collection: str, database: str, available: list[str]
    ) -> str:
        """Error when collection doesn't exist."""
        available_str = ", ".join(f"'{c}'" for c in available) if available else "none"
        return f"""Collection '{collection}' not found in database '{database}'.

Available collections: {available_str}

To create this collection:
create_collection(database="{database}", collection="{collection}", embedding="default")"""

    @staticmethod
    def collection_already_exists(collection: str, database: str) -> str:
        """Error when trying to create a collection that already exists."""
        return f"""Collection '{collection}' already exists in database '{database}'.

To use this collection, write documents directly:
write_documents(database="{database}", documents=[...])

To delete and recreate:
delete_collection(database="{database}", collection="{collection}")"""

    @staticmethod
    def database_already_exists(database: str) -> str:
        """Error when trying to register a database that already exists."""
        return f"""Database '{database}' is already registered.

To use this database:
- Write documents: write_documents(database="{database}", documents=[...])
- Query: search(database="{database}", query="...")

To remove and recreate:
cleanup(database="{database}")"""

    @staticmethod
    def database_not_initialized(database: str) -> str:
        """Error when database is registered but not initialized."""
        return f"""Database '{database}' is registered but not initialized.

Initialize the connection:
setup_database(database="{database}", embedding="default")

Then create a collection:
create_collection(database="{database}", collection="default")"""

    @staticmethod
    def invalid_embedding(embed_model: str, supported: list[str]) -> str:
        """Error when embedding model is not supported."""
        supported_str = ", ".join(f"'{e}'" for e in supported)
        return f"""Embedding model '{embed_model}' not supported.

Supported models: {supported_str}

Common options:
- 'default' (OpenAI text-embedding-ada-002)
- 'text-embedding-3-small' (OpenAI, faster)
- 'text-embedding-3-large' (OpenAI, more accurate)
- 'custom_local' (requires CUSTOM_EMBEDDING_URL env var)

To see all supported embeddings:
get_supported_embeddings(database="your_database")"""

    @staticmethod
    def invalid_database_type(db_type: str) -> str:
        """Error when database type is not supported."""
        return f"""Database type '{db_type}' not supported.

Supported types: 'milvus', 'weaviate'

Example:
register_database(database="mydb", database_type="milvus", collection="default")"""

    @staticmethod
    def document_not_found(document_name: str, collection: str, database: str) -> str:
        """Error when document doesn't exist."""
        return f"""Document '{document_name}' not found in collection '{collection}' of database '{database}'.

To list available documents:
list_documents_in_collection(database="{database}", collection="{collection}")

To write a new document:
write_document_to_collection(database="{database}", collection="{collection}", document_name="{document_name}", text="...", url="...")"""

    @staticmethod
    def invalid_limit(limit: int, min_val: int = 1, max_val: int = 100) -> str:
        """Error when limit parameter is out of range."""
        return f"""Invalid limit value: {limit}

Limit must be between {min_val} and {max_val}.

Example:
search(database="mydb", query="...", limit=10)"""

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
search(database="mydb", query="...", min_score=0.7)"""

    @staticmethod
    def empty_documents_list() -> str:
        """Error when documents list is empty."""
        return """Documents list cannot be empty.

Provide at least one document with 'url' field:
write_documents(database="mydb", documents=[
    {"url": "https://example.com/doc1", "metadata": {"type": "article"}},
    {"url": "doc2", "text": "Direct text content"}
])"""

    @staticmethod
    def missing_required_field(field: str, context: str = "") -> str:
        """Error when required field is missing."""
        context_str = f" in {context}" if context else ""
        return f"""Required field '{field}' is missing{context_str}.

Each document must include:
- 'url' (required): Document identifier or URL
- 'text' (optional): Direct text content
- 'metadata' (optional): Additional metadata dict"""

    @staticmethod
    def operation_timeout(operation: str, timeout: int) -> str:
        """Error when operation times out."""
        return f"""Operation '{operation}' timed out after {timeout} seconds.

Possible causes:
- Database server not responding
- Network connectivity issues
- Operation too complex (try reducing limit or simplifying query)

Troubleshooting:
1. Check database server status
2. Verify network connectivity
3. Try a simpler operation first
4. Increase timeout via environment variables (see documentation)"""

    @staticmethod
    def generic_operation_failed(operation: str, database: str, details: str) -> str:
        """Generic error for failed operations."""
        return f"""Failed to {operation} in database '{database}'.

Error details: {details}

Troubleshooting:
1. Verify database is initialized: get_database_info(database="{database}")
2. Check database status: list_databases()
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
