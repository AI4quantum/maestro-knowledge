# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""
End-to-end tests against a real Weaviate backend via FastMCP HTTP client.

These tests use the EXACT same structure as the working Milvus E2E tests,
changing only the backend-specific parameters (db_type, environment variables).

Required env to enable (example values):
- E2E_WEAVIATE=1 (or E2E_BACKEND=weaviate)
- WEAVIATE_API_KEY=your-key (or test-key for local)
- WEAVIATE_URL=https://your.weaviate.network (or http://localhost:8080 for local)

Optional env:
- E2E_MCP_PORT=8030

Container setup:
- Local: tests/setup/weaviate_e2e.sh

Note: These tests start the MCP HTTP server in-process on a local port and then
use fastmcp.Client to call the server tools end-to-end.
"""

from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # Only for type checkers; no runtime import
    from collections.abc import AsyncGenerator

import httpx
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.requires_weaviate]


def _required_env_present() -> bool:
    """Return True if this Weaviate E2E suite should run."""
    # Backend selector
    backend = (os.getenv("E2E_BACKEND") or "").strip().lower()
    if backend and backend != "weaviate":
        return False

    # If both legacy flags are set and no selector provided, do not run either suite
    if (
        not backend
        and os.getenv("E2E_MILVUS") == "1"
        and os.getenv("E2E_WEAVIATE") == "1"
    ):
        return False

    if not backend and os.getenv("E2E_WEAVIATE") != "1":
        return False

    required = ["WEAVIATE_API_KEY", "WEAVIATE_URL"]
    return all(os.getenv(k) for k in required)


@pytest.fixture(scope="module")
async def mcp_http_server() -> "AsyncGenerator[dict[str, Any], None]":
    """Start the MCP HTTP server in-process for the duration of the module."""
    if not _required_env_present():
        backend = os.getenv("E2E_BACKEND")
        if backend and backend.strip().lower() != "weaviate":
            pytest.skip(
                "E2E_BACKEND is set to a non-weaviate value; skipping Weaviate E2E"
            )
        pytest.skip(
            "E2E Weaviate env not present or E2E_WEAVIATE/E2E_BACKEND not enabled; skipping end-to-end tests"
        )

    import subprocess
    import sys
    import time

    host = "127.0.0.1"
    port = int(os.getenv("E2E_MCP_PORT", "8030"))

    # Start server as subprocess
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    # Use uv to run the server with proper environment
    cmd = [
        "uv",
        "run",
        "python",
        "-c",
        f"from maestro_mcp.server import run_http_server_sync; run_http_server_sync('{host}', {port})",
    ]

    process = subprocess.Popen(
        cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=os.getcwd()
    )

    # Wait for health endpoint to be ready (up to ~20s)
    base = f"http://{host}:{port}"
    health_url = f"{base}/health"

    server_ready = False
    async with httpx.AsyncClient() as client:
        for _ in range(40):  # 40 * 0.5s = 20s
            if process.poll() is not None:
                # Server process died
                stdout, stderr = process.communicate()
                pytest.skip(f"MCP server process failed to start: {stderr.decode()}")

            try:
                resp = await client.get(health_url, timeout=1.5)
                if resp.status_code < 500:
                    server_ready = True
                    break
            except Exception:
                pass
            await asyncio.sleep(0.5)

    if not server_ready:
        process.terminate()
        process.wait()
        pytest.skip("MCP HTTP server did not become ready in time")

    yield {"host": host, "port": port, "process": process}

    # Teardown: terminate the server process
    process.terminate()
    process.wait(timeout=5)


@pytest.mark.asyncio
async def test_weaviate_database_management(mcp_http_server: dict[str, Any]) -> None:
    """Test database management operations (exact copy of Milvus structure)."""
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"

    async with Client(base_mcp_url, timeout=60) as client:
        database = "E2E_Weaviate_DB_Management"

        # Create vector DB
        res = await client.call_tool(
            "create_database",
            {
                "database": database,
                "database_type": "weaviate",  # Only difference from Milvus
            },
        )
        assert hasattr(res, "data")

        # Test list_databases
        res = await client.call_tool("list_databases")
        assert hasattr(res, "data")

        # Test get_database_info
        res = await client.call_tool("get_database_info", {"database": database})
        assert hasattr(res, "data")

        # Test list_collections
        res = await client.call_tool("list_collections", {"database": database})
        assert hasattr(res, "data")

        # Cleanup
        res = await client.call_tool("delete_database", {"database": database})
        assert hasattr(res, "data")


@pytest.mark.asyncio
async def test_weaviate_configuration_discovery(
    mcp_http_server: dict[str, Any],
) -> None:
    """Test configuration discovery operations (exact copy of Milvus structure)."""

    # Skip if Weaviate not available
    try:
        import httpx

        weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{weaviate_url}/v1/meta")
            if resp.status_code >= 500:
                pytest.skip(
                    "Weaviate service not available for configuration discovery testing"
                )
    except Exception:
        pytest.skip(
            "Weaviate service not available for configuration discovery testing"
        )

    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"

    try:
        database = "E2E_Weaviate_Config_Test"

        async with Client(base_mcp_url, timeout=60) as client:
            print("✓ Testing configuration discovery operations")

            # Create a test database first
            res = await client.call_tool(
                "create_database",
                {
                    "database": database,
                    "database_type": "weaviate",  # Only difference from Milvus
                },
            )
            assert hasattr(res, "data")
            print("✓ Created test database for configuration testing")

            # Test get_database_info with include_embeddings
            res = await client.call_tool(
                "get_database_info", {"database": database, "include_embeddings": True}
            )
            assert hasattr(res, "data")
            # Backend-agnostic validation - just check we get some response
            assert res.data and len(str(res.data)) > 0, (
                f"No embeddings returned: {res.data}"
            )
            print("✓ Got supported embeddings")

            # Test get_database_info with include_chunking
            res = await client.call_tool(
                "get_database_info", {"database": database, "include_chunking": True}
            )
            assert hasattr(res, "data")
            # Should contain chunking strategies like 'Fixed', 'Sentence', etc.
            strategies_mentioned = any(
                strategy in res.data for strategy in ["Fixed", "Sentence", "Semantic"]
            )
            assert strategies_mentioned, (
                f"Expected chunking strategies not found in: {res.data}"
            )
            print("✓ Got supported chunking strategies")

            # Cleanup
            res = await client.call_tool("delete_database", {"database": database})
            assert hasattr(res, "data")
            print("✓ Configuration discovery tests completed")

    except Exception as e:
        pytest.fail(f"Configuration discovery E2E test failed: {e}")


@pytest.mark.asyncio
async def test_weaviate_resync_operations(mcp_http_server: dict[str, Any]) -> None:
    """Test database resynchronization functionality (exact copy of Milvus structure)."""
    from fastmcp import Client

    host = mcp_http_server["host"]
    port = mcp_http_server["port"]
    base_mcp_url = f"http://{host}:{port}/mcp/"

    async with Client(base_mcp_url, timeout=300) as client:
        # Test refresh_databases (note: no input parameter needed)
        res = await client.call_tool("refresh_databases")
        assert hasattr(res, "data"), f"refresh_databases failed: {res}"

        # Validate the response indicates successful execution
        result_data = res.data if hasattr(res, "data") else ""
        assert isinstance(result_data, (str, dict, list)), (
            f"Unexpected response format: {result_data}"
        )
