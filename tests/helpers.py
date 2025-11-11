# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import asyncio
import os


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
