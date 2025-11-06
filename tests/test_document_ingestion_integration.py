"""Integration tests for document ingestion with URL fetching."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.vector_db_milvus import MilvusVectorDatabase


@pytest.mark.integration
class TestDocumentIngestionIntegration:
    """Test document ingestion with automatic URL fetching and conversion."""

    @pytest.mark.asyncio
    @patch("pymilvus.AsyncMilvusClient")
    async def test_write_document_with_url_only(
        self, mock_milvus_client: AsyncMock
    ) -> None:
        """Test writing a document with only URL (no text field)."""
        # Setup mock
        mock_client_instance = AsyncMock()
        mock_milvus_client.return_value = mock_client_instance
        mock_client_instance.has_collection.return_value = True
        mock_client_instance.insert.return_value = MagicMock(insert_count=1)

        # Create temp file with content
        with tempfile.TemporaryDirectory() as tmpdir:
            # Allow temp directory for testing
            os.environ["MAESTRO_ALLOWED_FILE_PATHS"] = tmpdir

            test_file = Path(tmpdir) / "test.txt"
            test_content = "This is test content from a file."
            test_file.write_text(test_content)

            # Create database with allowed path
            db = MilvusVectorDatabase(collection_name="test_collection")
            db.client = mock_client_instance

            # Write document with URL only (no text field)
            documents = [{"url": f"file://{test_file}", "metadata": {"source": "test"}}]

            # Mock embedding function
            with patch.object(
                db, "_generate_embedding_async", return_value=[0.1] * 768
            ):
                await db.write_documents(documents, embedding="custom_local")

            # Verify insert was called
            assert mock_client_instance.insert.called
            call_args = mock_client_instance.insert.call_args

            # Verify the document was processed and has text
            # insert is called as: insert(collection_name, data)
            inserted_data = call_args[0][1]  # Second positional argument
            assert len(inserted_data) > 0
            assert "text" in inserted_data[0]
            assert test_content in inserted_data[0]["text"]

    @pytest.mark.asyncio
    @patch("pymilvus.AsyncMilvusClient")
    async def test_write_document_backwards_compatible(
        self, mock_milvus_client: AsyncMock
    ) -> None:
        """Test that providing text directly still works (backwards compatible)."""
        # Setup mock
        mock_client_instance = AsyncMock()
        mock_milvus_client.return_value = mock_client_instance
        mock_client_instance.has_collection.return_value = True
        mock_client_instance.insert.return_value = MagicMock(insert_count=1)

        db = MilvusVectorDatabase(collection_name="test_collection")
        db.client = mock_client_instance

        # Write document with text field (old way)
        test_text = "Direct text content"
        documents = [{"url": "doc1", "text": test_text, "metadata": {}}]

        # Mock embedding function
        with patch.object(db, "_generate_embedding_async", return_value=[0.1] * 768):
            await db.write_documents(documents, embedding="custom_local")

        # Verify insert was called
        assert mock_client_instance.insert.called
        call_args = mock_client_instance.insert.call_args

        # Verify the text was used directly
        # insert is called as: insert(collection_name, data)
        inserted_data = call_args[0][1]  # Second positional argument
        assert len(inserted_data) > 0
        assert inserted_data[0]["text"] == test_text

    @pytest.mark.asyncio
    @patch("pymilvus.AsyncMilvusClient")
    async def test_write_document_with_metadata_enrichment(
        self, mock_milvus_client: AsyncMock
    ) -> None:
        """Test that fetched documents get enriched metadata."""
        # Setup mock
        mock_client_instance = AsyncMock()
        mock_milvus_client.return_value = mock_client_instance
        mock_client_instance.has_collection.return_value = True
        mock_client_instance.insert.return_value = MagicMock(insert_count=1)

        # Create temp file
        with tempfile.TemporaryDirectory() as tmpdir:
            # Allow temp directory for testing
            os.environ["MAESTRO_ALLOWED_FILE_PATHS"] = tmpdir

            test_file = Path(tmpdir) / "test.md"
            test_file.write_text("# Test Markdown\n\nContent here.")

            db = MilvusVectorDatabase(collection_name="test_collection")
            db.client = mock_client_instance

            # Write document with URL only
            documents = [
                {"url": f"file://{test_file}", "metadata": {"custom": "value"}}
            ]

            # Mock embedding function
            with patch.object(
                db, "_generate_embedding_async", return_value=[0.1] * 768
            ):
                await db.write_documents(documents, embedding="custom_local")

            # Verify metadata was enriched
            call_args = mock_client_instance.insert.call_args
            # insert is called as: insert(collection_name, data)
            inserted_data = call_args[0][1]  # Second positional argument

            # Check that metadata includes both custom and fetch metadata
            metadata_str = inserted_data[0]["metadata"]
            assert "custom" in metadata_str
            assert "value" in metadata_str
            # Should have fetch metadata
            assert "fetched_at" in metadata_str or "content_length" in metadata_str

    @pytest.mark.asyncio
    @patch("pymilvus.AsyncMilvusClient")
    async def test_get_document_reassembles_chunks(
        self, mock_milvus_client: AsyncMock
    ) -> None:
        """Test that get_document reassembles chunks into full document."""
        # Setup mock
        mock_client_instance = AsyncMock()
        mock_milvus_client.return_value = mock_client_instance
        mock_client_instance.has_collection.return_value = True

        # Mock query to return chunks
        mock_chunks = [
            {
                "text": "First chunk of text. ",
                "metadata": '{"doc_name": "test_doc", "chunk_sequence_number": 1, "total_chunks": 3, "offset_start": 0, "offset_end": 21}',
                "url": "test_doc",
            },
            {
                "text": "Second chunk of text. ",
                "metadata": '{"doc_name": "test_doc", "chunk_sequence_number": 2, "total_chunks": 3, "offset_start": 21, "offset_end": 43}',
                "url": "test_doc",
            },
            {
                "text": "Third chunk of text.",
                "metadata": '{"doc_name": "test_doc", "chunk_sequence_number": 3, "total_chunks": 3, "offset_start": 43, "offset_end": 63}',
                "url": "test_doc",
            },
        ]
        mock_client_instance.query.return_value = mock_chunks

        db = MilvusVectorDatabase(collection_name="test_collection")
        db.client = mock_client_instance

        # Get document
        result = await db.get_document("test_doc")

        # Verify document was reassembled
        assert result is not None
        assert result["url"] == "test_doc"
        assert (
            result["text"]
            == "First chunk of text. Second chunk of text. Third chunk of text."
        )
        assert "metadata" in result

    @pytest.mark.asyncio
    @patch("pymilvus.AsyncMilvusClient")
    async def test_write_document_with_file_path_security(
        self, mock_milvus_client: AsyncMock
    ) -> None:
        """Test that file path security restrictions are enforced."""
        # Setup mock
        mock_client_instance = AsyncMock()
        mock_milvus_client.return_value = mock_client_instance
        mock_client_instance.has_collection.return_value = True

        db = MilvusVectorDatabase(collection_name="test_collection")
        db.client = mock_client_instance

        # Try to write document with forbidden path
        documents = [{"url": "file:///etc/passwd", "metadata": {}}]

        # Mock embedding function
        with patch.object(db, "_generate_embedding_async", return_value=[0.1] * 768):
            # Should not raise error, but should skip the document
            await db.write_documents(documents, embedding="custom_local")

        # Verify insert was NOT called (document was skipped)
        assert not mock_client_instance.insert.called

    @pytest.mark.asyncio
    @patch("pymilvus.AsyncMilvusClient")
    async def test_write_mixed_documents(self, mock_milvus_client: AsyncMock) -> None:
        """Test writing mix of URL-only and text-provided documents."""
        # Setup mock
        mock_client_instance = AsyncMock()
        mock_milvus_client.return_value = mock_client_instance
        mock_client_instance.has_collection.return_value = True
        mock_client_instance.insert.return_value = MagicMock(insert_count=2)

        # Create temp file
        with tempfile.TemporaryDirectory() as tmpdir:
            # Allow temp directory for testing
            os.environ["MAESTRO_ALLOWED_FILE_PATHS"] = tmpdir

            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("File content")

            db = MilvusVectorDatabase(collection_name="test_collection")
            db.client = mock_client_instance

            # Mix of documents
            documents = [
                {"url": f"file://{test_file}", "metadata": {}},  # URL only
                {"url": "doc2", "text": "Direct text", "metadata": {}},  # With text
            ]

            # Mock embedding function
            with patch.object(
                db, "_generate_embedding_async", return_value=[0.1] * 768
            ):
                await db.write_documents(documents, embedding="custom_local")

            # Verify both documents were processed
            assert mock_client_instance.insert.called
            call_args = mock_client_instance.insert.call_args
            # insert is called as: insert(collection_name, data)
            inserted_data = call_args[0][1]  # Second positional argument

            # Should have chunks from both documents
            assert len(inserted_data) >= 2


# Made with Bob
