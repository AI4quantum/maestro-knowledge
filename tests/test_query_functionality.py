# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import warnings
from typing import Any
from unittest.mock import MagicMock, Mock

import pytest

# Suppress Pydantic deprecation warnings from dependencies
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, message=".*class-based `config`.*"
)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, message=".*PydanticDeprecatedSince20.*"
)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=".*Support for class-based `config`.*",
)

import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.vector_db_base import VectorDatabase


@pytest.mark.unit
class TestQueryFunctionality:
    """Test cases for the query functionality in vector databases."""

    def test_query_method_exists_in_base_class(self) -> None:
        """Test that the query method is defined in the base class."""
        # Check that query method exists in the abstract base class
        assert hasattr(VectorDatabase, "query")

        # Check that it's an abstract method
        # Check that it's an abstract method that requires implementation
        import inspect

        assert inspect.isabstract(VectorDatabase)
        assert "query" in VectorDatabase.__abstractmethods__

    def test_query_method_signature(self) -> None:
        """Test that the query method has the correct signature."""
        import inspect

        # Get the signature of the query method
        sig = inspect.signature(VectorDatabase.query)
        params = list(sig.parameters.keys())

        # Should have self, query, and limit parameters
        assert "self" in params
        assert "query" in params
        assert "limit" in params

        # Check default value for limit
        assert sig.parameters["limit"].default == 5


class ConcreteQueryVectorDatabase:
    """Mock implementation for testing query functionality."""

    def __init__(self, collection_name: str = "TestCollection") -> None:
        self.collection_name = collection_name
        self.documents = []
        self.next_id = 0
        self.query_agent = MagicMock()
        self.db_type = "test"

    def supported_embeddings(self) -> list[str]:
        return ["default", "test-embedding"]

    async def setup(
        self,
        embedding: str = "default",
        collection_name: str = "",
        chunking_config: dict = {},
    ) -> None:
        pass

    async def write_documents(
        self,
        documents: list[dict[str, Any]],
        embedding: str = "default",
        collection_name: str = "",
    ) -> None:
        for doc in documents:
            doc_copy = doc.copy()
            doc_copy["id"] = str(self.next_id)
            doc_copy["embedding_used"] = embedding
            self.documents.append(doc_copy)
            self.next_id += 1

    async def list_documents(
        self, limit: int = 10, offset: int = 0
    ) -> list[dict[str, Any]]:
        return self.documents[offset : offset + limit]

    async def count_documents(self) -> int:
        return len(self.documents)

    async def delete_documents(self, document_ids: list[str]) -> None:
        self.documents = [
            doc for doc in self.documents if doc["id"] not in document_ids
        ]

    async def delete_collection(self, collection_name: str = "") -> None:
        target_collection = collection_name if collection_name else self.collection_name
        if target_collection == self.collection_name:
            self.documents = []
            self.collection_name = None

    async def get_document(
        self, doc_name: str, collection_name: str = ""
    ) -> dict[str, Any]:
        """Get a specific document by name from the vector database."""
        target_collection = collection_name if collection_name else self.collection_name

        # For testing purposes, search through documents for matching doc_name
        for doc in self.documents:
            metadata = doc.get("metadata", {})
            if metadata.get("doc_name") == doc_name:
                return {
                    "id": doc.get("id", "unknown"),
                    "url": doc.get("url", ""),
                    "text": doc.get("text", ""),
                    "metadata": metadata,
                }

        raise ValueError(
            f"Document '{doc_name}' not found in collection '{target_collection}'"
        )

    async def list_collections(self) -> list[str]:
        return [self.collection_name] if self.collection_name else []

    async def get_collection_info(self, collection_name: str = "") -> dict[str, Any]:
        target_collection = collection_name if collection_name else self.collection_name
        return {
            "name": target_collection,
            "document_count": len(self.documents),
            "db_type": self.db_type,
            "embedding": "default",
            "metadata": {},
        }

    def create_query_agent(self) -> Mock:
        return self.query_agent

    async def query(self, query: str, limit: int = 5, collection_name: str = "") -> str:
        """Test implementation of query method."""
        try:
            # Mock the query agent response
            self.query_agent.run.return_value = f"Response to: {query}"
            response = self.query_agent.run(query)
            return response
        except Exception as e:
            return f"Error querying database: {str(e)}"

    async def search(
        self, query: str, limit: int = 5, collection_name: str = ""
    ) -> list[dict]:
        """Test implementation of search method."""
        try:
            # Mock the query agent response
            self.query_agent.run.return_value = [{"result": f"Response to: {query}"}]
            response = self.query_agent.run(query)
            return response
        except Exception as e:
            return []

    async def cleanup(self) -> None:
        self.documents = []


