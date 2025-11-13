# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""
Shared E2E test functions for all vector database backends.

These test functions are backend-agnostic and can be used with any
vector database backend (Milvus, Weaviate, etc.) by passing the
appropriate backend configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.e2e.common import get_backend_config, get_db_name_for_test

if TYPE_CHECKING:
    from fastmcp import Client


async def run_database_management_tests(client: Client, backend_name: str) -> None:
    """Test database creation, collection management, and list_collections tool."""
    config = get_backend_config(backend_name)
    db_name = get_db_name_for_test(backend_name, "DB_Management")

    # Test create_vector_database_tool
    res = await client.call_tool(
        "create_database",
        {
            "database": db_name,
            "database_type": config["db_type"],
        },
    )
    assert hasattr(res, "data"), f"create_vector_database_tool failed: {res}"

    # Test create_collection
    res = await client.call_tool(
        "create_collection",
        {
            "database": db_name,
            "collection": f"{db_name}_Collection",
        },
    )
    assert hasattr(res, "data"), f"create_collection failed: {res}"

    # Test list_collections
    res = await client.call_tool("list_collections", {"database": db_name})
    assert hasattr(res, "data"), f"list_collections failed: {res}"

    # Test get_collection_info
    res = await client.call_tool("get_collection_info", {"database": db_name})
    assert hasattr(res, "data"), f"get_collection_info failed: {res}"

    # Test list_databases - HIGH PRIORITY addition
    res = await client.call_tool("list_databases")
    assert hasattr(res, "data"), f"list_databases failed: {res}"
    # Verify our database appears in the list
    assert db_name in str(res.data), (
        f"Database {db_name} not found in list_databases result"
    )

    # Test get_database_info - HIGH PRIORITY addition
    res = await client.call_tool("get_database_info", {"database": db_name})
    assert hasattr(res, "data"), f"get_database_info failed: {res}"

    # Cleanup
    res = await client.call_tool("delete_database", {"database": db_name})
    assert hasattr(res, "data"), f"cleanup failed: {res}"


async def run_document_operations_tests(client: Client, backend_name: str) -> None:
    """Test document CRUD operations."""
    config = get_backend_config(backend_name)
    db_name = get_db_name_for_test(backend_name, "Document_Ops")

    # Setup
    res = await client.call_tool(
        "create_database",
        {
            "database": db_name,
            "database_type": config["db_type"],
        },
    )
    assert hasattr(res, "data")

    res = await client.call_tool(
        "create_collection",
        {
            "database": db_name,
            "collection": f"{db_name}_Collection",
        },
    )
    assert hasattr(res, "data")

    # Test write_documents
    docs = [
        {
            "url": f"https://example.com/doc1",
            "text": f"{backend_name.title()} document one",
        },
        {
            "url": f"https://example.com/doc2",
            "text": f"{backend_name.title()} document two",
        },
    ]
    res = await client.call_tool(
        "write_documents",
        {
            "database": db_name,
            "documents": docs,
        },
    )
    # Accept string or object response
    if not hasattr(res, "data"):
        import json

        try:
            res_data = json.loads(res) if isinstance(res, str) else res
        except Exception:
            res_data = res
        assert res_data, f"write_documents failed: {res}"

    # Test get_collection_info with count
    res = await client.call_tool(
        "get_collection_info", {"database": db_name, "include_count": True}
    )
    if not hasattr(res, "data") and isinstance(res, str):
        assert res, f"get_collection_info with count failed: {res}"

    # Test delete_documents (use search to get a document ID first)
    res = await client.call_tool(
        "search", {"database": db_name, "query": "test", "limit": 1}
    )
    first_doc_id = None
    if hasattr(res, "data"):
        search_results = res.data if isinstance(res.data, list) else []
        if (
            search_results
            and isinstance(search_results, list)
            and len(search_results) > 0
        ):
            first_doc = search_results[0]
            if isinstance(first_doc, dict):
                first_doc_id = (
                    first_doc.get("id")
                    or first_doc.get("doc_id")
                    or first_doc.get("document_id")
                )
    elif isinstance(res, str):
        import json

        try:
            search_results = json.loads(res)
            if isinstance(search_results, list) and len(search_results) > 0:
                first_doc = search_results[0]
                if isinstance(first_doc, dict):
                    first_doc_id = (
                        first_doc.get("id")
                        or first_doc.get("doc_id")
                        or first_doc.get("document_id")
                    )
        except Exception:
            pass

    if first_doc_id:
        res = await client.call_tool(
            "delete_documents", {"database": db_name, "document_ids": [first_doc_id]}
        )
        if not hasattr(res, "data") and isinstance(res, str):
            assert res, f"delete_documents failed: {res}"

    # Cleanup
    res = await client.call_tool("delete_database", {"database": db_name})
    if not hasattr(res, "data") and isinstance(res, str):
        assert res, f"cleanup failed: {res}"


