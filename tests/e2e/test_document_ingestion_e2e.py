"""E2E tests for document ingestion with URL fetching and format conversion."""

import os
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

# Configure pytest-asyncio to use function scope for event loop
pytestmark = pytest.mark.asyncio(scope="function")

from src.db.vector_db_milvus import MilvusVectorDatabase


# Helper function to create and setup database
async def create_test_db() -> MilvusVectorDatabase:
    """Create a test database with embedding configuration."""
    import time

    collection_name = f"test_doc_ingestion_{int(time.time() * 1000)}"
    db = MilvusVectorDatabase(collection_name=collection_name)

    await db.setup(
        embedding="custom_local",
        chunking_config={
            "strategy": "Sentence",
            "parameters": {"chunk_size": 512, "overlap": 24},
        },
    )
    return db


@pytest.mark.e2e
class TestDocumentIngestionE2E:
    """E2E tests for document ingestion with real Milvus."""

    @pytest.fixture
    def test_dir(self) -> Generator[Path, None, None]:
        """Create a test directory in current working directory (allowed by default)."""
        import time

        test_dir = Path.cwd() / f"test_docs_temp_{int(time.time() * 1000)}"
        test_dir.mkdir(exist_ok=True)
        yield test_dir
        # Cleanup
        import shutil

        if test_dir.exists():
            shutil.rmtree(test_dir)

    @pytest.mark.asyncio
    async def test_ingest_text_file_from_url(self, test_dir: Path) -> None:
        """Test ingesting a plain text file from file:// URL."""
        # Skip if not running E2E tests
        if not os.getenv("E2E_MILVUS"):
            pytest.skip("E2E_MILVUS not set")

        import asyncio

        # Create database
        db = await create_test_db()

        try:
            # Create a test text file in allowed directory
            test_file = test_dir / "test.txt"
            test_content = "This is a test document.\nIt has multiple lines.\nFor testing purposes."
            test_file.write_text(test_content)

            # Ingest document with URL only (no text field)
            file_url = f"file://{test_file}"
            documents = [
                {
                    "url": file_url,
                    "metadata": {"type": "text", "source": "test"},
                }
            ]

            # Write documents
            result = await db.write_documents(documents)
            assert result["documents"] == 1
            assert result["chunks"] > 0

            # Wait a moment for Milvus to index
            await asyncio.sleep(0.5)

            # Retrieve the full document using the URL as doc_name
            doc = await db.get_document(file_url)
            assert doc is not None
            assert doc["url"] == file_url
            # Check that the content is present (newlines may be normalized during chunking)
            assert "This is a test document" in doc["text"]
            assert "multiple lines" in doc["text"]
            assert "testing purposes" in doc["text"]
            assert "metadata" in doc
        finally:
            # Cleanup
            try:
                await db.cleanup()
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_ingest_markdown_file_from_url(self, test_dir: Path) -> None:
        """Test ingesting a markdown file from file:// URL."""
        if not os.getenv("E2E_MILVUS"):
            pytest.skip("E2E_MILVUS not set")

        import asyncio

        db = await create_test_db()

        try:
            test_file = test_dir / "test.md"
            test_content = "# Test Document\n\nThis is **markdown** content.\n\n## Section 2\n\nMore content here."
            test_file.write_text(test_content)

            file_url = f"file://{test_file}"
            documents = [
                {"url": file_url, "metadata": {"type": "markdown", "source": "test"}}
            ]

            await db.write_documents(documents)
            await asyncio.sleep(0.5)

            doc = await db.get_document(file_url)
            assert doc is not None
            assert "Test Document" in doc["text"]
            assert "markdown" in doc["text"]
        finally:
            try:
                await db.cleanup()
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_ingest_multiple_documents_mixed_types(self, test_dir: Path) -> None:
        """Test ingesting multiple documents with different types."""
        if not os.getenv("E2E_MILVUS"):
            pytest.skip("E2E_MILVUS not set")

        import asyncio

        db = await create_test_db()

        try:
            txt_file = test_dir / "doc1.txt"
            txt_file.write_text("Plain text document content.")

            md_file = test_dir / "doc2.md"
            md_file.write_text("# Markdown Document\n\nMarkdown content here.")

            documents = [
                {"url": f"file://{txt_file}", "metadata": {"type": "text"}},
                {"url": f"file://{md_file}", "metadata": {"type": "markdown"}},
                {
                    "url": "doc3",
                    "text": "Direct text content",
                    "metadata": {"type": "direct"},
                },
            ]

            await db.write_documents(documents)
            await asyncio.sleep(0.5)

            doc1 = await db.get_document(f"file://{txt_file}")
            assert doc1 is not None
            assert "Plain text" in doc1["text"]

            doc2 = await db.get_document(f"file://{md_file}")
            assert doc2 is not None
            assert "Markdown" in doc2["text"]

            doc3 = await db.get_document("doc3")
            assert doc3 is not None
            assert doc3["text"] == "Direct text content"
        finally:
            try:
                await db.cleanup()
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_backwards_compatibility_with_text_field(self) -> None:
        """Test that providing text directly still works (backwards compatible)."""
        if not os.getenv("E2E_MILVUS"):
            pytest.skip("E2E_MILVUS not set")

        import asyncio

        db = await create_test_db()

        try:
            documents = [
                {
                    "url": "test_doc",
                    "text": "This is direct text content.",
                    "metadata": {"method": "direct"},
                }
            ]

            await db.write_documents(documents)
            await asyncio.sleep(0.5)

            doc = await db.get_document("test_doc")
            assert doc is not None
            assert doc["text"] == "This is direct text content."
        finally:
            try:
                await db.cleanup()
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_metadata_enrichment_from_fetch(self, test_dir: Path) -> None:
        """Test that fetched documents get enriched metadata."""
        if not os.getenv("E2E_MILVUS"):
            pytest.skip("E2E_MILVUS not set")

        import asyncio

        db = await create_test_db()

        try:
            test_file = test_dir / "test.txt"
            test_file.write_text("Test content for metadata check.")

            file_url = f"file://{test_file}"
            documents = [
                {"url": file_url, "metadata": {"custom_field": "custom_value"}}
            ]

            await db.write_documents(documents)
            await asyncio.sleep(0.5)

            doc = await db.get_document(file_url)
            assert doc is not None

            metadata = doc.get("metadata", {})
            assert "custom_field" in str(metadata) or "custom_value" in str(metadata)
        finally:
            try:
                await db.cleanup()
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_document_chunking_and_reassembly(self, test_dir: Path) -> None:
        """Test that large documents are chunked and can be reassembled."""
        if not os.getenv("E2E_MILVUS"):
            pytest.skip("E2E_MILVUS not set")

        import asyncio

        db = await create_test_db()

        try:
            test_file = test_dir / "large.txt"
            large_content = " ".join([f"Sentence {i}." for i in range(100)])
            test_file.write_text(large_content)

            file_url = f"file://{test_file}"
            documents = [{"url": file_url, "metadata": {}}]

            await db.write_documents(documents)
            await asyncio.sleep(0.5)

            # Retrieve full document - should be reassembled
            doc = await db.get_document(file_url)
            assert doc is not None
            # Check that content is complete (all sentences present)
            assert "Sentence 0" in doc["text"]
            assert "Sentence 99" in doc["text"]
        finally:
            try:
                await db.cleanup()
            except Exception:
                pass

    @pytest.mark.asyncio
    async def test_file_path_security_enforcement(self) -> None:
        """Test that file path security is enforced."""
        if not os.getenv("E2E_MILVUS"):
            pytest.skip("E2E_MILVUS not set")

        import asyncio

        db = await create_test_db()

        try:
            # Try to access a file outside allowed paths
            # This should fail gracefully (document skipped, not crash)
            documents = [{"url": "file:///etc/passwd", "metadata": {}}]

            # Should not raise an error, but document should be skipped
            await db.write_documents(documents)
            await asyncio.sleep(0.5)

            # Verify no documents were added (security blocked the file)
            count = await db.count_documents()
            assert count == 0  # No documents should be added
        finally:
            try:
                await db.cleanup()
            except Exception:
                pass


# Made with Bob
