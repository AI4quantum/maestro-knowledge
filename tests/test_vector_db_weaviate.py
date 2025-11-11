# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import warnings

# Suppress all deprecation warnings from external packages immediately
warnings.filterwarnings("ignore", category=DeprecationWarning)


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
# Suppress external package deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import os
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Check if weaviate is available
try:
    import weaviate  # noqa: F401

    WEAVIATE_AVAILABLE = True
except ImportError:
    WEAVIATE_AVAILABLE = False

# Check if weaviate agents are available
try:
    import weaviate.agents  # noqa: F401

    WEAVIATE_AGENTS_AVAILABLE = True
except ImportError:
    WEAVIATE_AGENTS_AVAILABLE = False

from src.db.vector_db_weaviate import WeaviateVectorDatabase


@pytest.mark.skipif(not WEAVIATE_AVAILABLE, reason="weaviate not available")
@pytest.mark.unit
class TestWeaviateVectorDatabase:
    """Test cases for the WeaviateVectorDatabase implementation."""

    def test_supported_embeddings(self) -> None:
        """Test the supported_embeddings method."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = MagicMock()
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()
            embeddings = db.supported_embeddings()

            assert "default" in embeddings
            assert "text2vec-weaviate" in embeddings
            assert "text2vec-openai" in embeddings
            assert "text2vec-cohere" in embeddings
            assert "text2vec-huggingface" in embeddings
            assert "text-embedding-ada-002" in embeddings
            assert "text-embedding-3-small" in embeddings
            assert "text-embedding-3-large" in embeddings

    def test_init_with_collection_name(self) -> None:
        """Test WeaviateVectorDatabase initialization with custom collection name."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = MagicMock()
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase("TestCollection")

            assert db.collection_name == "TestCollection"
            assert db.client == mock_client

    def test_init_default_collection_name(self) -> None:
        """Test WeaviateVectorDatabase initialization with default collection name."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = MagicMock()
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()

            assert db.collection_name == "MaestroDocs"
            assert db.client == mock_client

    @pytest.mark.asyncio
    async def test_setup_collection_exists(self) -> None:
        """Test setup when collection already exists."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_client.collections.exists = AsyncMock(return_value=True)
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()
            await db.setup()

            # Should not create collection since it exists
            mock_client.collections.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_setup_collection_not_exists_default_embedding(self) -> None:
        """Test create_collection when collection doesn't exist with default embedding."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch("weaviate.classes.config.Configure") as mock_configure,
            patch("weaviate.classes.config.Property") as mock_property,
            patch("weaviate.classes.config.DataType") as mock_datatype,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_client.collections.exists = AsyncMock(return_value=False)
            mock_connect.return_value = mock_client

            # Mock the configuration objects
            mock_configure.Vectorizer.text2vec_weaviate.return_value = (
                "vectorizer_config"
            )
            mock_property.return_value = "property"
            mock_datatype.TEXT = "TEXT"

            db = WeaviateVectorDatabase()
            # Phase 2.6: setup() and create_collection() are separate
            await db.setup()
            await db.create_collection("MaestroDocs")

            # Should create collection since it doesn't exist
            mock_client.collections.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_collection_not_exists_custom_embedding(self) -> None:
        """Test create_collection when collection doesn't exist with custom embedding."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch("weaviate.classes.config.Configure") as mock_configure,
            patch("weaviate.classes.config.Property") as mock_property,
            patch("weaviate.classes.config.DataType") as mock_datatype,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_client.collections.exists = AsyncMock(return_value=False)
            mock_connect.return_value = mock_client

            # Mock the configuration objects
            mock_configure.Vectorizer.text2vec_openai.return_value = (
                "openai_vectorizer_config"
            )
            mock_property.return_value = "property"
            mock_datatype.TEXT = "TEXT"

            db = WeaviateVectorDatabase()
            # Phase 2.6: setup() and create_collection() are separate
            await db.setup(embedding="text-embedding-ada-002")
            await db.create_collection(
                "MaestroDocs", embedding="text-embedding-ada-002"
            )

            # Should create collection since it doesn't exist
            mock_client.collections.create.assert_called_once()

    def test_get_vectorizer_config_default(self) -> None:
        """Test getting vectorizer config for default embedding."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch("weaviate.classes.config.Configure") as mock_configure,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = MagicMock()
            mock_connect.return_value = mock_client

            # Mock the configuration
            mock_configure.Vectorizer.text2vec_weaviate.return_value = (
                "vectorizer_config"
            )

            db = WeaviateVectorDatabase()
            config = db._get_vectorizer_config("default")
            assert config == "vectorizer_config"  # Mocked return value

    def test_get_vectorizer_config_unsupported(self) -> None:
        """Test getting vectorizer config for unsupported embedding."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = MagicMock()
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()
            with pytest.raises(ValueError, match="Unsupported embedding"):
                db._get_vectorizer_config("unsupported-model")

    # Tests removed: Per-write embedding parameter no longer exists in Phase 2 refactoring
    # - test_write_documents_default_embedding: Embedding now set during setup()
    # - test_write_documents_custom_embedding: Custom embedding set during setup()
    # - test_write_documents_ignores_per_write_embedding_with_warning: No per-write param
    # - test_write_documents_unsupported_embedding: Validation now in setup()

    @pytest.mark.asyncio
    async def test_list_documents(self) -> None:
        """Test listing documents from Weaviate."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_collection = AsyncMock()
            mock_result = AsyncMock()
            mock_object1 = MagicMock()
            mock_object2 = MagicMock()

            # Mock the query result
            mock_object1.uuid = "uuid1"
            mock_object1.properties = {
                "url": "http://test1.com",
                "text": "content1",
                "metadata": '{"type": "webpage"}',
            }
            mock_object2.uuid = "uuid2"
            mock_object2.properties = {
                "url": "http://test2.com",
                "text": "content2",
                "metadata": '{"type": "webpage"}',
            }

            mock_result.objects = [mock_object1, mock_object2]
            mock_collection.query.fetch_objects.return_value = mock_result
            mock_client.collections.get.return_value = mock_collection
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()

            documents = await db.list_documents(limit=2, offset=0)

            assert len(documents) == 2
            assert documents[0]["id"] == "uuid1"
            assert documents[0]["url"] == "http://test1.com"
            assert documents[1]["id"] == "uuid2"
            assert documents[1]["url"] == "http://test2.com"

    @pytest.mark.asyncio
    async def test_count_documents(self) -> None:
        """Test counting documents in Weaviate."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_collection = AsyncMock()
            mock_result = AsyncMock()

            # Create mock objects to simulate the fetch_objects result
            mock_object1 = MagicMock()
            mock_object2 = MagicMock()
            mock_object3 = MagicMock()
            mock_object4 = MagicMock()
            mock_object5 = MagicMock()

            mock_result.objects = [
                mock_object1,
                mock_object2,
                mock_object3,
                mock_object4,
                mock_object5,
            ]
            mock_collection.query.fetch_objects.return_value = mock_result
            mock_client.collections.get.return_value = mock_collection
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()
            count = await db.count_documents()

            assert count == 5

    @pytest.mark.asyncio
    async def test_list_collections(self) -> None:
        """Test listing collections in Weaviate."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()

            # Create mock collections
            mock_collection1 = MagicMock()
            mock_collection1.name = "Collection1"
            mock_collection2 = MagicMock()
            mock_collection2.name = "Collection2"
            mock_collection3 = MagicMock()
            mock_collection3.name = "MaestroDocs"

            mock_client.collections.list_all.return_value = [
                mock_collection1,
                mock_collection2,
                mock_collection3,
            ]
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()
            collections = await db.list_collections()

            assert collections == ["Collection1", "Collection2", "MaestroDocs"]
            mock_client.collections.list_all.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_collections_exception(self) -> None:
        """Test listing collections when an exception occurs."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = MagicMock()
            mock_client.collections.list_all.side_effect = Exception("Connection error")
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()
            # Suppress the expected warning for this test
            with pytest.warns(
                UserWarning, match="Could not list collections from Weaviate"
            ):
                collections = await db.list_collections()

            assert collections == []

    @pytest.mark.asyncio
    async def test_delete_documents(self) -> None:
        """Test deleting documents from Weaviate."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_collection = AsyncMock()
            mock_client.collections.get.return_value = mock_collection
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()
            await db.delete_documents(["uuid1", "uuid2"])

            # Verify delete_by_id was called for each document
            assert mock_collection.data.delete_by_id.call_count == 2
            mock_collection.data.delete_by_id.assert_any_call("uuid1")
            mock_collection.data.delete_by_id.assert_any_call("uuid2")

    @pytest.mark.asyncio
    async def test_delete_collection(self) -> None:
        """Test deleting a collection from Weaviate."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_client.collections.exists = AsyncMock(return_value=True)
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase("TestCollection")
            await db.delete_collection()

            mock_client.collections.delete.assert_called_once_with("TestCollection")
            assert db.collection_name is None

    @pytest.mark.skipif(
        not WEAVIATE_AGENTS_AVAILABLE, reason="weaviate agents not available"
    )
    def test_create_query_agent(self) -> None:
        """Test creating a query agent."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch("weaviate.agents.query.QueryAgent") as mock_query_agent,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = MagicMock()
            mock_connect.return_value = mock_client
            mock_agent = MagicMock()
            mock_query_agent.return_value = mock_agent

            db = WeaviateVectorDatabase()
            agent = db.create_query_agent()

            # The actual QueryAgent is created, not the mock, so we just verify it's not None
            assert agent is not None

    @pytest.mark.asyncio
    async def test_cleanup(self) -> None:
        """Test cleanup method."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = MagicMock()
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()
            await db.cleanup()

            # Verify client is set to None after cleanup
            assert db.client is None

    def test_db_type_property(self) -> None:
        """Test the db_type property."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = MagicMock()
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()

            assert db.db_type == "weaviate"

    @pytest.mark.asyncio
    async def test_get_collection_info_includes_chunking(self) -> None:
        """get_collection_info should include chunking config set at create_collection time."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            # Mock client and collection
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client

            # Create a regular Mock for the collection but with async methods where needed
            mock_collection = MagicMock()
            mock_client.collections = MagicMock()
            mock_client.collections.exists = AsyncMock(return_value=True)
            mock_client.collections.get = AsyncMock(return_value=mock_collection)

            # Mock the async query.fetch_objects method
            mock_result = MagicMock()
            mock_result.objects = [MagicMock(), MagicMock()]  # Simulate 2 documents
            mock_collection.query = MagicMock()
            mock_collection.query.fetch_objects = AsyncMock(return_value=mock_result)

            # Mock the config.get method (non-async)
            mock_cfg = MagicMock()
            mock_cfg.description = "Test collection"
            mock_cfg.vectorizer = "text2vec-openai"
            mock_cfg.properties = []
            mock_cfg.module_config = {}
            mock_collection.config = MagicMock()
            mock_collection.config.get = MagicMock(return_value=mock_cfg)

            db = WeaviateVectorDatabase()
            chunk_cfg = {
                "strategy": "Fixed",
                "parameters": {"chunk_size": 512, "overlap": 0},
            }
            # Phase 2.6: setup() and create_collection() are separate
            await db.setup(embedding="text-embedding-3-small")
            await db.create_collection(
                collection_name="InfoCol",
                embedding="text-embedding-3-small",
                chunking_config=chunk_cfg,
            )

            info = await db.get_collection_info("InfoCol")
            assert info["name"] == "InfoCol"
            assert info["db_type"] == "weaviate"
            assert info.get("chunking") == chunk_cfg
            # embedding may be stored as we set in create_collection
            assert info.get("embedding") in (
                "text-embedding-3-small",
                "text2vec-openai",
            )

    @pytest.mark.asyncio
    async def test_get_document_success(self) -> None:
        """Test successfully getting a document by name."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_collection = AsyncMock()
            mock_result = AsyncMock()

            # Create mock objects representing two chunks for the same document
            mock_object1 = MagicMock()
            mock_object1.uuid = "chunk1"
            mock_object1.properties = {
                "url": "test_url",
                "text": "Hello ",
                "metadata": {
                    "doc_name": "test_doc",
                    "collection_name": "test_collection",
                    "chunk_sequence_number": 1,
                    "total_chunks": 2,
                },
            }

            mock_object2 = MagicMock()
            mock_object2.uuid = "chunk2"
            mock_object2.properties = {
                "url": "test_url",
                "text": "World",
                "metadata": {
                    "doc_name": "test_doc",
                    "collection_name": "test_collection",
                    "chunk_sequence_number": 2,
                    "total_chunks": 2,
                },
            }

            mock_result.objects = [mock_object1, mock_object2]
            mock_collection.query.fetch_objects.return_value = mock_result
            mock_client.collections.exists = AsyncMock(return_value=True)
            mock_client.collections.get.return_value = mock_collection
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()
            result = await db.get_document("test_doc", "test_collection")

            assert result["id"] in ("chunk1", "chunk2")
            assert result["url"] == "test_url"
            assert result["text"] == "Hello World"
            assert result["metadata"]["doc_name"] == "test_doc"
            assert result["metadata"]["collection_name"] == "test_collection"

    @pytest.mark.asyncio
    async def test_get_document_collection_not_found(self) -> None:
        """Test getting a document when collection doesn't exist."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_client.collections.exists = AsyncMock(return_value=False)
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()

            with pytest.raises(
                ValueError, match="Collection 'test_collection' not found"
            ):
                await db.get_document("test_doc", "test_collection")

    @pytest.mark.asyncio
    async def test_get_document_document_not_found(self) -> None:
        """Test getting a document when document doesn't exist."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_collection = AsyncMock()
            mock_result = AsyncMock()

            # No objects returned
            mock_result.objects = []
            mock_collection.query.fetch_objects.return_value = mock_result
            mock_client.collections.exists = AsyncMock(return_value=True)
            mock_client.collections.get.return_value = mock_collection
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()

            with pytest.raises(
                ValueError,
                match="Document 'test_doc' not found in collection 'test_collection'",
            ):
                await db.get_document("test_doc", "test_collection")

    @pytest.mark.asyncio
    async def test_get_document_no_matching_doc_name(self) -> None:
        """Test getting a document when no document has the specified name."""
        with (
            patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
            patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test-key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ),
        ):
            mock_client = AsyncMock()
            mock_collection = AsyncMock()
            mock_result = AsyncMock()

            # Create mock object with different doc_name
            mock_object = MagicMock()
            mock_object.properties = {
                "url": "test_url",
                "text": "test content",
                "metadata": {
                    "doc_name": "different_doc",
                    "collection_name": "test_collection",
                },
            }

            mock_result.objects = [mock_object]
            mock_collection.query.fetch_objects.return_value = mock_result
            mock_client.collections.exists = AsyncMock(return_value=True)
            mock_client.collections.get.return_value = mock_collection
            mock_connect.return_value = mock_client

            db = WeaviateVectorDatabase()

            with pytest.raises(
                ValueError,
                match="Document 'test_doc' not found in collection 'test_collection'",
            ):
                await db.get_document("test_doc", "test_collection")