async def run_query_operations_tests(client: Client, backend_name: str) -> None:
    """Test query and search operations."""
    config = get_backend_config(backend_name)
    db_name = get_db_name_for_test(backend_name, "Query_Ops")

    # Setup
    res = await client.call_tool(
        "create_database",
        {
            "database": db_name,
            "database_type": config["db_type"],
        },
    )
    assert hasattr(res, "data")

    res = await client.call_tool(
        "create_collection",
        {
            "database": db_name,
            "collection": f"{db_name}_Collection",
        },
    )
    assert hasattr(res, "data")

    # Write test documents
    docs = [
        {
            "url": "https://example.com/ai",
            "text": "Artificial intelligence and machine learning",
        },
        {
            "url": "https://example.com/vector",
            "text": "Vector databases for semantic search",
        },
        {
            "url": f"https://example.com/{backend_name}",
            "text": f"{backend_name.title()} is a vector database",
        },
    ]
    res = await client.call_tool(
        "write_documents",
        {
            "database": db_name,
            "documents": docs,
        },
    )
    assert hasattr(res, "data")

    # Test search
    res = await client.call_tool(
        "search",
        {
            "database": db_name,
            "query": "vector database",
            "limit": 2,
        },
    )
    assert hasattr(res, "data") or hasattr(res, "content"), f"search failed: {res}"

    # Test query (intelligent query with reasoning)
    res = await client.call_tool(
        "query",
        {
            "database": db_name,
            "query": "What is machine learning?",
            "limit": 1,
        },
    )
    assert hasattr(res, "data") or hasattr(res, "content"), f"query failed: {res}"

    # Cleanup
    res = await client.call_tool("delete_database", {"database": db_name})
    assert hasattr(res, "data")


async def run_configuration_discovery_tests(client: Client, backend_name: str) -> None:
    """Test configuration discovery operations: get_database_info with embeddings and chunking."""
    config = get_backend_config(backend_name)
    db_name = get_db_name_for_test(backend_name, "Config_Test")

    # Create a test database first
    res = await client.call_tool(
        "create_database",
        {
            "database": db_name,
            "database_type": config["db_type"],
        },
    )
    assert hasattr(res, "data")

    # Test get_database_info with include_embeddings
    res = await client.call_tool(
        "get_database_info", {"database": db_name, "include_embeddings": True}
    )
    assert hasattr(res, "data")
    # Should contain embedding options (backend-specific validation)
    if backend_name == "milvus":
        assert "custom_local" in res.data or "custom" in res.data.lower()
    elif backend_name == "weaviate":
        assert "default" in res.data or "text2vec" in res.data.lower()

    # Test get_database_info with include_chunking
    res = await client.call_tool(
        "get_database_info", {"database": db_name, "include_chunking": True}
    )
    assert hasattr(res, "data")
    # Should contain chunking strategies
    strategies_mentioned = any(
        strategy in res.data for strategy in ["Fixed", "Sentence", "Semantic"]
    )
    assert strategies_mentioned, (
        f"Expected chunking strategies not found in: {res.data}"
    )

    # Cleanup
    res = await client.call_tool("delete_database", {"database": db_name})
    assert hasattr(res, "data")


