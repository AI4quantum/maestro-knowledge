# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import asyncio
import json
import os
from typing import Any


def is_milvus_running() -> bool:
    """Check if a Milvus instance is running and accessible."""
    try:
        return asyncio.run(is_milvus_running_async())
    except Exception:
        return False


async def is_milvus_running_async() -> bool:
    """Check if a Milvus instance is running and accessible."""
    try:
        from pymilvus import AsyncMilvusClient
    except ImportError:
        return False

    milvus_uri = os.environ.get("MILVUS_URI", "milvus_demo.db")
    milvus_token = os.environ.get("MILVUS_TOKEN")
    timeout = int(
        os.environ.get("MILVUS_CONNECT_TIMEOUT", "3")
    )  # Short timeout for check

    try:
        if milvus_token:
            client = AsyncMilvusClient(
                uri=milvus_uri, token=milvus_token, timeout=timeout
            )
        else:
            client = AsyncMilvusClient(uri=milvus_uri, timeout=timeout)
        await client.list_collections()
        return True
    except Exception:
        return False


def parse_mcp_response(result: str) -> dict[str, Any]:
    """Parse MCP tool response as JSON.

    Args:
        result: JSON string response from MCP tool

    Returns:
        Parsed JSON response dict

    Raises:
        AssertionError: If response is not valid JSON
    """
    try:
        return json.loads(result)
    except json.JSONDecodeError as e:
        raise AssertionError(f"Invalid JSON response: {result}") from e


def assert_success_response(
    response: dict[str, Any], operation: str | None = None
) -> None:
    """Assert response is a successful MCP response.

    Args:
        response: Parsed JSON response
        operation: Expected operation name (optional)
    """
    assert response["status"] == "success", f"Expected success, got: {response}"
    assert "message" in response
    assert "data" in response

    if operation:
        assert response.get("metadata", {}).get("operation") == operation


def assert_error_response(
    response: dict[str, Any], error_code: str | None = None
) -> None:
    """Assert response is an error MCP response.

    Args:
        response: Parsed JSON response
        error_code: Expected error code (optional)
    """
    assert response["status"] == "error", f"Expected error, got: {response}"
    assert "error_code" in response
    assert "message" in response

    if error_code:
        assert response["error_code"] == error_code
