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

# Suppress Milvus connection warnings during tests
warnings.filterwarnings(
    "ignore", category=UserWarning, message=".*Failed to connect to Milvus.*"
)
warnings.filterwarnings(
    "ignore", category=UserWarning, message=".*Milvus client is not available.*"
)
# Suppress external package deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import os
import sys
from unittest.mock import MagicMock, patch
from typing import Any

import pytest

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymilvus.exceptions import MilvusException

from src.db.vector_db_milvus import MilvusVectorDatabase


class TestMilvusVectorDatabase:
    """Test cases for the MilvusVectorDatabase implementation."""

    def test_supported_embeddings(self) -> None:
        """Test the supported_embeddings method."""
        db = MilvusVectorDatabase()
        embeddings = db.supported_embeddings()
        assert "default" in embeddings
        assert "text-embedding-ada-002" in embeddings
        assert "text-embedding-3-small" in embeddings
        assert "text-embedding-3-large" in embeddings

    @patch("pymilvus.MilvusClient")
    def test_init_with_collection_name(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase("TestCollection")
        assert db.collection_name == "TestCollection"
        # Client is not created until needed due to lazy initialization
        assert db.client is None
        # Trigger client creation
        db._ensure_client()
        assert db.client == mock_client

    @patch("pymilvus.MilvusClient")
    def test_setup_collection_exists(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        db.setup()
        mock_client.create_collection.assert_not_called()

    @patch("pymilvus.MilvusClient")
    def test_setup_collection_not_exists(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        db.dimension = 1536
        db.setup()
        mock_client.create_collection.assert_called_once_with(
            collection_name="MaestroDocs",
            dimension=1536,
            primary_field_name="id",
            vector_field_name="vector",
        )

    @patch("pymilvus.MilvusClient")
    def test_write_documents_with_precomputed_vector(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """Test writing documents with pre-computed vectors."""
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        documents = [
            {
                "url": "http://test1.com",
                "text": "test content 1",
                "metadata": {"type": "webpage"},
                "vector": [0.1] * 1536,
            },
            {
                "url": "http://test2.com",
                "text": "test content 2",
                "metadata": {"type": "webpage"},
                "vector": [0.2] * 1536,
            },
        ]
        db.write_documents(documents, embedding="default")
        assert mock_client.insert.called

    @patch("pymilvus.MilvusClient")
    def test_write_documents_with_embedding_model(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """Test writing documents with embedding model generation."""
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client

        db = MilvusVectorDatabase()

        # Mock the _generate_embedding method to return a test vector
        with patch.object(db, "_generate_embedding", return_value=[0.1] * 1536):
            documents = [
                {
                    "url": "http://test1.com",
                    "text": "test content 1",
                    "metadata": {"type": "webpage"},
                }
            ]

            # Set environment variable for OpenAI API key
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                db.write_documents(documents, embedding="text-embedding-ada-002")
                assert mock_client.insert.called

    @patch("pymilvus.MilvusClient")
    def test_write_documents_excludes_chunking_metadata(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """Write path should NOT attach chunking policy into per-chunk metadata (kept at collection level)."""
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client

        db = MilvusVectorDatabase("ChunkCol")
        # Configure collection chunking
        chunk_cfg = {
            "strategy": "Fixed",
            "parameters": {"chunk_size": 16, "overlap": 0},
        }
        # Also set embedding to avoid openai dependency by mocking _generate_embedding
        db.setup(
            embedding="text-embedding-ada-002",
            collection_name="ChunkCol",
            chunking_config=chunk_cfg,
        )

        # Mock embed generation
        with patch.object(
            db, "_generate_embedding", return_value=[0.0] * (db.dimension or 1536)
        ):
            documents = [
                {
                    "url": "u",
                    "text": "abcdefghijklmnopqrstuvwxyz",
                    "metadata": {"doc_name": "doc1"},
                }
            ]
            db.write_documents(documents, embedding="default")

        # Verify insert was called and metadata contains chunking
        assert mock_client.insert.called
        args, kwargs = mock_client.insert.call_args
        assert args[0] == "ChunkCol"
        data = args[1]
        assert isinstance(data, list) and len(data) > 0
        meta = data[0]["metadata"]
        # metadata stored as JSON string
        import json as _json

        parsed = _json.loads(meta)
        # Per-result chunking metadata has been removed to avoid duplication
        assert "chunking" not in parsed
        # Still includes prior fields
        assert "offset_start" in parsed and "offset_end" in parsed
        assert "chunk_sequence_number" in parsed and "total_chunks" in parsed

    @patch("pymilvus.MilvusClient")
    def test_get_collection_info_custom_local_includes_config(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """For custom_local embedding, collection info should include URL/model config."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_client.get_collection_stats.return_value = {"row_count": 0}
        mock_desc = MagicMock()
        mock_desc.fields = []
        mock_client.describe_collection.return_value = mock_desc
        mock_milvus_client.return_value = mock_client

        db = MilvusVectorDatabase("CfgCol")
        with patch.dict(
            os.environ,
            {
                "CUSTOM_EMBEDDING_URL": "http://localhost:11434/v1",
                "CUSTOM_EMBEDDING_MODEL": "nomic-embed-text",
                "CUSTOM_EMBEDDING_VECTORSIZE": "768",
            },
            clear=True,
        ):
            db.setup(
                embedding="custom_local",
                collection_name="CfgCol",
                chunking_config={
                    "strategy": "Fixed",
                    "parameters": {"chunk_size": 512, "overlap": 0},
                },
            )
            info = db.get_collection_info("CfgCol")

        ed = info.get("embedding_details", {})
        cfg = ed.get("config", {})
        assert cfg.get("url") == "http://localhost:11434/v1"
        assert cfg.get("model") == "nomic-embed-text"

    @patch("pymilvus.MilvusClient")
    def test_write_documents_unsupported_embedding(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """Test writing documents with unsupported embedding model."""
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        documents = [
            {
                "url": "http://test1.com",
                "text": "test content 1",
                "metadata": {"type": "webpage"},
            }
        ]
        with pytest.raises(ValueError, match="Unsupported embedding"):
            db.write_documents(documents, embedding="unsupported-model")

    @patch("pymilvus.MilvusClient")
    def test_write_documents_missing_openai_key(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """Test writing documents without OpenAI API key."""
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()

        # Mock the _generate_embedding method to simulate missing openai module
        with patch.object(
            db,
            "_generate_embedding",
            side_effect=ValueError("OPENAI_API_KEY is required for OpenAI embeddings."),
        ):
            documents = [
                {
                    "url": "http://test1.com",
                    "text": "test content 1",
                    "metadata": {"type": "webpage"},
                }
            ]

            # Ensure no OpenAI API key is set
            with patch.dict(os.environ, {}, clear=True):
                with pytest.raises(
                    ValueError,
                    match="OPENAI_API_KEY is required for OpenAI embeddings.",
                ):
                    db.write_documents(documents, embedding="text-embedding-ada-002")

    @patch("pymilvus.MilvusClient")
    def test_write_documents_real_openai_integration(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """Test writing documents with real OpenAI integration when available."""
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()

        # Only run this test if openai module is available
        import importlib.util

        if importlib.util.find_spec("openai") is None:
            pytest.skip("openai module not available")

        # Mock the OpenAI client to return a test embedding
        with patch("openai.OpenAI") as mock_openai:
            mock_client_instance = MagicMock()
            mock_openai.return_value = mock_client_instance
            mock_client_instance.embeddings.create.return_value.data = [
                MagicMock(embedding=[0.1] * 1536)
            ]

            documents = [
                {
                    "url": "http://test1.com",
                    "text": "test content 1",
                    "metadata": {"type": "webpage"},
                }
            ]

            # Set environment variable for OpenAI API key
            with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
                db.write_documents(documents, embedding="text-embedding-ada-002")
                assert mock_client.insert.called
                # Verify that the OpenAI client was called correctly
                mock_openai.assert_called_once_with(api_key="test-key")
                mock_client_instance.embeddings.create.assert_called_once_with(
                    model="text-embedding-ada-002", input="test content 1"
                )

    @patch("pymilvus.MilvusClient")
    def test_list_documents(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        # Milvus query returns a list of dictionaries directly
        mock_client.query.return_value = [
            {
                "id": 1,
                "url": "http://test1.com",
                "text": "content1",
                "metadata": """{"type": "webpage"}""",
            },
            {
                "id": 2,
                "url": "http://test2.com",
                "text": "content2",
                "metadata": """{"type": "webpage"}""",
            },
        ]
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        docs = db.list_documents(limit=2)
        assert len(docs) == 2
        assert docs[0]["id"] == 1
        assert docs[0]["url"] == "http://test1.com"

    @patch("pymilvus.MilvusClient")
    def test_count_documents(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.get_collection_stats.return_value = {"row_count": 5}
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        count = db.count_documents()
        assert count == 5

    @patch("pymilvus.MilvusClient")
    def test_list_collections(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.list_collections.return_value = [
            "Collection1",
            "Collection2",
            "MaestroDocs",
        ]
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        collections = db.list_collections()
        assert collections == ["Collection1", "Collection2", "MaestroDocs"]
        mock_client.list_collections.assert_called_once()

    @patch("pymilvus.MilvusClient")
    def test_list_collections_exception(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.list_collections.side_effect = Exception("Connection error")
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        # Suppress the expected warning for this test
        with pytest.warns(UserWarning, match="Could not list collections from Milvus"):
            collections = db.list_collections()
        assert collections == []

    @patch("pymilvus.MilvusClient")
    def test_list_collections_no_client(self, mock_milvus_client: MagicMock) -> None:
        mock_milvus_client.return_value = None
        db = MilvusVectorDatabase()
        # Suppress the expected warning for this test
        with pytest.warns(UserWarning, match="Milvus client is not available"):
            collections = db.list_collections()
        assert collections == []

    @patch("pymilvus.MilvusClient")
    def test_delete_documents(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        db.delete_documents(["1", "2", "3"])
        mock_client.delete.assert_called_once_with(db.collection_name, ids=[1, 2, 3])

    @patch("pymilvus.MilvusClient")
    def test_delete_documents_invalid_ids(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        with pytest.raises(
            ValueError, match="Milvus document IDs must be convertible to integers"
        ):
            db.delete_documents(["1", "invalid", "3"])

    @patch("pymilvus.MilvusClient")
    def test_delete_collection(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase("TestCollection")
        db.delete_collection()
        mock_client.drop_collection.assert_called_once_with("TestCollection")
        assert db.collection_name is None

    @patch("pymilvus.MilvusClient")
    def test_cleanup(self, mock_milvus_client: MagicMock) -> None:
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        db.cleanup()
        assert db.client is None

    def test_db_type_property(self) -> None:
        """Test the db_type property."""
        db = MilvusVectorDatabase()
        assert db.db_type == "milvus"

    def test_reassemble_document_no_chunks(self) -> None:
        """reassemble_document should return None when given no chunks."""
        db = MilvusVectorDatabase()
        assert db.reassemble_document([]) is None

    @patch("pymilvus.MilvusClient")
    def test_get_collection_info_includes_chunking(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """get_collection_info should include the chunking config after setup."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_client.get_collection_stats.return_value = {"row_count": 7}
        # describe_collection returns an object with attributes used by code
        mock_desc = MagicMock()
        mock_desc.fields = []
        mock_desc.description = "Test collection"
        mock_client.describe_collection.return_value = mock_desc
        mock_milvus_client.return_value = mock_client

        db = MilvusVectorDatabase()
        chunk_cfg = {
            "strategy": "Fixed",
            "parameters": {"chunk_size": 512, "overlap": 0},
        }
        db.setup(
            embedding="text-embedding-3-small",
            collection_name="InfoCol",
            chunking_config=chunk_cfg,
        )

        info = db.get_collection_info("InfoCol")
        assert info["name"] == "InfoCol"
        assert info["db_type"] == "milvus"
        assert info["document_count"] == 7
        # chunking should reflect what we set in setup
        assert info.get("chunking") == chunk_cfg
        # embedding should be whatever we set in setup
        assert info.get("embedding") == "text-embedding-3-small"

    @patch("pymilvus.MilvusClient")
    def test_get_collection_info_nonexistent_still_returns_chunking_meta(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """If collection does not exist, info should still surface stored chunking metadata."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_milvus_client.return_value = mock_client

        db = MilvusVectorDatabase()
        chunk_cfg = {"strategy": "Sentence", "parameters": {"max_chars": 500}}
        # Store metadata via setup
        db.setup(
            embedding="default", collection_name="NoSuchCol", chunking_config=chunk_cfg
        )

        info = db.get_collection_info("NoSuchCol")
        assert info["name"] == "NoSuchCol"
        assert info["db_type"] == "milvus"
        assert info["document_count"] == 0
        assert info.get("chunking") == chunk_cfg
        assert info.get("metadata", {}).get("error") == "Collection does not exist"

    @patch("pymilvus.MilvusClient")
    def test_get_document_success(self, mock_milvus_client: MagicMock) -> None:
        """Test successfully getting a document by name."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_client.query.return_value = [
            {
                "id": "chunk1",
                "url": "test_url",
                "text": "Hello ",
                "metadata": """{"doc_name": "test_doc", "collection_name": "test_collection", "chunk_sequence_number": 1, "total_chunks": 2, "offset_start": 0, "offset_end": 6, "chunk_size": 6}""",
            },
            {
                "id": "chunk2",
                "url": "test_url",
                "text": "World",
                "metadata": """{"doc_name": "test_doc", "collection_name": "test_collection", "chunk_sequence_number": 2, "total_chunks": 2, "offset_start": 6, "offset_end": 11, "chunk_size": 5}""",
            },
        ]
        mock_milvus_client.return_value = mock_client

        db = MilvusVectorDatabase()
        result = db.get_document("test_doc", "test_collection")

        assert result["id"] in ("chunk1", "chunk2")
        assert result["url"] == "test_url"
        assert result["text"] == "Hello World"
        assert result["metadata"]["doc_name"] == "test_doc"
        assert result["metadata"]["collection_name"] == "test_collection"

        # Verify the query was called with correct parameters
        mock_client.query.assert_called_once_with(
            "test_collection",
            filter='''metadata["doc_name"] == "test_doc"''',
            output_fields=["id", "url", "text", "metadata"],
            limit=10000,
        )

    @patch("pymilvus.MilvusClient")
    def test_write_documents_ignores_per_write_embedding_with_warning(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """When collection embedding is set, per-write embedding should be ignored and warn."""
        mock_client = MagicMock()
        mock_milvus_client.return_value = mock_client
        mock_client.has_collection.return_value = True

        db = MilvusVectorDatabase()
        # Simulate prior setup setting embedding model and dimension
        db.embedding_model = "text-embedding-3-small"
        db.dimension = 1536

        # Patch embedding generator to check which model is used
        with patch.object(db, "_generate_embedding", return_value=[0.0] * 1536) as gen:
            docs = [{"url": "u", "text": "abc", "metadata": {}}]
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                db.write_documents(docs, embedding="text-embedding-ada-002")
                # one warning emitted
                assert any("per-collection" in str(x.message) for x in w)
            # Should have used effective (collection) model, not the per-write arg
            gen.assert_called()

    @patch("pymilvus.MilvusClient")
    def test_get_document_collection_not_found(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """Test getting a document when collection doesn't exist."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = False
        mock_milvus_client.return_value = mock_client

        db = MilvusVectorDatabase()

        with pytest.raises(ValueError, match="Collection 'test_collection' not found"):
            db.get_document("test_doc", "test_collection")

    @patch("pymilvus.MilvusClient")
    def test_get_document_document_not_found(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """Test getting a document when document doesn't exist."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_client.query.return_value = []  # No documents found
        mock_milvus_client.return_value = mock_client

        db = MilvusVectorDatabase()

        with pytest.raises(
            ValueError,
            match="Document 'test_doc' not found in collection 'test_collection'",
        ):
            db.get_document("test_doc", "test_collection")

    @patch("pymilvus.MilvusClient")
    @pytest.mark.filterwarnings("ignore:Failed to connect to Milvus")
    def test_get_document_no_client(self, mock_milvus_client: MagicMock) -> None:
        """Test getting a document when client is not available."""
        mock_milvus_client.side_effect = Exception("Connection failed")

        db = MilvusVectorDatabase()

        with pytest.raises(ValueError, match="Milvus client is not available"):
            db.get_document("test_doc", "test_collection")

    @patch("pymilvus.MilvusClient")
    def test_get_document_invalid_metadata(self, mock_milvus_client: MagicMock) -> None:
        """Test getting a document with invalid metadata JSON."""
        mock_client = MagicMock()
        mock_client.has_collection.return_value = True
        mock_client.query.return_value = [
            {
                "id": "doc123",
                "url": "test_url",
                "text": "test content",
                "metadata": "invalid json",
            }
        ]
        mock_milvus_client.return_value = mock_client

        db = MilvusVectorDatabase()
        result = db.get_document("test_doc", "test_collection")

        # Should handle invalid JSON gracefully
        assert result["id"] == "doc123"
        assert result["url"] == "test_url"
        assert result["text"] == "test content"
        assert result["metadata"] == {}  # Should be empty dict for invalid JSON

    def test_custom_local_embedding_missing_url(self) -> None:
        db = MilvusVectorDatabase()
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="CUSTOM_EMBEDDING_URL must be set"):
                db._generate_embedding("test", "custom_local")

    def test_custom_local_embedding_missing_model(self) -> None:
        db = MilvusVectorDatabase()
        with patch.dict(
            os.environ, {"CUSTOM_EMBEDDING_URL": "http://localhost:8080"}, clear=True
        ):
            with pytest.raises(ValueError, match="CUSTOM_EMBEDDING_MODEL must be set"):
                db._generate_embedding("test", "custom_local")

    def test_custom_local_embedding_missing_vectorsize(self) -> None:
        db = MilvusVectorDatabase()
        with patch.dict(
            os.environ,
            {
                "CUSTOM_EMBEDDING_URL": "http://localhost:8080",
                "CUSTOM_EMBEDDING_MODEL": "test-model",
            },
            clear=True,
        ):
            with pytest.raises(
                ValueError, match="CUSTOM_EMBEDDING_VECTORSIZE must be set"
            ):
                db._get_embedding_dimension("custom_local")

    def test_custom_local_embedding_invalid_vectorsize(self) -> None:
        db = MilvusVectorDatabase()
        with patch.dict(
            os.environ,
            {
                "CUSTOM_EMBEDDING_URL": "http://localhost:8080",
                "CUSTOM_EMBEDDING_MODEL": "test-model",
                "CUSTOM_EMBEDDING_VECTORSIZE": "invalid",
            },
            clear=True,
        ):
            with pytest.raises(
                ValueError, match="CUSTOM_EMBEDDING_VECTORSIZE must be a valid integer"
            ):
                db._get_embedding_dimension("custom_local")

    @patch("pymilvus.MilvusClient")
    def test_write_documents_raises_milvus_exception(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """Test that write_documents raises a MilvusException on client error."""
        mock_client = MagicMock()
        mock_client.insert.side_effect = MilvusException("Insert failed")
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        db.client = mock_client  # Directly set the client for the test
        documents = [
            {
                "url": "http://test.com",
                "text": "test content",
                "metadata": {},
                "vector": [0.1] * 1536,
            }
        ]
        with pytest.raises(MilvusException, match="Insert failed"):
            db.write_documents(documents)

    @patch("pymilvus.MilvusClient")
    def test_delete_documents_raises_milvus_exception(
        self, mock_milvus_client: MagicMock
    ) -> None:
        """Test that delete_documents raises a MilvusException on client error."""
        mock_client = MagicMock()
        mock_client.delete.side_effect = MilvusException("Delete failed")
        mock_milvus_client.return_value = mock_client
        db = MilvusVectorDatabase()
        db.client = mock_client  # Directly set the client for the test
        with pytest.raises(MilvusException, match="Delete failed"):
            db.delete_documents(["1"])

    def test_parse_custom_headers(self) -> None:
        """Test the _parse_custom_headers method with various formats."""
        db = MilvusVectorDatabase()

        # Test case 1: No environment variable set
        with patch.dict(os.environ, {}, clear=True):
            assert db._parse_custom_headers() == {}

        # Test case 2: Simple key-value string
        with patch.dict(os.environ, {"CUSTOM_EMBEDDING_HEADERS": "KEY=VALUE"}):
            assert db._parse_custom_headers() == {"KEY": "VALUE"}

        # Test case 3: Multiple key-value pairs
        with patch.dict(
            os.environ, {"CUSTOM_EMBEDDING_HEADERS": "KEY1=VALUE1,KEY2=VALUE2"}
        ):
            assert db._parse_custom_headers() == {"KEY1": "VALUE1", "KEY2": "VALUE2"}

        # Test case 4: Key-value with equals sign in value
        with patch.dict(
            os.environ, {"CUSTOM_EMBEDDING_HEADERS": "KEY=VALUE_WITH_EQUALS="}
        ):
            assert db._parse_custom_headers() == {"KEY": "VALUE_WITH_EQUALS="}

        # Test case 5: Simple JSON string
        with patch.dict(os.environ, {"CUSTOM_EMBEDDING_HEADERS": '{"KEY": "VALUE"}'}):
            assert db._parse_custom_headers() == {"KEY": "VALUE"}

        # Test case 6: JSON string with multiple values
        with patch.dict(
            os.environ,
            {"CUSTOM_EMBEDDING_HEADERS": '{"KEY1": "VALUE1", "KEY2": "VALUE2"}'},
        ):
            assert db._parse_custom_headers() == {"KEY1": "VALUE1", "KEY2": "VALUE2"}

        # Test case 7: Key-value string with surrounding quotes to be stripped
        with patch.dict(os.environ, {"CUSTOM_EMBEDDING_HEADERS": '"KEY=VALUE"'}):
            assert db._parse_custom_headers() == {"KEY": "VALUE"}
        with patch.dict(os.environ, {"CUSTOM_EMBEDDING_HEADERS": "'KEY=VALUE'"}):
            assert db._parse_custom_headers() == {"KEY": "VALUE"}

        # Test case 8: Key-value with spaces
        with patch.dict(os.environ, {"CUSTOM_EMBEDDING_HEADERS": "  KEY = VALUE  "}):
            assert db._parse_custom_headers() == {"KEY": "VALUE"}

        # Test case 9: JSON that is not a dictionary (should be ignored)
        with patch.dict(os.environ, {"CUSTOM_EMBEDDING_HEADERS": '"just a string"'}):
            # This is valid JSON (a string), but not a dict, so our parser should fall back
            # to key-value parsing, which will fail and return an empty dict.
            assert db._parse_custom_headers() == {}


if __name__ == "__main__":
    pytest.main()