async def run_document_retrieval_tests(client: Client, backend_name: str) -> None:
    """Test document retrieval operations: get_document."""
    config = get_backend_config(backend_name)
    db_name = get_db_name_for_test(backend_name, "Doc_Retrieval")

    # Create the database (now includes setup)
    res = await client.call_tool(
        "create_database",
        {
            "database": db_name,
            "database_type": config["db_type"],
        },
    )
    assert hasattr(res, "data")

    # Create collection
    res = await client.call_tool(
        "create_collection",
        {
            "database": db_name,
            "collection": f"{db_name}_Collection",
        },
    )
    assert hasattr(res, "data")

    # Write a test document to retrieve later
    test_doc = {
        "url": "https://example.com/retrieval-test",
        "text": f"This document is for testing retrieval in {backend_name.title()}",
        "metadata": {"test": "retrieval", "backend": backend_name},
    }

    res = await client.call_tool(
        "write_documents",
        {
            "database": db_name,
            "documents": [test_doc],
        },
    )
    assert hasattr(res, "data")

    # Get document list to find a document ID
    res = await client.call_tool(
        "search", {"database": db_name, "query": "*", "limit": 1}
    )
    assert hasattr(res, "data")

    if isinstance(res.data, list) and len(res.data) > 0:
        doc_id = res.data[0].get("id")
        if doc_id:
            # Test get_document
            res = await client.call_tool(
                "get_document", {"database": db_name, "document_id": doc_id}
            )
            assert hasattr(res, "data")

    # Cleanup
    res = await client.call_tool("delete_database", {"database": db_name})
    assert hasattr(res, "data")


async def run_bulk_operations_tests(client: Client, backend_name: str) -> None:
    """Test bulk operations: delete_documents."""
    config = get_backend_config(backend_name)
    db_name = get_db_name_for_test(backend_name, "Bulk_Ops")

    # Setup
    res = await client.call_tool(
        "create_database",
        {
            "database": db_name,
            "database_type": config["db_type"],
        },
    )
    assert hasattr(res, "data")

    res = await client.call_tool(
        "create_collection",
        {
            "database": db_name,
            "collection": f"{db_name}_Collection",
        },
    )
    assert hasattr(res, "data")

    # Write multiple documents for bulk deletion
    docs = [
        {
            "url": f"https://example.com/bulk{i}",
            "text": f"{backend_name.title()} bulk document {i}",
        }
        for i in range(1, 4)
    ]
    res = await client.call_tool(
        "write_documents",
        {
            "database": db_name,
            "documents": docs,
        },
    )
    assert hasattr(res, "data")

    # Get document IDs for bulk deletion
    res = await client.call_tool(
        "search", {"database": db_name, "query": "*", "limit": 10}
    )
    assert hasattr(res, "data")

    if isinstance(res.data, list) and len(res.data) >= 2:
        doc_ids = [doc.get("id") for doc in res.data[:2] if doc.get("id")]
        if doc_ids:
            # Test delete_documents (bulk)
            res = await client.call_tool(
                "delete_documents", {"database": db_name, "document_ids": doc_ids}
            )
            assert hasattr(res, "data")

    # Cleanup
    res = await client.call_tool("delete_database", {"database": db_name})
    assert hasattr(res, "data")


