"""Chunking package public API.

Exports ChunkingConfig and chunk_text so previous imports like
`from src.chunking import ChunkingConfig, chunk_text` continue to work.
"""

from .common import ChunkingConfig, chunk_text
from .fixed import fixed_chunk

# Re-export strategy names for discovery if needed
from .none import none_chunk
from .sentence import sentence_chunk
from .semantic_chunking import semantic_chunk

__all__ = [
    "ChunkingConfig",
    "chunk_text",
    "none_chunk",
    "fixed_chunk",
    "sentence_chunk",
    "semantic_chunk",
]
