import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest

from src.chunking import ChunkingConfig, chunk_text


@pytest.mark.unit
def test_fixed_chunk() -> None:
    text = "a" * 1200
    cfg = ChunkingConfig(
        strategy="Fixed", parameters={"chunk_size": 500, "overlap": 100}
    )
    res = chunk_text(text, cfg)
    assert len(res) >= 2
    # ensure overlap behavior: step = 400
    assert res[0]["offset_start"] == 0
    assert res[1]["offset_start"] == 400


@pytest.mark.unit
def test_fixed_overlap_validation() -> None:
    text = "a" * 100
    # overlap == chunk_size should raise for Fixed
    cfg = ChunkingConfig(strategy="Fixed", parameters={"chunk_size": 10, "overlap": 10})
    try:
        chunk_text(text, cfg)
        assert False, "Expected ValueError for overlap == chunk_size in Fixed"
    except ValueError as e:
        assert "overlap" in str(e)

    # negative overlap should raise
    cfg = ChunkingConfig(strategy="Fixed", parameters={"chunk_size": 10, "overlap": -1})
    try:
        chunk_text(text, cfg)
        assert False, "Expected ValueError for negative overlap in Fixed"
    except ValueError as e:
        assert "overlap" in str(e)

    # non-positive chunk size should raise
    cfg = ChunkingConfig(strategy="Fixed", parameters={"chunk_size": 0, "overlap": 0})
    try:
        chunk_text(text, cfg)
        assert False, "Expected ValueError for chunk_size <= 0 in Fixed"
    except ValueError as e:
        assert "chunk_size" in str(e)


@pytest.mark.unit
def test_fixed_empty_text_returns_no_chunks() -> None:
    cfg = ChunkingConfig(strategy="Fixed", parameters={"chunk_size": 10, "overlap": 0})
    res = chunk_text("", cfg)
    assert res == []


@pytest.mark.unit
def test_fixed_defaults_apply_when_params_missing() -> None:
    # Only set strategy; expect defaults chunk_size=512, overlap=0
    text = "a" * 600
    cfg = ChunkingConfig(strategy="Fixed", parameters={})
    res = chunk_text(text, cfg)
    assert len(res) == 2
    assert res[0]["offset_start"] == 0
    assert res[1]["offset_start"] == 512


@pytest.mark.unit
def test_fixed_near_max_overlap_many_steps() -> None:
    # overlap just below chunk_size should produce many small steps (step=1)
    text = "a" * 35
    cfg = ChunkingConfig(strategy="Fixed", parameters={"chunk_size": 10, "overlap": 9})
    res = chunk_text(text, cfg)
    assert len(res) == 35
    starts = [c["offset_start"] for c in res]
    assert starts[:3] == [0, 1, 2]
    assert starts[-3:] == [32, 33, 34]
    # Ensure no empty chunks and last end at len(text)
    assert all(len(c["text"]) > 0 for c in res)
    assert res[-1]["offset_end"] == len(text)