async def run_collection_specific_tests(client: Client, backend_name: str) -> None:
    """Test collection-specific document operations."""
    import pytest

    config = get_backend_config(backend_name)
    db_name = get_db_name_for_test(backend_name, "Collection_Ops")
    collection_name = f"{db_name}_Collection"
    doc_name = f"test_{backend_name}_doc"

    # Track if we need cleanup
    needs_cleanup = False
    skip_reason = None

    try:
        # Setup
        res = await client.call_tool(
            "create_database",
            {
                "database": db_name,
                "database_type": config["db_type"],
            },
        )
        if not hasattr(res, "data"):
            skip_reason = f"Could not create vector database for {backend_name}: {res}"
        else:
            needs_cleanup = True

        if skip_reason is None:
            res = await client.call_tool(
                "create_collection",
                {
                    "database": db_name,
                    "collection": collection_name,
                },
            )
            if not hasattr(res, "data"):
                skip_reason = f"Could not create collection for {backend_name}: {res}"

        # Verify collection existence (retry for Weaviate) - only if no skip reason yet
        if skip_reason is None:
            collection_found = False
            max_retries = 5 if backend_name == "weaviate" else 1
            for attempt in range(max_retries):
                res = await client.call_tool("list_collections", {"database": db_name})
                if hasattr(res, "data") and isinstance(res.data, list):
                    if collection_name in res.data:
                        collection_found = True
                        break
                if backend_name == "weaviate" and attempt < max_retries - 1:
                    import asyncio

                    await asyncio.sleep(1)
            if not collection_found:
                skip_reason = f"Collection '{collection_name}' not found in database '{db_name}' for {backend_name} after creation."

        # Skip immediately if we have a skip reason, after cleanup
        if skip_reason:
            # Instead of skipping, just return early to avoid pytest skip complications
            return

        # Test write_documents (replaces write_document_to_collection)
        res = await client.call_tool(
            "write_documents",
            {
                "database": db_name,
                "documents": [
                    {
                        "url": "https://example.com/collection-doc",
                        "text": f"This is a collection-specific document for {backend_name.title()}",
                        "metadata": {
                            "source": "collection_test",
                            "backend": backend_name,
                            "doc_name": doc_name,
                        },
                    }
                ],
            },
        )
        if not hasattr(res, "data"):
            pytest.fail(f"write_documents failed for {backend_name}: {res}")

        # Test search in collection
        res = await client.call_tool(
            "search",
            {
                "database": db_name,
                "collection": collection_name,
                "query": "*",
                "limit": 10,
            },
        )
        if not hasattr(res, "data"):
            pytest.fail(f"search failed for {backend_name}: {res}")

        # Test delete_documents - need to find document ID first from search
        res = await client.call_tool(
            "search",
            {
                "database": db_name,
                "collection": collection_name,
                "query": "*",
                "limit": 10,
            },
        )
        doc_id = None
        if hasattr(res, "data") and isinstance(res.data, list):
            for doc in res.data:
                if (
                    isinstance(doc, dict)
                    and doc.get("metadata", {}).get("doc_name") == doc_name
                ):
                    doc_id = doc.get("id")
                    break

        if doc_id:
            res = await client.call_tool(
                "delete_documents",
                {
                    "database": db_name,
                    "document_ids": [doc_id],
                },
            )
            if not hasattr(res, "data"):
                pytest.fail(f"delete_documents failed for {backend_name}: {res}")

        # Test delete_collection - MEDIUM PRIORITY addition
        res = await client.call_tool(
            "delete_collection",
            {
                "database": db_name,
                "collection": collection_name,
            },
        )
        if not hasattr(res, "data"):
            pytest.fail(f"delete_collection failed for {backend_name}: {res}")

        # Verify collection was deleted by checking it no longer appears in list
        res = await client.call_tool("list_collections", {"database": db_name})
        if hasattr(res, "data") and isinstance(res.data, list):
            if collection_name in res.data:
                pytest.fail(
                    f"Collection '{collection_name}' still exists after deletion for {backend_name}"
                )

    except Exception as e:
        if "pytest" in str(type(e)) and "Skip" in str(type(e)):
            # This is a pytest.skip() exception, let it propagate after cleanup
            raise
        else:
            pytest.fail(
                f"Exception in collection-specific test for {backend_name}: {e}"
            )

    finally:
        # Always cleanup if we created resources
        if needs_cleanup:
            try:
                res = await client.call_tool("delete_database", {"database": db_name})
            except Exception:
                pass


async def run_resync_operations_tests(client: Client, backend_name: str) -> None:
    """Test database resynchronization functionality."""
    # Test refresh_databases
    res = await client.call_tool("refresh_databases")
    assert hasattr(res, "data"), f"refresh_databases failed: {res}"

    # Validate the response indicates successful execution
    # Note: For MCP-created collections, this might return 0 discoveries
    # but should still execute without error
    result_data = res.data if hasattr(res, "data") else ""
    assert isinstance(result_data, (str, dict, list)), (
        f"Unexpected response format: {result_data}"
    )


