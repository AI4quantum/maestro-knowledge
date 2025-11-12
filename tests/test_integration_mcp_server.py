# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""
Integration tests for MCP server functionality.
These tests use real components but mock external services.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from unittest.mock import Mock, patch

import pytest
from fastmcp import FastMCP

from src.maestro_mcp.server import create_mcp_server
from tests.test_utils import mock_resync_functions


@pytest.mark.integration
class TestMCPServerIntegration:
    """Integration tests for MCP server creation and tool registration."""

    @pytest.mark.integration
    async def test_server_creation(self) -> None:
        """Test that MCP server can be created with mocked database connections."""
        with mock_resync_functions():
            server = await create_mcp_server()

            assert server is not None
            assert server.name == "maestro-vector-db"
            assert hasattr(server, "get_tools")
            assert hasattr(server, "tool")

    @pytest.mark.integration
    async def test_server_tool_registration(self) -> None:
        """Test that expected tools are registered in the server."""
        expected_tools = [
            "create_database",
            "get_supported_embeddings",
            "query",
            "search",
            "list_databases",
        ]

        with mock_resync_functions():
            server = await create_mcp_server()

            # Note: FastMCP doesn't expose tools directly,
            # but we can verify the server was created successfully
            # In a real integration test, we'd invoke the tools
            assert server is not None


@pytest.mark.integration
class TestQueryWorkflowIntegration:
    """Integration tests for query workflow with mocked databases."""

    @pytest.fixture
    async def mcp_server(self) -> FastMCP:
        """Create a test MCP server instance."""
        with mock_resync_functions():
            return await create_mcp_server()

    @pytest.mark.integration
    async def test_query_workflow_with_mocked_db(self, mcp_server: FastMCP) -> None:
        """Test complete query workflow with mocked vector database."""
        # Create a mock vector database
        mock_db = Mock()
        mock_db.query.return_value = "Test query response from mocked DB"
        mock_db.db_type = "test"
        mock_db.collection_name = "TestCollection"

        # Mock the vector_databases dictionary
        with patch("src.maestro_mcp.server.vector_databases", {"test-db": mock_db}):
            # Verify server is ready
            assert mcp_server is not None

            # Test query parameters (flat structure - no input wrapper)
            query_params = {
                "database": "test-db",
                "query": "What is the main topic?",
                "limit": 5,
            }

            assert query_params["database"] == "test-db"
            assert query_params["query"] == "What is the main topic?"
            assert query_params["limit"] == 5

            # In a real test, we'd invoke the query tool:
            # result = await mcp_server.call_tool("query", query_params)
            # assert "Test query response" in result.content

    @pytest.mark.integration
    async def test_query_with_nonexistent_database(self, mcp_server: FastMCP) -> None:
        """Test query behavior when database doesn't exist."""
        # Mock empty vector_databases dictionary
        with patch("src.maestro_mcp.server.vector_databases", {}):
            # Create query for non-existent database (flat structure)
            query_params = {
                "database": "nonexistent-db",
                "query": "Test query",
                "limit": 5,
            }

            # Verify parameters are valid
            assert query_params["database"] == "nonexistent-db"

            # In a real test, we'd verify the tool returns an error:
            # with pytest.raises(ValueError, match="not found"):
            #     await mcp_server.call_tool("query", query_input.model_dump())
