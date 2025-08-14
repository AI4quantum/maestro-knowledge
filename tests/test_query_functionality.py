# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import warnings
import pytest
from unittest.mock import Mock
from typing import Dict, Any

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

import sys
import os

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.vector_db_base import VectorDatabase


class TestQueryFunctionality:
    """Test cases for the query functionality in vector databases."""

    def test_query_method_exists_in_base_class(self):
        """Test that the query method is defined in the base class."""
        # Check that query method exists in the abstract base class
        assert hasattr(VectorDatabase, "query")

        # Check that it's an abstract method
        with pytest.raises(TypeError):
            VectorDatabase().query("test query")

    def test_query_method_signature(self):
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


class ConcreteQueryVectorDatabase(VectorDatabase):
    """Concrete implementation for testing query functionality."""

    def __init__(self, collection_name: str = "TestCollection"):
        super().__init__(collection_name)
        self.documents = []
        self.next_id = 0
        self.query_agent = Mock()

    @property
    def db_type(self) -> str:
        return "test"

    def supported_embeddings(self):
        return ["default", "test-embedding"]

    def setup(self, embedding: str = "default", collection_name: str = None):
        pass

    def write_documents(self, documents, embedding="default"):
        for doc in documents:
            doc_copy = doc.copy()
            doc_copy["id"] = str(self.next_id)
            doc_copy["embedding_used"] = embedding
            self.documents.append(doc_copy)
            self.next_id += 1

    def list_documents(self, limit=10, offset=0):
        return self.documents[offset : offset + limit]

    def count_documents(self) -> int:
        return len(self.documents)

    def delete_documents(self, document_ids):
        self.documents = [
            doc for doc in self.documents if doc["id"] not in document_ids
        ]

    def delete_collection(self, collection_name=None):
        target_collection = collection_name or self.collection_name
        if target_collection == self.collection_name:
            self.documents = []
            self.collection_name = None

    def get_document(
        self, doc_name: str, collection_name: str = None
    ) -> Dict[str, Any]:
        """Get a specific document by name from the vector database."""
        target_collection = collection_name or self.collection_name

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

    def list_collections(self):
        return [self.collection_name] if self.collection_name else []

    def get_collection_info(self, collection_name=None):
        target_collection = collection_name or self.collection_name
        return {
            "name": target_collection,
            "document_count": self.count_documents(),
            "db_type": self.db_type,
            "embedding": "default",
            "metadata": {},
        }

    def create_query_agent(self):
        return self.query_agent

    def query(self, query: str, limit: int = 5, collection_name: str = None) -> str:
        """Test implementation of query method."""
        try:
            # Mock the query agent response
            self.query_agent.run.return_value = f"Response to: {query}"
            response = self.query_agent.run(query)
            return response
        except Exception as e:
            return f"Error querying database: {str(e)}"

    def search(
        self, query: str, limit: int = 5, collection_name: str = None
    ) -> list[dict]:
        """Test implementation of search method."""
        try:
            # Mock the query agent response
            self.query_agent.run.return_value = [{"result": f"Response to: {query}"}]
            response = self.query_agent.run(query)
            return response
        except Exception as e:
            return f"Error querying database: {str(e)}"

    def cleanup(self):
        self.documents = []


class TestConcreteQueryVectorDatabase:
    """Test cases for the concrete query implementation."""

    def test_query_basic_functionality(self):
        """Test basic query functionality."""
        db = ConcreteQueryVectorDatabase()

        # Test query with default limit
        result = db.query("What is the main topic?")
        assert "Response to: What is the main topic?" in result

        # Verify query agent was called
        db.query_agent.run.assert_called_once_with("What is the main topic?")

    def test_query_with_custom_limit(self):
        """Test query with custom limit."""
        db = ConcreteQueryVectorDatabase()

        result = db.query("Test query", limit=10)
        assert "Response to: Test query" in result

        # Verify query agent was called
        db.query_agent.run.assert_called_once_with("Test query")

    def test_query_error_handling(self):
        """Test query error handling."""
        db = ConcreteQueryVectorDatabase()

        # Make the query agent raise an exception
        db.query_agent.run.side_effect = Exception("Test error")

        result = db.query("Test query")
        assert "Error querying database: Test error" in result

    def test_query_empty_string(self):
        """Test query with empty string."""
        db = ConcreteQueryVectorDatabase()

        result = db.query("")
        assert "Response to: " in result

    def test_query_special_characters(self):
        """Test query with special characters."""
        db = ConcreteQueryVectorDatabase()

        special_query = "What's the deal with API endpoints? (v2.0)"
        result = db.query(special_query)
        assert f"Response to: {special_query}" in result


class TestQueryMethodIntegration:
    """Test integration of query method with other VDB functionality."""

    def test_query_with_documents(self):
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
        db.write_documents(docs)

        # Verify documents were added
        assert db.count_documents() == 2

        # Test query still works
        result = db.query("Find API information")
        assert "Response to: Find API information" in result

    def test_query_after_cleanup(self):
        """Test query functionality after cleanup."""
        db = ConcreteQueryVectorDatabase()

        # Add documents
        docs = [{"url": "test.com", "text": "test", "metadata": {}}]
        db.write_documents(docs)
        assert db.count_documents() == 1

        # Cleanup
        db.cleanup()
        assert db.count_documents() == 0

        # Query should still work
        result = db.query("Test query")
        assert "Response to: Test query" in result


class TestQueryMethodEdgeCases:
    """Test edge cases for the query method."""

    def test_query_very_long_string(self):
        """Test query with very long string."""
        db = ConcreteQueryVectorDatabase()

        long_query = "A" * 1000
        result = db.query(long_query)
        assert f"Response to: {long_query}" in result

    def test_query_unicode_characters(self):
        """Test query with unicode characters."""
        db = ConcreteQueryVectorDatabase()

        unicode_query = "¿Qué tal? 你好世界 🌍"
        result = db.query(unicode_query)
        assert f"Response to: {unicode_query}" in result

    def test_query_none_value(self):
        """Test query with None value (should be converted to string)."""
        db = ConcreteQueryVectorDatabase()

        # None should be converted to string "None" by the query agent
        result = db.query(None)
        assert "Response to: None" in result

    def test_query_invalid_limit(self):
        """Test query with invalid limit values."""
        db = ConcreteQueryVectorDatabase()

        # Test with zero limit
        result = db.query("test", limit=0)
        assert "Response to: test" in result

        # Test with negative limit
        result = db.query("test", limit=-1)
        assert "Response to: test" in result

        # Test with very large limit
        result = db.query("test", limit=1000000)
        assert "Response to: test" in result
