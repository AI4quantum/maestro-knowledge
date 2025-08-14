# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import warnings
from abc import ABC, abstractmethod
from typing import List, Dict, Any

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


class VectorDatabase(ABC):
    """Abstract base class for vector database implementations."""

    @abstractmethod
    def __init__(self, collection_name: str = "MaestroDocs"):
        """Initialize the vector database with a collection name."""
        self.collection_name = collection_name

    @property
    @abstractmethod
    def db_type(self) -> str:
        """Return the type/name of the vector database."""
        pass

    @abstractmethod
    def supported_embeddings(self) -> List[str]:
        """
        Return a list of supported embedding model names for this vector database.

        Returns:
            List of supported embedding model names (e.g., ["default", "text-embedding-ada-002"])
        """
        pass

    @abstractmethod
    def setup(self, embedding: str = "default", collection_name: str = None):
        """
        Set up the database and create collections if they don't exist.

        Args:
            embedding: Embedding model to use for the collection
            collection_name: Name of the collection to set up (optional)
        """
        pass

    @abstractmethod
    def write_documents(
        self,
        documents: List[Dict[str, Any]],
        embedding: str = "default",
        collection_name: str = None,
    ):
        """
        Write documents to the vector database.

        Args:
            documents: List of documents with 'url', 'text', and 'metadata' fields.
                       For Milvus, documents may also include a 'vector' field.
            embedding: Embedding strategy to use. Options:
                      - "default": Use database's default embedding strategy
                      - Specific model name: Use the specified embedding model
            collection_name: Name of the collection to write to (optional)
        """
        pass

    def write_documents_to_collection(
        self,
        documents: List[Dict[str, Any]],
        collection_name: str,
        embedding: str = "default",
    ):
        """
        Write documents to a specific collection in the vector database.

        Args:
            documents: List of documents with 'url', 'text', and 'metadata' fields.
                       For Milvus, documents may also include a 'vector' field.
            collection_name: Name of the collection to write to
            embedding: Embedding strategy to use. Options:
                      - "default": Use database's default embedding strategy
                      - Specific model name: Use the specified embedding model
        """
        return self.write_documents(documents, embedding, collection_name)

    def write_document(
        self,
        document: Dict[str, Any],
        embedding: str = "default",
        collection_name: str = None,
    ):
        """
        Write a single document to the vector database.

        Args:
            document: Document with 'url', 'text', and 'metadata' fields.
                     For Milvus, document may also include a 'vector' field.
            embedding: Embedding strategy to use (see write_documents for options)
            collection_name: Name of the collection to write to (optional)
        """
        return self.write_documents([document], embedding, collection_name)

    @abstractmethod
    def list_documents(self, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """
        List documents from the vector database.

        Args:
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of documents with their properties
        """
        pass

    def list_documents_in_collection(
        self, collection_name: str, limit: int = 10, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List documents from a specific collection in the vector database.

        Args:
            collection_name: Name of the collection to list documents from
            limit: Maximum number of documents to return
            offset: Number of documents to skip

        Returns:
            List of documents with their properties
        """
        # Default implementation: temporarily switch collection and call list_documents
        original_collection = self.collection_name
        self.collection_name = collection_name
        try:
            return self.list_documents(limit, offset)
        finally:
            self.collection_name = original_collection

    @abstractmethod
    def get_document(
        self, doc_name: str, collection_name: str = None
    ) -> Dict[str, Any]:
        """
        Get a specific document by name from the vector database.

        Args:
            doc_name: Name of the document to retrieve
            collection_name: Name of the collection to search in. If None, uses the current collection.

        Returns:
            Document with its properties

        Raises:
            ValueError: If the document is not found
        """
        pass

    @abstractmethod
    def count_documents(self) -> int:
        """
        Get the current count of documents in the collection.

        Returns:
            Number of documents in the collection
        """
        pass

    def count_documents_in_collection(self, collection_name: str) -> int:
        """
        Get the current count of documents in a specific collection.

        Args:
            collection_name: Name of the collection to count documents in

        Returns:
            Number of documents in the collection
        """
        # Default implementation: temporarily switch collection and call count_documents
        original_collection = self.collection_name
        self.collection_name = collection_name
        try:
            return self.count_documents()
        finally:
            self.collection_name = original_collection

    @abstractmethod
    def list_collections(self) -> List[str]:
        """
        List all collections in the vector database.

        Returns:
            List of collection names
        """
        pass

    @abstractmethod
    def get_collection_info(self, collection_name: str = None) -> Dict[str, Any]:
        """
        Get detailed information about a collection.

        Args:
            collection_name: Name of the collection to get info for. If None, uses the current collection.

        Returns:
            Dictionary containing collection information including:
            - name: Collection name
            - document_count: Number of documents in the collection
            - db_type: Type of vector database
            - embedding: Default embedding used (if available)
            - metadata: Additional collection metadata
        """
        pass

    @abstractmethod
    def delete_documents(self, document_ids: List[str]):
        """
        Delete documents from the vector database by their IDs.

        Args:
            document_ids: List of document IDs to delete
        """
        pass

    def delete_document(self, document_id: str):
        """
        Delete a single document from the vector database by its ID.

        Args:
            document_id: Document ID to delete
        """
        return self.delete_documents([document_id])

    @abstractmethod
    def delete_collection(self, collection_name: str = None):
        """
        Delete an entire collection from the database.

        Args:
            collection_name: Name of the collection to delete. If None, uses the current collection.
        """
        pass

    @abstractmethod
    def create_query_agent(self):
        """Create and return a query agent for this vector database."""
        pass

    @abstractmethod
    def query(self, query: str, limit: int = 5, collection_name: str = None) -> str:
        """
        Query the vector database using the default query agent.

        Args:
            query: The query string to search for
            limit: Maximum number of results to consider
            collection_name: Optional collection name to search in

        Returns:
            A string response with relevant information from the database
        """
        pass

    @abstractmethod
    def search(
        self, query: str, limit: int = 5, collection_name: str = None
    ) -> list[dict]:
        """
        Search for documents using vector similarity search.

        Args:
            query: The search query text
            limit: Maximum number of results to return
            collection_name: Optional collection name to search in

        Returns:
            List of documents sorted by relevance
        """
        pass

    @abstractmethod
    def cleanup(self):
        """Clean up resources and close connections."""
        pass
