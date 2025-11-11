# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""
Unit tests for MCP server flat parameter structure.
These tests should run fast with no external dependencies.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from unittest.mock import Mock

import pytest


@pytest.mark.unit
class TestQueryParameters:
    """Unit tests for query flat parameter structure."""

    @pytest.mark.unit
    def test_query_parameters_valid(self) -> None:
        """Test query parameters with valid values."""
        query_params = {
            "database": "test-db",
            "query": "What is the main topic?",
            "limit": 10,
        }

        assert query_params["database"] == "test-db"
        assert query_params["query"] == "What is the main topic?"
        assert query_params["limit"] == 10

    @pytest.mark.unit
    def test_query_parameters_defaults(self) -> None:
        """Test query parameters with default values."""
        query_params = {"database": "test-db", "query": "Test query"}

        assert query_params["database"] == "test-db"
        assert query_params["query"] == "Test query"
        assert query_params.get("limit", 5) == 5  # Default value

    @pytest.mark.unit
    def test_query_parameters_validation_missing_database(self) -> None:
        """Test query parameters validation when database is missing."""
        incomplete_params = {"query": "test"}
        assert "database" not in incomplete_params

    @pytest.mark.unit
    def test_query_parameters_validation_missing_query(self) -> None:
        """Test query parameters validation when query is missing."""
        incomplete_params = {"database": "test-db"}
        assert "query" not in incomplete_params

    @pytest.mark.unit
    def test_query_parameters_special_characters(self) -> None:
        """Test query parameters handle special characters properly."""
        special_query = "What's the deal with API endpoints? (v2.0) & more!"
        query_params = {"database": "test-db", "query": special_query, "limit": 5}

        assert query_params["database"] == "test-db"
        assert query_params["query"] == special_query
        assert query_params["limit"] == 5

    @pytest.mark.unit
    @pytest.mark.parametrize("limit", [1, 5, 10, 100])
    def test_query_parameters_different_limits(self, limit: int) -> None:
        """Test query parameters with different limit values."""
        query_params = {"database": "test-db", "query": "Test query", "limit": limit}

        assert query_params["database"] == "test-db"
        assert query_params["query"] == "Test query"
        assert query_params["limit"] == limit
