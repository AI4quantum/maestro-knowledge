import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest

from src.chunking import ChunkingConfig, chunk_text


@pytest.mark.unit
def test_sentence_chunk_simple() -> None:
    text = "This is one sentence. This is another! And a third?"
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 50, "overlap": 0}
    )
    res = chunk_text(text, cfg)
    assert len(res) >= 1
    # ensure sequences are ordered
    seqs = [c["sequence"] for c in res]
    assert seqs == sorted(seqs)


@pytest.mark.unit
def test_sentence_split_long_sentence() -> None:
    text = "A" * 1200
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 500, "overlap": 50}
    )
    res = chunk_text(text, cfg)
    assert len(res) >= 2
    # total should be set on each chunk
    assert all("total" in c for c in res)


@pytest.mark.unit
def test_sentence_overlap_validation() -> None:
    text = "a" * 100
    # overlap > chunk_size should raise for Sentence
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 10, "overlap": 11}
    )
    try:
        chunk_text(text, cfg)
        assert False, "Expected ValueError for overlap > chunk_size in Sentence"
    except ValueError as e:
        assert "overlap" in str(e)

    # negative overlap should raise
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 10, "overlap": -1}
    )
    try:
        chunk_text(text, cfg)
        assert False, "Expected ValueError for negative overlap in Sentence"
    except ValueError as e:
        assert "overlap" in str(e)

    # non-positive chunk size should raise
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 0, "overlap": 0}
    )
    try:
        chunk_text(text, cfg)
        assert False, "Expected ValueError for chunk_size <= 0 in Sentence"
    except ValueError as e:
        assert "chunk_size" in str(e)

    # overlap == chunk_size is allowed and should not hang
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 10, "overlap": 10}
    )
    res = chunk_text("A" * 25, cfg)
    # Should split into non-overlapping windows with step clamped to chunk_size
    starts = [c["offset_start"] for c in res]
    assert starts == [0, 10, 20]


@pytest.mark.unit
def test_sentence_empty_text_returns_no_chunks() -> None:
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 10, "overlap": 0}
    )
    res = chunk_text("", cfg)
    assert res == []


@pytest.mark.unit
def test_sentence_packs_sentences_and_is_contiguous() -> None:
    text = "A. B. C. D. E. F."
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 5, "overlap": 0}
    )
    res = chunk_text(text, cfg)
    # No chunk exceeds chunk_size
    assert all(len(c["text"]) <= 5 for c in res)
    # Chunks are contiguous by offsets (no gaps or overlaps beyond expected boundaries)
    for i in range(1, len(res)):
        assert res[i - 1]["offset_end"] == res[i]["offset_start"]


@pytest.mark.unit
def test_sentence_split_long_sentence_with_overlap_windows() -> None:
    # One long sentence should be split with the requested overlap
    text = "X" * 30
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 10, "overlap": 5}
    )
    res = chunk_text(text, cfg)
    starts = [c["offset_start"] for c in res]
    assert starts == [0, 5, 10, 15, 20]
    ends = [c["offset_end"] for c in res]
    assert ends == [10, 15, 20, 25, 30]
    # Validate sequence and total
    assert [c["sequence"] for c in res] == list(range(len(res)))
    assert all(c["total"] == len(res) for c in res)


@pytest.mark.unit
def test_sentence_mixed_punctuation_and_newlines() -> None:
    text = (
        "One line.\nSecond line!\nThird line? Fourth line without punctuation\nFifth."
    )
    # Choose a chunk size that packs a couple sentences but not all
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 30, "overlap": 0}
    )
    res = chunk_text(text, cfg)
    assert len(res) >= 2
    # Chunks are contiguous by offsets
    for i in range(1, len(res)):
        assert res[i - 1]["offset_end"] == res[i]["offset_start"]
    # Prefer sentence boundaries: at least half of the non-final chunks end at punctuation/newline
    non_final = max(0, len(res) - 1)
    boundary_count = sum(
        1 for i in range(len(res) - 1) if res[i]["text"].endswith((".", "!", "?", "\n"))
    )
    assert boundary_count >= (non_final // 2)


@pytest.mark.unit
def test_sentence_exact_fit_boundary() -> None:
    # Two sentences exactly fill chunk_size — they should be packed together
    text = "abcd.efg."
    assert len(text) == 9
    cfg = ChunkingConfig(
        strategy="Sentence", parameters={"chunk_size": 9, "overlap": 0}
    )
    res = chunk_text(text, cfg)
    assert len(res) == 1
    assert res[0]["text"] == text
    assert res[0]["offset_start"] == 0
    assert res[0]["offset_end"] == len(text)
