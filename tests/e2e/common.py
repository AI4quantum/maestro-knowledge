# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""
Common E2E test infrastructure for all vector database backends.

This module provides shared test logic, fixtures, and configuration
that can be used across different vector database backends (Milvus, Weaviate, etc.)
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Any

import httpx
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# Backend configurations
BACKEND_CONFIGS = {
    "milvus": {
        "env_flag": "E2E_MILVUS",
        "required_env": [
            "MILVUS_URI",
            "CUSTOM_EMBEDDING_URL",
            "CUSTOM_EMBEDDING_MODEL",
            "CUSTOM_EMBEDDING_VECTORSIZE",
        ],
        "db_type": "milvus",
        "service_check": lambda: _check_milvus_service(),
        "skip_reason": "E2E Milvus env not present or E2E_MILVUS/E2E_BACKEND not enabled; skipping end-to-end tests",
    },
    "weaviate": {
        "env_flag": "E2E_WEAVIATE",
        "required_env": ["WEAVIATE_API_KEY", "WEAVIATE_URL"],
        "db_type": "weaviate",
        "service_check": lambda: _check_weaviate_service(),
        "skip_reason": "E2E Weaviate env not present or E2E_WEAVIATE/E2E_BACKEND not enabled; skipping end-to-end tests",
    },
}


def _check_milvus_service() -> bool:
    """Check if Milvus service is available."""
    # Quick TCP port check first - fails fast if port is closed
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)  # Very short timeout for port check
        result = sock.connect_ex(("localhost", 19530))
        sock.close()
        if result != 0:  # Port not open
            return False
    except Exception:
        return False

    # Port is open, now verify it's actually Milvus with gRPC
    try:
        from pymilvus import connections, utility

        connections.connect(
            alias="test_config", host="localhost", port="19530", timeout=2
        )
        utility.list_collections(using="test_config")
        connections.disconnect("test_config")
        return True
    except Exception:
        return False


def _check_weaviate_service() -> bool:
    """Check if Weaviate service is available."""
    try:
        import httpx

        weaviate_url = os.getenv("WEAVIATE_URL", "http://localhost:8080")
        with httpx.Client(timeout=2) as client:
            resp = client.get(f"{weaviate_url}/v1/meta")
            return resp.status_code < 500
    except Exception:
        return False


def _required_env_present(backend: str) -> bool:
    """Return True if the required environment for a backend is present.

    Rules:
    - If E2E_BACKEND is set, it must equal the backend name (case-insensitive)
    - Backward-compat: if E2E_BACKEND is NOT set, we fall back to requiring E2E_{BACKEND}=1
    - In all cases, the backend-specific env vars must be present.
    """
    config = BACKEND_CONFIGS[backend]

    e2e_backend = (os.getenv("E2E_BACKEND") or "").strip().lower()
    if e2e_backend and e2e_backend != backend:
        return False

    # If both legacy flags are set and no selector provided, do not run either suite
    if (
        not e2e_backend
        and os.getenv("E2E_MILVUS") == "1"
        and os.getenv("E2E_WEAVIATE") == "1"
    ):
        return False

    if not e2e_backend and os.getenv(config["env_flag"]) != "1":
        return False

    return all(os.getenv(k) for k in config["required_env"])


BACKEND_NAME = None


def set_backend_name(name: str) -> None:
    global BACKEND_NAME
    BACKEND_NAME = name


@pytest.fixture(scope="function")
async def mcp_http_server() -> "AsyncGenerator[dict[str, Any], None]":
    """Start the MCP HTTP server in-process for the duration of the module.
    Uses global BACKEND_NAME set by test entrypoint.
    Skips the test module if required env is not present or service is unavailable.
    """
    backend_name = BACKEND_NAME or os.getenv("E2E_BACKEND", "weaviate").strip().lower()
    if not _required_env_present(backend_name):
        config = BACKEND_CONFIGS[backend_name]
        e2e_backend = os.getenv("E2E_BACKEND")
        if e2e_backend and e2e_backend.strip().lower() != backend_name:
            pytest.skip(
                f"E2E_BACKEND is set to a non-{backend_name} value; skipping {backend_name.title()} E2E"
            )
        pytest.skip(config["skip_reason"])

    # Check service availability
    config = BACKEND_CONFIGS[backend_name]
    if not config["service_check"]():
        pytest.skip(f"{backend_name.title()} service not available for E2E testing")

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

    yield {"host": host, "port": port, "process": process, "backend": backend_name}

    # Teardown: terminate the server process
    try:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if graceful termination fails
            process.kill()
            process.wait(timeout=2)
    except Exception as e:
        # If all else fails, try to kill the process
        try:
            process.kill()
            process.wait(timeout=2)
        except Exception:
            pass


def get_backend_config(backend_name: str) -> dict[str, Any]:
    """Get the configuration for a specific backend."""
    return BACKEND_CONFIGS[backend_name]


def get_db_name_for_test(backend_name: str, test_category: str) -> str:
    """Generate a consistent database name for tests."""
    return f"E2E_{backend_name.title()}_{test_category}"


# Pytest marks for each backend
pytestmark_milvus = [pytest.mark.e2e, pytest.mark.requires_milvus]
pytestmark_weaviate = [pytest.mark.e2e, pytest.mark.requires_weaviate]
