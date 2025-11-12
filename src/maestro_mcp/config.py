# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""Configuration and environment management for MCP server."""

import logging
import os
from collections.abc import Awaitable, Callable
import asyncio
from typing import Any

logger = logging.getLogger(__name__)


def load_env_file() -> None:
    """Load environment variables from .env file."""
    env_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
    )
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value


# Default timeout (in seconds) for MCP tool execution. Can be overridden via env.
DEFAULT_TOOL_TIMEOUT = int(os.getenv("MCP_TOOL_TIMEOUT", "15"))

# Per-category timeout defaults (seconds).
# Override via environment variables MCP_TIMEOUT_<CATEGORY>, e.g., MCP_TIMEOUT_QUERY=45
TIMEOUT_DEFAULTS: dict[str, int] = {
    "health": 30,
    "list_databases": 15,
    "list_collections": 15,
    "list_documents": 30,
    "count_documents": 15,
    "get_database_info": 15,
    "get_collection_info": 30,
    "query": 30,
    "search": 30,
    "write_single": 900,  # 15 minutes
    "write_bulk": 3600,  # 60 minutes
    "delete": 60,
    "cleanup": 60,
    "create_collection": 60,
    "setup_database": 60,
    "resync": 60,
}


def get_timeout(category: str, fallback: int | None = None) -> int:
    """Resolve timeout for a category from env or defaults.

    Env var format: MCP_TIMEOUT_<CATEGORY>, e.g., MCP_TIMEOUT_QUERY=45
    """
    env_key = f"MCP_TIMEOUT_{category.upper()}"
    val = os.getenv(env_key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    if fallback is not None:
        return fallback
    return TIMEOUT_DEFAULTS.get(category, DEFAULT_TOOL_TIMEOUT)


def tool_timeout(
    seconds: int | None = None,
) -> Callable[[Callable[..., Awaitable[object]]], Callable[..., Awaitable[object]]]:
    """Decorator to enforce a timeout and guaranteed response for MCP tools.

    Ensures that every tool returns a response even if an operation hangs or raises.
    Timeout is configurable via MCP_TOOL_TIMEOUT env var or the decorator argument.
    """

    def decorator(
        func: Callable[..., Awaitable[object]],
    ) -> Callable[..., Awaitable[object]]:
        async def wrapper(*args: object, **kwargs: object) -> object:
            timeout_s = seconds if seconds is not None else DEFAULT_TOOL_TIMEOUT
            func_name = getattr(func, "__name__", "tool")

            # Create task explicitly to enable proper cancellation on timeout
            task = asyncio.create_task(func(*args, **kwargs))  # type: ignore[arg-type]
            try:
                return await asyncio.wait_for(task, timeout=timeout_s)
            except asyncio.TimeoutError:
                logger.error(
                    "Tool '%s' timed out after %s seconds", func_name, timeout_s
                )
                # Properly cancel the task to avoid resource leaks
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected when we cancel
                return f"Error: '{func_name}' timed out after {timeout_s} seconds"
            except Exception as e:
                # Catch any uncaught exceptions so we always return a response
                logger.exception("Tool '%s' failed: %s", func_name, e)
                return f"Error: {str(e)}"

        return wrapper

    return decorator


async def run_with_timeout(
    awaitable: Awaitable[Any], tool_name: str, timeout_s: int | None = None
) -> tuple[bool, Any]:
    """Run an awaitable with a timeout, return (ok, result_or_error_message).

    If the awaitable completes, returns (True, result). If it times out, returns
    (False, error_message). Any other exception is caught and returned as (False, error_message).
    """
    to = timeout_s if timeout_s is not None else DEFAULT_TOOL_TIMEOUT

    # Create task explicitly to enable proper cancellation on timeout
    # Use type: ignore to handle Awaitable -> Coroutine conversion
    task = asyncio.create_task(awaitable)  # type: ignore[arg-type]
    try:
        result = await asyncio.wait_for(task, timeout=to)
        return True, result
    except asyncio.TimeoutError:
        logger.error("Tool '%s' timed out after %s seconds", tool_name, to)
        # Properly cancel the task to avoid resource leaks
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected when we cancel
        return False, f"Error: '{tool_name}' timed out after {to} seconds"
    except Exception as e:
        logger.exception("Tool '%s' failed: %s", tool_name, e)
        return False, f"Error: {str(e)}"


# Made with Bob
