# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import warnings

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

import asyncio
import os
import sys
from typing import Any

import pytest

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.vector_db_base import VectorDatabase


@pytest.mark.unit
class TestVectorDatabase:
    """Test cases for the VectorDatabase abstract base class."""

    def test_vector_database_abstract(self) -> None:
        """Test that VectorDatabase is abstract and cannot be instantiated."""
        with pytest.raises(TypeError):
            VectorDatabase()


class ConcreteVectorDatabase(VectorDatabase):
    """Concrete implementation for testing abstract methods."""

    def __init__(self, collection_name: str = "TestCollection") -> None:
        super().__init__(collection_name)
        self.documents = []
        self.next_id = 0
        self.embedding_model = "default"

    @property
    def db_type(self) -> str:
        return "test"

    def supported_embeddings(self) -> list[str]:
        return ["default", "test-embedding"]

    def setup(self, embedding: str = "default", collection_name: str = None) -> None:
        self.embedding_model = embedding
        if collection_name:
            self.collection_name = collection_name

    async def write_documents(
        self,
        documents: list[dict[str, Any]],
        collection_name: str = None,
    ) -> None:
        for doc in documents:
            doc_copy = doc.copy()
            doc_copy["id"] = str(self.next_id)
            doc_copy["embedding_used"] = self.embedding_model
            self.documents.append(doc_copy)
            self.next_id += 1

    def list_documents(self, limit: int = 10, offset: int = 0) -> list[dict[str, Any]]:
        return self.documents[offset : offset + limit]

    def count_documents(self) -> int:
        return len(self.documents)

    async def delete_documents(self, document_ids: list[str]) -> None:
        self.documents = [
            doc for doc in self.documents if doc["id"] not in document_ids
        ]

    def delete_collection(self, collection_name: str = None) -> None:
        target_collection = collection_name or self.collection_name
        if target_collection == self.collection_name:
            self.documents = []
            self.collection_name = None

    def get_document(
        self, doc_name: str, collection_name: str = None
    ) -> dict[str, Any]:
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

    def list_collections(self) -> list[str]:
        """List all collections in the vector database."""
        # For testing purposes, return a list with the current collection if it exists
        if self.collection_name:
            return [self.collection_name]
        return []

    def get_collection_info(self, collection_name: str = None) -> dict[str, Any]:
        """Get detailed information about a collection."""
        target_collection = collection_name or self.collection_name
        return {
            "name": target_collection,
            "document_count": len(self.documents),
            "db_type": "test",
            "embedding": "default",
            "metadata": {"test_collection": True, "documents": len(self.documents)},
        }

    def create_query_agent(self) -> "VectorDatabase":
        return self

    def cleanup(self) -> None:
        self.documents = []

    def query(self, query: str, limit: int = 5, collection_name: str = None) -> str:
        return f"Dummy query response: {query} (limit={limit})"

    def search(
        self, query: str, limit: int = 5, collection_name: str = None
    ) -> list[dict]:
        return [{"result": f"Dummy search response: {query} (limit={limit})"}]


@pytest.mark.unit
class TestConcreteVectorDatabase:
    """Test cases for the concrete implementation of VectorDatabase."""

    def test_supported_embeddings(self) -> None:
        """Test the supported_embeddings method."""
        db = ConcreteVectorDatabase()
        embeddings = db.supported_embeddings()
        assert "default" in embeddings
        assert "test-embedding" in embeddings
        assert len(embeddings) == 2

    @pytest.mark.asyncio
    async def test_write_document_singular(self) -> None:
        """Test the singular write_document method."""
        db = ConcreteVectorDatabase()
        db.setup(embedding="default")
        doc = {"url": "test.com", "text": "test", "metadata": {"key": "value"}}

        await db.write_document(doc)
        assert len(db.documents) == 1
        assert db.documents[0]["url"] == "test.com"
        assert db.documents[0]["embedding_used"] == "default"

    @pytest.mark.asyncio
    async def test_write_document_with_embedding(self) -> None:
        """Test the write_document method uses embedding from setup."""
        db = ConcreteVectorDatabase()
        db.setup(embedding="test-embedding")
        doc = {"url": "test.com", "text": "test", "metadata": {"key": "value"}}

        await db.write_document(doc)
        assert len(db.documents) == 1
        assert db.documents[0]["embedding_used"] == "test-embedding"

    @pytest.mark.asyncio
    async def test_write_documents_with_embedding(self) -> None:
        """Test the write_documents method uses embedding from setup."""
        db = ConcreteVectorDatabase()
        db.setup(embedding="test-embedding")
        docs = [
            {"url": "test1.com", "text": "test1", "metadata": {}},
            {"url": "test2.com", "text": "test2", "metadata": {}},
        ]

        await db.write_documents(docs)
        assert len(db.documents) == 2
        assert all(doc["embedding_used"] == "test-embedding" for doc in db.documents)

    @pytest.mark.asyncio
    async def test_delete_document_singular(self) -> None:
        """Test the singular delete_document method."""
        db = ConcreteVectorDatabase()
        doc = {"url": "test.com", "text": "test", "metadata": {"key": "value"}}

        await db.write_document(doc)
        assert len(db.documents) == 1

        await db.delete_document("0")
        assert len(db.documents) == 0

    @pytest.mark.asyncio
    async def test_count_documents(self) -> None:
        """Test the count_documents method."""
        db = ConcreteVectorDatabase()
        assert db.count_documents() == 0

        doc1 = {"url": "test1.com", "text": "test1", "metadata": {}}
        doc2 = {"url": "test2.com", "text": "test2", "metadata": {}}

        await db.write_documents([doc1, doc2])
        assert db.count_documents() == 2

    @pytest.mark.asyncio
    async def test_delete_documents_multiple(self) -> None:
        """Test the delete_documents method with multiple IDs."""
        db = ConcreteVectorDatabase()
        doc1 = {"url": "test1.com", "text": "test1", "metadata": {}}
        doc2 = {"url": "test2.com", "text": "test2", "metadata": {}}
        doc3 = {"url": "test3.com", "text": "test3", "metadata": {}}

        await db.write_documents([doc1, doc2, doc3])
        assert db.count_documents() == 3

        await db.delete_documents(["0", "2"])
        assert db.count_documents() == 1
        assert db.documents[0]["url"] == "test2.com"

    @pytest.mark.asyncio
    async def test_delete_collection(self) -> None:
        """Test the delete_collection method."""
        db = ConcreteVectorDatabase("TestCollection")
        doc = {"url": "test.com", "text": "test", "metadata": {}}

        await db.write_document(doc)
        assert db.count_documents() == 1
        assert db.collection_name == "TestCollection"

        db.delete_collection()
        assert db.count_documents() == 0
        assert db.collection_name is None

    @pytest.mark.asyncio
    async def test_delete_collection_specific_name(self) -> None:
        """Test the delete_collection method with specific collection name."""
        db = ConcreteVectorDatabase("TestCollection")
        doc = {"url": "test.com", "text": "test", "metadata": {}}

        await db.write_document(doc)
        assert db.count_documents() == 1

        # Delete a different collection name (should not affect current collection)
        db.delete_collection("DifferentCollection")
        assert db.count_documents() == 1
        assert db.collection_name == "TestCollection"
