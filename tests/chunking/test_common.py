import os
import sys

# Ensure the project root is on sys.path so tests can import `src.*`
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

import pytest

from src.chunking import ChunkingConfig, chunk_text


@pytest.mark.unit
def test_unknown_strategy_raises_value_error() -> None:
    cfg = ChunkingConfig(strategy="Bogus", parameters={})
    try:
        chunk_text("hi", cfg)
        assert False, "Expected ValueError for unknown strategy"
    except ValueError as e:
        assert "Unknown chunking strategy" in str(e)
