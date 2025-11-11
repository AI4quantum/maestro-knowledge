# SPDX-License-Identifier: Apache 2.0
# Test for resync_vector_databases helper

import os
import sys
from typing import Any

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.maestro_mcp import server


@pytest.mark.unit
@pytest.mark.asyncio
async def test_resync_vector_databases_registers_collections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mock MilvusVectorDatabase to return a predictable list and verify registration."""

    class DummyMilvus:
        def __init__(self, collection_name: str = None) -> None:
            self.collection_name = collection_name
            self.client = True

        def _ensure_client(self) -> None:
            # no-op
            return

        async def list_collections(self) -> list[str]:
            return ["coll_a", "coll_b"]

    # Patch the MilvusVectorDatabase import inside the server module
    monkeypatch.setattr(server, "MilvusVectorDatabase", DummyMilvus, raising=False)

    # Ensure the vector_databases dict is empty
    server.vector_databases.clear()

    added = await server.resync_vector_databases()

    assert set(added) == {"coll_a", "coll_b"}
    # Ensure that the vector_databases dict has entries for the collections
    assert "coll_a" in server.vector_databases
    assert "coll_b" in server.vector_databases