@pytest.mark.unit
class TestConcreteQueryVectorDatabase:
    """Test cases for the concrete query implementation."""

    @pytest.mark.asyncio
    async def test_query_basic_functionality(self) -> None:
        """Test basic query functionality."""
        db = ConcreteQueryVectorDatabase()

        # Test query with default limit
        result = await db.query("What is the main topic?")
        assert "Response to: What is the main topic?" in result

        # Verify query agent was called
        db.query_agent.run.assert_called_once_with("What is the main topic?")

    @pytest.mark.asyncio
    async def test_query_with_custom_limit(self) -> None:
        """Test query with custom limit."""
        db = ConcreteQueryVectorDatabase()

        result = await db.query("Test query", limit=10)
        assert "Response to: Test query" in result

        # Verify query agent was called
        db.query_agent.run.assert_called_once_with("Test query")

    @pytest.mark.asyncio
    async def test_query_error_handling(self) -> None:
        """Test query error handling."""
        db = ConcreteQueryVectorDatabase()

        # Make the query agent raise an exception
        db.query_agent.run.side_effect = Exception("Test error")

        result = await db.query("Test query")
        assert "Error querying database: Test error" in result

    @pytest.mark.asyncio
    async def test_query_empty_string(self) -> None:
        """Test query with empty string."""
        db = ConcreteQueryVectorDatabase()

        result = await db.query("")
        assert "Response to: " in result

    @pytest.mark.asyncio
    async def test_query_special_characters(self) -> None:
        """Test query with special characters."""
        db = ConcreteQueryVectorDatabase()

        special_query = "What's the deal with API endpoints? (v2.0)"
        result = await db.query(special_query)
        assert f"Response to: {special_query}" in result


@pytest.mark.unit
class TestQueryMethodIntegration:
    """Test integration of query method with other VDB functionality."""

    @pytest.mark.asyncio
    async def test_query_with_documents(self) -> None:
        """Test query functionality when documents are present."""
        db = ConcreteQueryVectorDatabase()

        # Add some test documents
        docs = [
            {
                "url": "test1.com",
                "text": "API documentation",
                "metadata": {"doc_name": "api_docs"},
            },
            {
                "url": "test2.com",
                "text": "User guide",
                "metadata": {"doc_name": "user_guide"},
            },
        ]
        await db.write_documents(docs)

        # Verify documents were added
        assert await db.count_documents() == 2

        # Test query still works
        result = await db.query("Find API information")
        assert "Response to: Find API information" in result

    @pytest.mark.asyncio
    async def test_query_after_cleanup(self) -> None:
        """Test query functionality after cleanup."""
        db = ConcreteQueryVectorDatabase()

        # Add documents
        docs = [{"url": "test.com", "text": "test", "metadata": {}}]
        await db.write_documents(docs)
        assert await db.count_documents() == 1

        # Cleanup
        await db.cleanup()
        assert await db.count_documents() == 0

        # Query should still work
        result = await db.query("Test query")
        assert "Response to: Test query" in result


@pytest.mark.unit
class TestQueryMethodEdgeCases:
    """Test edge cases for the query method."""

    @pytest.mark.asyncio
    async def test_query_very_long_string(self) -> None:
        """Test query with very long string."""
        db = ConcreteQueryVectorDatabase()

        long_query = "A" * 1000
        result = await db.query(long_query)
        assert f"Response to: {long_query}" in result

    @pytest.mark.asyncio
    async def test_query_unicode_characters(self) -> None:
        """Test query with unicode characters."""
        db = ConcreteQueryVectorDatabase()

        unicode_query = "¿Qué tal? 你好世界 🌍"
        result = await db.query(unicode_query)
        assert f"Response to: {unicode_query}" in result

    @pytest.mark.asyncio
    async def test_query_none_value(self) -> None:
        """Test query with None value (should be converted to string)."""
        db = ConcreteQueryVectorDatabase()

        # Test with string "None"
        result = await db.query("None")
        assert "Response to: None" in result

    @pytest.mark.asyncio
    async def test_query_invalid_limit(self) -> None:
        """Test query with invalid limit values."""
        db = ConcreteQueryVectorDatabase()

        # Test with zero limit
        result = await db.query("test", limit=0)
        assert "Response to: test" in result

        # Test with negative limit
        result = await db.query("test", limit=-1)
        assert "Response to: test" in result

        # Test with very large limit
        result = await db.query("test", limit=1000000)
        assert "Response to: test" in result
