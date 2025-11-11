"""Unit tests for document chunk reassembly with overlap handling."""

import pytest
from src.db.vector_db_milvus import MilvusVectorDatabase


@pytest.mark.unit
class TestReassembly:
    """Test suite for _reassemble_chunks_into_document method."""

    def test_reassembly_no_chunks(self) -> None:
        """Test that empty chunk list returns None."""
        db = MilvusVectorDatabase()
        result = db._reassemble_chunks_into_document([])
        assert result is None

    def test_reassembly_single_chunk(self) -> None:
        """Test reassembly with a single chunk."""
        db = MilvusVectorDatabase()
        chunks = [
            {
                "text": "This is a single chunk.",
                "metadata": {
                    "chunk_sequence_number": 0,
                    "total_chunks": 1,
                    "offset_start": 0,
                    "offset_end": 23,
                    "doc_name": "test.txt",
                },
                "url": "test.txt",
            }
        ]
        result = db._reassemble_chunks_into_document(chunks)

        assert result is not None
        assert result["text"] == "This is a single chunk."
        assert result["url"] == "test.txt"
        # Chunk-specific metadata should be removed
        assert "chunk_sequence_number" not in result["metadata"]
        assert "offset_start" not in result["metadata"]
        assert "offset_end" not in result["metadata"]
        # Document metadata should remain
        assert result["metadata"]["doc_name"] == "test.txt"

    def test_reassembly_no_overlap(self) -> None:
        """Test reassembly with non-overlapping chunks."""
        db = MilvusVectorDatabase()
        chunks = [
            {
                "text": "First chunk. ",
                "metadata": {
                    "chunk_sequence_number": 0,
                    "offset_start": 0,
                    "offset_end": 13,
                },
                "url": "test.txt",
            },
            {
                "text": "Second chunk. ",
                "metadata": {
                    "chunk_sequence_number": 1,
                    "offset_start": 13,
                    "offset_end": 27,
                },
                "url": "test.txt",
            },
            {
                "text": "Third chunk.",
                "metadata": {
                    "chunk_sequence_number": 2,
                    "offset_start": 27,
                    "offset_end": 39,
                },
                "url": "test.txt",
            },
        ]
        result = db._reassemble_chunks_into_document(chunks)

        assert result is not None
        assert result["text"] == "First chunk. Second chunk. Third chunk."

    def test_reassembly_with_fixed_overlap(self) -> None:
        """Test reassembly with fixed overlap (typical Fixed chunking strategy)."""
        db = MilvusVectorDatabase()
        # Simulate overlap=10: "brown fox " is repeated
        chunks = [
            {
                "text": "The quick brown fox ",
                "metadata": {
                    "chunk_sequence_number": 0,
                    "offset_start": 0,
                    "offset_end": 20,
                },
                "url": "test.txt",
            },
            {
                "text": "brown fox jumps over ",
                "metadata": {
                    "chunk_sequence_number": 1,
                    "offset_start": 10,  # Overlap starts here
                    "offset_end": 31,
                },
                "url": "test.txt",
            },
            {
                "text": "jumps over the lazy dog",
                "metadata": {
                    "chunk_sequence_number": 2,
                    "offset_start": 20,  # Overlap starts here
                    "offset_end": 43,
                },
                "url": "test.txt",
            },
        ]
        result = db._reassemble_chunks_into_document(chunks)

        assert result is not None
        # Should not have duplicated text
        assert "brown fox brown fox" not in result["text"]
        assert "jumps over jumps over" not in result["text"]
        # Should have complete text without duplication
        assert result["text"] == "The quick brown fox jumps over the lazy dog"

    def test_reassembly_with_variable_overlap(self) -> None:
        """Test reassembly with variable overlap sizes."""
        db = MilvusVectorDatabase()
        chunks = [
            {
                "text": "Section one has content. ",
                "metadata": {
                    "chunk_sequence_number": 0,
                    "offset_start": 0,
                    "offset_end": 25,
                },
                "url": "test.txt",
            },
            {
                "text": "content. Section two continues. ",
                "metadata": {
                    "chunk_sequence_number": 1,
                    "offset_start": 17,  # 8 char overlap: "content. "
                    "offset_end": 49,
                },
                "url": "test.txt",
            },
            {
                "text": "continues. Final section.",
                "metadata": {
                    "chunk_sequence_number": 2,
                    "offset_start": 39,  # 10 char overlap: "continues. "
                    "offset_end": 64,
                },
                "url": "test.txt",
            },
        ]
        result = db._reassemble_chunks_into_document(chunks)

        assert result is not None
        # Note: Extra spaces appear because chunks include trailing spaces
        assert (
            result["text"]
            == "Section one has content.  Section two continues.  Final section."
        )

    def test_reassembly_fallback_text_based(self) -> None:
        """Test text-based overlap detection when offset metadata is missing."""
        db = MilvusVectorDatabase()
        chunks = [
            {
                "text": "The quick brown fox ",
                "metadata": {
                    "chunk_sequence_number": 0,
                    # No offset_start/offset_end
                },
                "url": "test.txt",
            },
            {
                "text": "brown fox jumps over ",
                "metadata": {
                    "chunk_sequence_number": 1,
                },
                "url": "test.txt",
            },
            {
                "text": "jumps over the lazy dog",
                "metadata": {
                    "chunk_sequence_number": 2,
                },
                "url": "test.txt",
            },
        ]
        result = db._reassemble_chunks_into_document(chunks)

        assert result is not None
        # Should detect overlap via text comparison
        assert "brown fox brown fox" not in result["text"]
        assert "jumps over jumps over" not in result["text"]
        assert result["text"] == "The quick brown fox jumps over the lazy dog"

    def test_reassembly_mixed_metadata(self) -> None:
        """Test reassembly when some chunks have offsets and others don't."""
        db = MilvusVectorDatabase()
        chunks = [
            {
                "text": "First chunk. ",
                "metadata": {
                    "chunk_sequence_number": 0,
                    "offset_start": 0,
                    "offset_end": 13,
                },
                "url": "test.txt",
            },
            {
                "text": "Second chunk. ",
                "metadata": {
                    "chunk_sequence_number": 1,
                    # Missing offsets - should fall back to text-based
                },
                "url": "test.txt",
            },
            {
                "text": "Third chunk.",
                "metadata": {
                    "chunk_sequence_number": 2,
                },
                "url": "test.txt",
            },
        ]
        result = db._reassemble_chunks_into_document(chunks)

        assert result is not None
        assert result["text"] == "First chunk. Second chunk. Third chunk."

    def test_reassembly_out_of_order_chunks(self) -> None:
        """Test that chunks are sorted by sequence number before reassembly."""
        db = MilvusVectorDatabase()
        chunks = [
            {
                "text": "Third chunk.",
                "metadata": {
                    "chunk_sequence_number": 2,
                    "offset_start": 27,
                    "offset_end": 39,
                },
                "url": "test.txt",
            },
            {
                "text": "First chunk. ",
                "metadata": {
                    "chunk_sequence_number": 0,
                    "offset_start": 0,
                    "offset_end": 13,
                },
                "url": "test.txt",
            },
            {
                "text": "Second chunk. ",
                "metadata": {
                    "chunk_sequence_number": 1,
                    "offset_start": 13,
                    "offset_end": 27,
                },
                "url": "test.txt",
            },
        ]
        result = db._reassemble_chunks_into_document(chunks)

        assert result is not None
        assert result["text"] == "First chunk. Second chunk. Third chunk."

    def test_find_text_overlap_exact_match(self) -> None:
        """Test _find_text_overlap with exact overlap."""
        db = MilvusVectorDatabase()
        text1 = "The quick brown fox"
        text2 = "brown fox jumps"

        overlap = db._find_text_overlap(text1, text2)
        assert overlap == 9  # "brown fox"

    def test_find_text_overlap_no_match(self) -> None:
        """Test _find_text_overlap with no overlap."""
        db = MilvusVectorDatabase()
        text1 = "First sentence."
        text2 = "Second sentence."

        overlap = db._find_text_overlap(text1, text2)
        assert overlap == 0

    def test_find_text_overlap_small_overlap(self) -> None:
        """Test _find_text_overlap with small overlap below minimum."""
        db = MilvusVectorDatabase()
        text1 = "Hello"
        text2 = "lo world"

        # Default min_overlap is 5, so "lo" (2 chars) should not be detected
        overlap = db._find_text_overlap(text1, text2)
        assert overlap == 0

        # But with min_overlap=2, it should be detected
        overlap = db._find_text_overlap(text1, text2, min_overlap=2)
        assert overlap == 2

    def test_find_text_overlap_partial_word(self) -> None:
        """Test _find_text_overlap with partial word overlap."""
        db = MilvusVectorDatabase()
        text1 = "The quick brown fox "
        text2 = "fox jumps"

        # Should find "fox " overlap (4 chars)
        overlap = db._find_text_overlap(text1, text2)
        assert overlap == 0  # No overlap because text2 doesn't start with space

        # Test with actual overlap
        text1 = "The quick brown fox"
        text2 = "fox"
        overlap = db._find_text_overlap(text1, text2)
        assert overlap == 0  # No overlap at boundary (min_overlap=5 by default)

        # Test with longer overlap
        text1 = "The quick brown"
        text2 = "brown fox"
        overlap = db._find_text_overlap(text1, text2)
        assert overlap == 5  # "brown"

    def test_reassembly_preserves_non_chunk_metadata(self) -> None:
        """Test that non-chunk-specific metadata is preserved."""
        db = MilvusVectorDatabase()
        chunks = [
            {
                "text": "Content here.",
                "metadata": {
                    "chunk_sequence_number": 0,
                    "offset_start": 0,
                    "offset_end": 13,
                    "doc_name": "test.txt",
                    "author": "John Doe",
                    "created_at": "2024-01-01",
                },
                "url": "test.txt",
            }
        ]
        result = db._reassemble_chunks_into_document(chunks)

        assert result is not None
        # Chunk metadata removed
        assert "chunk_sequence_number" not in result["metadata"]
        assert "offset_start" not in result["metadata"]
        # Document metadata preserved
        assert result["metadata"]["doc_name"] == "test.txt"
        assert result["metadata"]["author"] == "John Doe"
        assert result["metadata"]["created_at"] == "2024-01-01"

    def test_reassembly_with_large_overlap(self) -> None:
        """Test reassembly when overlap is larger than expected."""
        db = MilvusVectorDatabase()
        chunks = [
            {
                "text": "The quick brown fox jumps",
                "metadata": {
                    "chunk_sequence_number": 0,
                    "offset_start": 0,
                    "offset_end": 25,
                },
                "url": "test.txt",
            },
            {
                "text": "fox jumps over the lazy dog",
                "metadata": {
                    "chunk_sequence_number": 1,
                    "offset_start": 16,  # Large overlap: "fox jumps"
                    "offset_end": 43,
                },
                "url": "test.txt",
            },
        ]
        result = db._reassemble_chunks_into_document(chunks)

        assert result is not None
        assert result["text"] == "The quick brown fox jumps over the lazy dog"
        assert "fox jumps fox jumps" not in result["text"]


# Made with Bob
