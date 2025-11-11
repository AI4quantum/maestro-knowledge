"""Tests for semantic chunking strategy."""

import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest

from src.chunking import ChunkingConfig, chunk_text


@pytest.mark.unit
def test_semantic_chunk_basic() -> None:
    """Test basic semantic chunking functionality."""
    text = "This is the first sentence. This is the second sentence. This is the third sentence."
    cfg = ChunkingConfig(strategy="Semantic", parameters={"chunk_size": 100})

    result = chunk_text(text, cfg)

    assert len(result) > 0
    assert all("text" in chunk for chunk in result)
    assert all("offset_start" in chunk for chunk in result)
    assert all("offset_end" in chunk for chunk in result)
    assert all("chunk_size" in chunk for chunk in result)
    assert all("sequence" in chunk for chunk in result)
    assert all("total" in chunk for chunk in result)
    assert all("semantic_info" in chunk for chunk in result)


@pytest.mark.unit
def test_semantic_chunk_empty_text() -> None:
    """Test semantic chunking with empty text."""
    cfg = ChunkingConfig(strategy="Semantic")

    result = chunk_text("", cfg)
    assert result == []

    result = chunk_text("   ", cfg)
    assert result == []


@pytest.mark.unit
def test_semantic_chunk_single_sentence() -> None:
    """Test semantic chunking with single sentence."""
    text = "This is a single sentence."
    cfg = ChunkingConfig(strategy="Semantic")

    result = chunk_text(text, cfg)

    assert len(result) == 1
    assert result[0]["text"] == text
    assert result[0]["semantic_info"]["split_reason"] == "single_sentence"


@pytest.mark.unit
def test_semantic_chunk_with_code_blocks() -> None:
    """Test semantic chunking preserves code blocks."""
    text = "Here is some text. ```print('hello world')``` Here is more text."
    cfg = ChunkingConfig(strategy="Semantic", parameters={"chunk_size": 50})

    result = chunk_text(text, cfg)

    # Should preserve code blocks
    code_block_present = any(
        "```print('hello world')```" in chunk["text"] for chunk in result
    )
    assert code_block_present


@pytest.mark.unit
def test_semantic_chunk_parameters() -> None:
    """Test semantic chunking with various parameters."""
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    cfg = ChunkingConfig(
        strategy="Semantic",
        parameters={
            "chunk_size": 30,
            "overlap": 5,
            "window_size": 2,
            "threshold_percentile": 90.0,
            "model_name": "all-MiniLM-L6-v2",
        },
    )

    result = chunk_text(text, cfg)

    assert len(result) > 0
    # Check that chunk_size limit is respected
    assert all(chunk["chunk_size"] <= 30 for chunk in result)


@pytest.mark.unit
def test_semantic_chunk_invalid_parameters() -> None:
    """Test semantic chunking with invalid parameters."""
    text = "Some text here."

    # Invalid chunk_size
    with pytest.raises(ValueError, match="chunk_size must be > 0"):
        cfg = ChunkingConfig(strategy="Semantic", parameters={"chunk_size": 0})
        chunk_text(text, cfg)

    # Invalid overlap
    with pytest.raises(ValueError, match="overlap must be >= 0"):
        cfg = ChunkingConfig(strategy="Semantic", parameters={"overlap": -1})
        chunk_text(text, cfg)

    # Invalid threshold_percentile
    with pytest.raises(
        ValueError, match="threshold_percentile must be between 0 and 100"
    ):
        cfg = ChunkingConfig(
            strategy="Semantic", parameters={"threshold_percentile": 150}
        )
        chunk_text(text, cfg)


@pytest.mark.unit
def test_semantic_chunk_large_text() -> None:
    """Test semantic chunking with larger text."""
    # Create a longer text with multiple sentences
    sentences = [f"This is sentence number {i}." for i in range(20)]
    text = " ".join(sentences)

    cfg = ChunkingConfig(strategy="Semantic", parameters={"chunk_size": 100})

    result = chunk_text(text, cfg)

    assert len(result) > 1  # Should create multiple chunks
    assert all(chunk["chunk_size"] <= 100 for chunk in result)


@pytest.mark.unit
def test_semantic_chunk_sequence_and_total() -> None:
    """Test that sequence and total are properly set."""
    text = "First. Second. Third. Fourth. Fifth."
    cfg = ChunkingConfig(strategy="Semantic")

    result = chunk_text(text, cfg)

    # Check sequence numbers
    sequences = [chunk["sequence"] for chunk in result]
    assert sequences == list(range(len(result)))

    # Check total count
    total = result[0]["total"]
    assert all(chunk["total"] == total for chunk in result)
    assert total == len(result)


@pytest.mark.unit
def test_semantic_chunk_semantic_info() -> None:
    """Test that semantic_info contains expected fields."""
    text = "First sentence. Second sentence."
    cfg = ChunkingConfig(strategy="Semantic")

    result = chunk_text(text, cfg)

    for chunk in result:
        semantic_info = chunk["semantic_info"]
        assert "strategy" in semantic_info
        assert "sentences_in_chunk" in semantic_info
        assert "split_reason" in semantic_info

        assert semantic_info["strategy"] == "Semantic"
        assert semantic_info["sentences_in_chunk"] > 0
        assert semantic_info["split_reason"] in [
            "semantic_boundary",
            "final_chunk",
            "single_sentence",
            "size_limit_enforced",
        ]


@pytest.mark.unit
def test_semantic_chunk_fallback_behavior() -> None:
    """Test that semantic chunking falls back gracefully if embeddings fail."""
    text = "First sentence. Second sentence. Third sentence."
    cfg = ChunkingConfig(
        strategy="Semantic", parameters={"model_name": "nonexistent_model"}
    )

    result = chunk_text(text, cfg)

    assert len(result) > 0
    assert all("text" in chunk for chunk in result)


@pytest.mark.unit
def test_semantic_chunk_integration() -> None:
    """Test semantic chunking integrates properly with the chunking system."""
    text = "This is a test document. It has multiple sentences. We want to chunk it semantically."

    # Test through the main chunk_text function
    cfg = ChunkingConfig(strategy="Semantic")
    result = chunk_text(text, cfg)

    assert len(result) > 0

    # Test that we can access the result properly
    first_chunk = result[0]
    assert isinstance(first_chunk["text"], str)
    assert isinstance(first_chunk["offset_start"], int)
    assert isinstance(first_chunk["offset_end"], int)
    assert isinstance(first_chunk["chunk_size"], int)
    assert isinstance(first_chunk["sequence"], int)
    assert isinstance(first_chunk["total"], int)


@pytest.mark.unit
def test_semantic_chunk_default_chunk_size() -> None:
    """Test that semantic chunking uses 768 as default chunk size."""
    # Create text that's longer than 512 but shorter than 768
    text = "This is a test sentence. " * 20
    cfg = ChunkingConfig(strategy="Semantic", parameters={})
    result = chunk_text(text, cfg)
    assert len(result) >= 1
    assert all(chunk["chunk_size"] <= 768 for chunk in result)
    cfg = ChunkingConfig(strategy="Semantic", parameters={"chunk_size": 512})
    result = chunk_text(text, cfg)
    assert all(chunk["chunk_size"] <= 512 for chunk in result)
