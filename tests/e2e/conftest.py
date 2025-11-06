import asyncio
from collections.abc import Generator

import pytest
from tests.e2e.common import mcp_http_server

# This file registers the mcp_http_server fixture for pytest discovery in tests/e2e


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Create a session-scoped event loop for E2E tests.
    This prevents event loop closure issues with gRPC async clients.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
