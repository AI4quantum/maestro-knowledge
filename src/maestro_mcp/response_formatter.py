# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""Response formatting utilities for MCP server.

Provides standardized JSON response formats for all MCP tools (Phase 9.3).
"""

import json
from datetime import datetime, timezone
from typing import Any


def success_response(
    message: str,
    data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    operation: str | None = None,
    database: str | None = None,
    collection: str | None = None,
) -> str:
    """Create a standardized success response.

    Args:
        message: Human-readable summary of the operation
        data: Tool-specific data (optional)
        metadata: Additional metadata (optional)
        operation: Operation name for auto-metadata (optional)
        database: Database name for auto-metadata (optional)
        collection: Collection name for auto-metadata (optional)

    Returns:
        JSON string with standardized success response
    """
    response: dict[str, Any] = {
        "status": "success",
        "message": message,
    }

    if data:
        response["data"] = data

    # Build metadata automatically if operation/database/collection provided
    auto_metadata: dict[str, Any] = {}
    if operation or database or collection or metadata:
        auto_metadata["timestamp"] = datetime.now(timezone.utc).isoformat()
        if operation:
            auto_metadata["operation"] = operation
        if database:
            auto_metadata["database"] = database
        if collection:
            auto_metadata["collection"] = collection

        # Merge with provided metadata
        if metadata:
            auto_metadata.update(metadata)

        response["metadata"] = auto_metadata

    return json.dumps(response, indent=2)


def error_response(
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
    suggestion: str | None = None,
) -> str:
    """Create a standardized error response.

    Args:
        error_code: Error code (e.g., "COLLECTION_NOT_FOUND")
        message: Human-readable error message
        details: Additional error details (optional)
        suggestion: Actionable suggestion to fix the error (optional)

    Returns:
        JSON string with standardized error response
    """
    response: dict[str, Any] = {
        "status": "error",
        "error_code": error_code,
        "message": message,
    }

    if details:
        response["details"] = details

    if suggestion:
        response["suggestion"] = suggestion

    return json.dumps(response, indent=2)


def database_created_response(
    database: str,
    database_type: str,
    embedding: str,
    connection_status: str = "connected",
    collections_count: int = 0,
) -> str:
    """Create response for database creation.

    Args:
        database: Database name
        database_type: Database type (milvus/weaviate)
        embedding: Embedding model name
        connection_status: Connection status
        collections_count: Number of collections

    Returns:
        JSON success response
    """
    return success_response(
        message=f"Database '{database}' created successfully",
        data={
            "database": database,
            "database_type": database_type,
            "embedding": embedding,
            "connection_status": connection_status,
            "collections_count": collections_count,
        },
        operation="create_database",
        database=database,
    )


def database_deleted_response(
    database: str,
    collections_deleted: int = 0,
    forced: bool = False,
) -> str:
    """Create response for database deletion.

    Args:
        database: Database name
        collections_deleted: Number of collections deleted
        forced: Whether force deletion was used

    Returns:
        JSON success response
    """
    message = f"Database '{database}' deleted successfully"
    if forced and collections_deleted > 0:
        message += f" (forced deletion of {collections_deleted} collections)"

    return success_response(
        message=message,
        data={
            "database": database,
            "collections_deleted": collections_deleted,
            "forced": forced,
        },
        operation="delete_database",
        database=database,
    )


def collection_created_response(
    database: str,
    collection: str,
    embedding: str,
    chunking_strategy: str,
) -> str:
    """Create response for collection creation.

    Args:
        database: Database name
        collection: Collection name
        embedding: Embedding model name
        chunking_strategy: Chunking strategy name

    Returns:
        JSON success response
    """
    return success_response(
        message=f"Collection '{collection}' created successfully",
        data={
            "collection": collection,
            "embedding": embedding,
            "chunking_strategy": chunking_strategy,
        },
        operation="create_collection",
        collection=collection,
    )


def collection_deleted_response(
    collection: str,
    documents_deleted: int = 0,
    forced: bool = False,
) -> str:
    """Create response for collection deletion.

    Args:
        collection: Collection name
        documents_deleted: Number of documents deleted
        forced: Whether force deletion was used

    Returns:
        JSON success response
    """
    message = f"Collection '{collection}' deleted successfully"
    if forced and documents_deleted > 0:
        message += f" (forced deletion of {documents_deleted} documents)"

    return success_response(
        message=message,
        data={
            "collection": collection,
            "documents_deleted": documents_deleted,
            "forced": forced,
        },
        operation="delete_collection",
        collection=collection,
    )


def documents_written_response(
    collection: str,
    documents_written: int,
    chunks_created: int,
    embedding_model: str,
    collection_total_documents: int | None = None,
    sample_query: str | None = None,
) -> str:
    """Create response for document writing.

    Args:
        collection: Collection name
        documents_written: Number of documents written
        chunks_created: Number of chunks created
        embedding_model: Embedding model used
        collection_total_documents: Total documents in collection
        sample_query: Sample query suggestion

    Returns:
        JSON success response
    """
    data = {
        "documents_written": documents_written,
        "chunks_created": chunks_created,
        "collection": collection,
        "embedding_model": embedding_model,
    }

    metadata: dict[str, Any] = {}
    if collection_total_documents is not None:
        metadata["collection_total_documents"] = collection_total_documents
    if sample_query:
        metadata["sample_query"] = sample_query

    return success_response(
        message=f"Wrote {documents_written} document{'s' if documents_written != 1 else ''} to collection '{collection}'",
        data=data,
        metadata=metadata if metadata else None,
        operation="write_documents",
        collection=collection,
    )


def documents_deleted_response(
    collection: str,
    documents_deleted: int,
    forced: bool = False,
) -> str:
    """Create response for document deletion.

    Args:
        collection: Collection name
        documents_deleted: Number of documents deleted
        forced: Whether force deletion was used

    Returns:
        JSON success response
    """
    message = f"Deleted {documents_deleted} document{'s' if documents_deleted != 1 else ''} from collection '{collection}'"
    if forced:
        message += " (forced)"

    return success_response(
        message=message,
        data={
            "documents_deleted": documents_deleted,
            "collection": collection,
            "forced": forced,
        },
        operation="delete_documents",
        collection=collection,
    )


def search_results_response(
    query: str,
    results_count: int,
    results: list[dict[str, Any]],
    collection: str | None = None,
    limit: int | None = None,
) -> str:
    """Create response for search results.

    Args:
        query: Search query
        results_count: Number of results returned
        results: Search results
        collection: Collection name (optional)
        limit: Result limit (optional)

    Returns:
        JSON success response
    """
    message = f"Found {results_count} result{'s' if results_count != 1 else ''}"
    if collection:
        message += f" in collection '{collection}'"

    data = {
        "query": query,
        "results_count": results_count,
        "results": results,
    }

    metadata: dict[str, Any] = {}
    if limit:
        metadata["limit"] = limit

    return success_response(
        message=message,
        data=data,
        metadata=metadata if metadata else None,
        operation="search",
        collection=collection,
    )


# Made with Bob
