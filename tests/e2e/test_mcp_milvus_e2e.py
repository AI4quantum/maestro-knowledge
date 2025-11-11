# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""
End-to-end tests against a real Milvus backend via FastMCP HTTP client.

These tests are OPTIONAL and will be skipped unless the required environment variables are set.
They test all 22 MCP server tools for feature parity with the Weaviate backend.

Required env to enable (example values):
- E2E_MILVUS=1 (or E2E_BACKEND=milvus)
- MILVUS_URI=http://localhost:19530
- CUSTOM_EMBEDDING_URL=http://localhost:11434/api/embeddings
- CUSTOM_EMBEDDING_MODEL=nomic-embed-text
- CUSTOM_EMBEDDING_VECTORSIZE=768

Optional env:
- E2E_MCP_PORT=8030
- LOG_LEVEL=info
- VDB_LOG_LEVEL=debug
- PRETTY_TOOL_JSON=true
- FULL_TOOL_JSON=true

Container setup:
- Local: tests/setup/milvus_e2e.sh
- Manual: podman run -d --name milvus-test -p 19530:19530 -p 9091:9091 -e ETCD_USE_EMBED=true milvusdb/milvus:v2.6.1

Note: These tests start the MCP HTTP server in-process on a local port and then
use fastmcp.Client to call the server tools end-to-end.
"""

from __future__ import annotations

import pytest

# Backend-agnostic Milvus E2E test entrypoint using shared test logic
pytestmark = [pytest.mark.e2e, pytest.mark.requires_milvus]

from tests.e2e.common import set_backend_name
from tests.e2e.test_functions import (
    run_bulk_operations_tests,
    run_collection_specific_tests,
    run_configuration_discovery_tests,
    run_database_management_tests,
    run_document_operations_tests,
    run_document_retrieval_tests,
    run_full_flow_test,
    run_health_check_tests,
    run_query_operations_tests,
    run_resync_operations_tests,
)

set_backend_name("milvus")
BACKEND_NAME = "milvus"


@pytest.mark.asyncio
async def test_database_management(mcp_http_server: dict) -> None:
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"
    async with Client(base_mcp_url, timeout=300) as client:
        await run_database_management_tests(client, BACKEND_NAME)


@pytest.mark.asyncio
async def test_document_operations(mcp_http_server: dict) -> None:
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"
    async with Client(base_mcp_url, timeout=300) as client:
        await run_document_operations_tests(client, BACKEND_NAME)


@pytest.mark.asyncio
async def test_query_operations(mcp_http_server: dict) -> None:
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"
    async with Client(base_mcp_url, timeout=300) as client:
        await run_query_operations_tests(client, BACKEND_NAME)


@pytest.mark.asyncio
async def test_configuration_discovery(mcp_http_server: dict) -> None:
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"
    async with Client(base_mcp_url, timeout=300) as client:
        await run_configuration_discovery_tests(client, BACKEND_NAME)


@pytest.mark.asyncio
async def test_document_retrieval(mcp_http_server: dict) -> None:
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"
    async with Client(base_mcp_url, timeout=300) as client:
        await run_document_retrieval_tests(client, BACKEND_NAME)


@pytest.mark.asyncio
async def test_bulk_operations(mcp_http_server: dict) -> None:
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"
    async with Client(base_mcp_url, timeout=300) as client:
        await run_bulk_operations_tests(client, BACKEND_NAME)


@pytest.mark.asyncio
async def test_collection_specific_operations(mcp_http_server: dict) -> None:
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"
    async with Client(base_mcp_url, timeout=300) as client:
        await run_collection_specific_tests(client, BACKEND_NAME)


@pytest.mark.asyncio
async def test_resync_operations(mcp_http_server: dict) -> None:
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"
    async with Client(base_mcp_url, timeout=300) as client:
        await run_resync_operations_tests(client, BACKEND_NAME)


@pytest.mark.asyncio
async def test_health_check(mcp_http_server: dict) -> None:
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"
    async with Client(base_mcp_url, timeout=300) as client:
        await run_health_check_tests(client, BACKEND_NAME, str(port))


@pytest.mark.asyncio
async def test_full_flow(mcp_http_server: dict) -> None:
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"
    async with Client(base_mcp_url, timeout=300) as client:
        await run_full_flow_test(client, BACKEND_NAME)


# E2E Test Status Summary:
# ✅ ALL PASSING (10/10):
#   - test_database_management
#   - test_document_operations
#   - test_query_operations
#   - test_configuration_discovery
#   - test_document_retrieval
#   - test_bulk_operations
#   - test_collection_specific_operations
#   - test_resync_operations
#   - test_health_check
#   - test_full_flow