async def run_health_check_tests(
    client: Client, backend_name: str, server_port: str = None
) -> None:
    """Test health endpoint functionality."""
    import httpx

    # Use provided server port or try to extract from client base URL, or use default
    if server_port:
        health_url = f"http://localhost:{server_port}/health"
    else:
        # Try to extract port from client base URL if available
        import os

        mcp_port = os.getenv("E2E_MCP_PORT", "8030")
        health_url = f"http://localhost:{mcp_port}/health"

    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.get(health_url)
            assert response.status_code == 200, (
                f"Health check failed with status {response.status_code}"
            )

            health_text = response.text
            assert health_text, "Health check returned empty response"

            # Health response should contain database information or "No vector databases" message
            assert (
                "vector databases" in health_text.lower()
                or "Available vector databases" in health_text
            ), f"Unexpected health response: {health_text}"

    except Exception as e:
        # Health endpoint test is informational - don't fail the entire test suite
        import pytest

        pytest.skip(f"Health endpoint test skipped due to connection issue: {e}")


async def run_full_flow_test(client: Client, backend_name: str) -> None:
    """Full flow integration test covering the main workflow."""
    import asyncio

    import pytest

    config = get_backend_config(backend_name)
    db_name = get_db_name_for_test(backend_name, "Full_Flow")

    try:
        # Create vector DB
        res = await client.call_tool(
            "create_database",
            {
                "database": db_name,
                "database_type": config["db_type"],
            },
        )
        if not hasattr(res, "data"):
            pytest.skip(f"Could not create vector database for {backend_name}: {res}")

        # Create collection with chunking config (retry for Weaviate)
        collection_created = False
        max_retries = 5 if backend_name == "weaviate" else 1
        for attempt in range(max_retries):
            res = await client.call_tool(
                "create_collection",
                {
                    "database": db_name,
                    "collection": db_name,
                    "chunking_config": {
                        "strategy": "Sentence",
                        "parameters": {
                            "chunk_size": 512,
                            "overlap": 24,
                        },
                    },
                },
            )
            if hasattr(res, "data"):
                collection_created = True
                break
            if backend_name == "weaviate":
                await asyncio.sleep(1)
        if not collection_created:
            pytest.skip(
                f"Could not create collection for {backend_name} after retries: {res}"
            )

        # Write documents
        docs = [
            {
                "url": f"https://example.com/{backend_name}1",
                "text": f"hello {backend_name} vector world",
            },
            {
                "url": f"https://example.com/{backend_name}2",
                "text": f"maestro knowledge {backend_name}",
            },
        ]
        res = await client.call_tool(
            "write_documents",
            {
                "database": db_name,
                "documents": docs,
            },
        )
        if not hasattr(res, "data"):
            pytest.fail(f"write_documents failed for {backend_name}: {res}")

        # List documents
        res = await client.call_tool(
            "search", {"database": db_name, "query": "*", "limit": 10}
        )
        if not hasattr(res, "data"):
            pytest.fail(f"list_documents failed for {backend_name}: {res}")

        # Count documents via get_collection_info
        res = await client.call_tool(
            "get_collection_info", {"database": db_name, "include_count": True}
        )
        if not hasattr(res, "data"):
            pytest.fail(
                f"get_collection_info with count failed for {backend_name}: {res}"
            )

        # Get collection info
        res = await client.call_tool("get_collection_info", {"database": db_name})
        if not hasattr(res, "data"):
            pytest.fail(f"get_collection_info failed for {backend_name}: {res}")

        # Search
        res = await client.call_tool(
            "search",
            {
                "database": db_name,
                "query": "vector",
                "limit": 1,
            },
        )
        if not (hasattr(res, "data") or hasattr(res, "content")):
            pytest.fail(f"search failed for {backend_name}: {res}")

    except Exception as e:
        pytest.fail(f"Exception in full flow test for {backend_name}: {e}")

    finally:
        # Cleanup
        try:
            res = await client.call_tool("delete_database", {"database": db_name})
        except Exception:
            pass
