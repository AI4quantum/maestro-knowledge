# Chunking Configuration Guide

## Overview

This document explains how chunking works in the Maestro Knowledge system, including configuration, defaults, and overlap handling.

## How Chunking is Configured

### 1. Via API (create_collection)

Chunking is configured when creating a collection:

```python
create_collection(
    collection="mydocs",
    embedding="auto",
    chunking_config={
        "strategy": "Sentence",
        "parameters": {
            "chunk_size": 512,
            "overlap": 0
        }
    }
)
```

### 2. Default Behavior

**If no chunking_config is provided:**
- **Default strategy**: `"Sentence"` (Phase 8.5 change from "None")
- **Default chunk_size**: `512` characters
- **Default overlap**: `0` characters

From [`src/chunking/common.py:14`](../src/chunking/common.py):
```python
@dataclass
class ChunkingConfig:
    strategy: str = "Sentence"  # Default strategy
    parameters: dict[str, object] | None = None
```

From [`src/chunking/common.py:52-56`](../src/chunking/common.py):
```python
if strategy != "None":
    if strategy == "Semantic":
        params = {"chunk_size": 768, "overlap": 0}
    else:
        params = {"chunk_size": 512, "overlap": 0}
```

## Available Chunking Strategies

### 1. None
- **Description**: No chunking; entire document is a single chunk
- **Use case**: Small documents, pre-chunked content
- **Parameters**: None

### 2. Fixed
- **Description**: Fixed-size windows with optional overlap
- **Default parameters**: `chunk_size=512, overlap=0`
- **Use case**: Uniform chunk sizes, simple splitting

### 3. Sentence (Default)
- **Description**: Sentence-aware packing up to chunk_size with optional overlap
- **Default parameters**: `chunk_size=512, overlap=0`
- **Use case**: Preserving sentence boundaries, better semantic coherence
- **Behavior**: 
  - Packs whole sentences into chunks
  - Splits long sentences if they exceed chunk_size
  - Respects sentence boundaries when possible

### 4. Semantic
- **Description**: Semantic chunking using sentence embeddings and similarity
- **Default parameters**: `chunk_size=768, overlap=0, window_size=1, threshold_percentile=95.0`
- **Use case**: Maximum semantic coherence, topic-based splitting
- **Note**: More computationally expensive

## Overlap: Should It Be Default?

### Current Default: overlap=0

**Reasons for overlap=0 as default:**

1. **Simplicity**: Easier to understand and debug
2. **Storage efficiency**: No duplicate content stored
3. **Reassembly works perfectly**: Chunks concatenate cleanly without deduplication
4. **Performance**: Faster processing, fewer chunks to embed

### When to Use Overlap

**Use overlap > 0 when:**

1. **Context preservation**: Important context might be split across chunk boundaries
2. **Search quality**: Overlapping chunks can improve retrieval by providing more context
3. **Question answering**: Answers that span chunk boundaries are more likely to be found

**Recommended overlap values:**
- **Small overlap**: 50-100 characters (10-20% of chunk_size)
- **Medium overlap**: 100-200 characters (20-40% of chunk_size)
- **Large overlap**: 200+ characters (40%+ of chunk_size)

**Trade-offs:**
- ✅ Better search quality
- ✅ More context preserved
- ❌ More storage required
- ❌ More chunks to embed (slower, more expensive)
- ❌ Potential duplicate results in search

## Overlap Handling During Reassembly

### Yes, Overlap is Handled! ✅

The system correctly handles overlapping chunks during document reassembly.

From [`src/db/vector_db_base.py:474-544`](../src/db/vector_db_base.py):

```python
def _reassemble_chunks_into_document(self, chunks: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Reassemble a document from its chunks, handling overlaps.
    
    Strategy:
    1. Sort chunks by chunk_sequence_number
    2. Use offset_start/offset_end to detect overlaps (primary method)
    3. Fall back to text-based overlap detection if offsets unavailable
    4. Skip overlapping portions when concatenating chunks
    """
```

**Overlap detection methods:**

1. **Offset-based (primary)**: Uses `offset_start` and `offset_end` metadata
   ```python
   overlap_size = max(0, last_offset_end - offset_start)
   if overlap_size > 0:
       result_text += chunk_text[overlap_size:]  # Skip overlap
   ```

2. **Text-based (fallback)**: Finds common suffix/prefix
   ```python
   overlap_size = self._find_text_overlap(result_text, chunk_text)
   if overlap_size > 0:
       result_text += chunk_text[overlap_size:]  # Skip overlap
   ```

**Result**: Original document is perfectly reconstructed, even with overlapping chunks.

## Embedding Configuration

### How Embedding is Determined

**Priority order:**

1. **Explicit parameter**: `embedding="custom_local"` in `create_collection()`
2. **Auto-detection**: `embedding="auto"` (default) checks environment:
   - If `CUSTOM_EMBEDDING_URL`, `CUSTOM_EMBEDDING_MODEL`, and `CUSTOM_EMBEDDING_VECTORSIZE` are set → uses `custom_local`
   - Otherwise → falls back to `text-embedding-ada-002` (OpenAI)

From [`src/maestro_mcp/server.py:1690-1703`](../src/maestro_mcp/server.py):
```python
if embedding == "auto":
    # Check if custom embedding is configured
    if os.getenv("CUSTOM_EMBEDDING_URL") and os.getenv("CUSTOM_EMBEDDING_MODEL"):
        resolved_embedding = "custom_local"
        logger.info("Auto-detected custom_local embedding from environment")
    else:
        resolved_embedding = "text-embedding-ada-002"
        logger.info("No custom embedding configured, using default OpenAI")
```

### Environment Variables

**For custom embeddings:**
```bash
CUSTOM_EMBEDDING_URL=http://localhost:11434/api/embeddings
CUSTOM_EMBEDDING_MODEL=nomic-embed-text
CUSTOM_EMBEDDING_VECTORSIZE=768
```

**For OpenAI embeddings:**
```bash
OPENAI_API_KEY=sk-...
```

## Metadata Persistence Issue

**Current limitation**: Chunking and embedding metadata is stored in memory (`_collections_metadata`) and lost on server restart.

**Workaround**: The system shows defaults with a note when metadata is unavailable.

**Future solution**: See [`docs/TODO_COLLECTION_METADATA_PERSISTENCE.md`](TODO_COLLECTION_METADATA_PERSISTENCE.md) for planned improvements.

## Best Practices

### Choosing Chunk Size

**Small chunks (256-512 chars):**
- ✅ More precise search results
- ✅ Better for specific facts
- ❌ May lose context
- ❌ More chunks to process

**Medium chunks (512-1024 chars):**
- ✅ Good balance of precision and context
- ✅ Works well for most use cases
- ✅ Default recommendation

**Large chunks (1024-2048 chars):**
- ✅ More context preserved
- ✅ Better for complex topics
- ❌ Less precise search
- ❌ May include irrelevant content

### Choosing Overlap

**No overlap (0):**
- ✅ Simple, efficient
- ✅ Good for most use cases
- ✅ **Recommended default**

**Small overlap (50-100):**
- ✅ Minimal storage overhead
- ✅ Helps with boundary cases
- ✅ Good compromise

**Large overlap (200+):**
- ✅ Maximum context preservation
- ❌ Significant storage overhead
- ❌ Use only when necessary

### Choosing Strategy

**Sentence (Default):**
- ✅ Respects sentence boundaries
- ✅ Better semantic coherence
- ✅ Good for natural language
- ✅ **Recommended for most use cases**

**Fixed:**
- ✅ Predictable chunk sizes
- ✅ Simple and fast
- ✅ Good for structured data

**Semantic:**
- ✅ Best semantic coherence
- ✅ Topic-aware splitting
- ❌ Slower, more expensive
- ❌ Use for high-quality requirements

**None:**
- ✅ No processing overhead
- ✅ Good for pre-chunked content
- ❌ Not recommended for large documents

## Examples

### Example 1: Default Configuration
```python
create_collection(collection="docs")
# Uses: Sentence strategy, chunk_size=512, overlap=0
```

### Example 2: Custom Chunking
```python
create_collection(
    collection="docs",
    chunking_config={
        "strategy": "Sentence",
        "parameters": {
            "chunk_size": 1024,
            "overlap": 100
        }
    }
)
```

### Example 3: No Chunking
```python
create_collection(
    collection="docs",
    chunking_config={
        "strategy": "None"
    }
)
```

### Example 4: Semantic Chunking
```python
create_collection(
    collection="docs",
    chunking_config={
        "strategy": "Semantic",
        "parameters": {
            "chunk_size": 768,
            "overlap": 0,
            "window_size": 1,
            "threshold_percentile": 95.0
        }
    }
)
```

## Summary

1. **Default chunking**: Sentence strategy, 512 chars, 0 overlap
2. **Configuration**: Via `chunking_config` parameter in `create_collection()`
3. **Overlap handling**: ✅ Fully supported during reassembly
4. **Overlap default**: 0 is appropriate for most use cases
5. **Embedding**: Auto-detected from environment or explicitly specified
6. **Metadata persistence**: Currently in-memory only (future improvement planned)

## Related Documentation

- [`docs/TODO_COLLECTION_METADATA_PERSISTENCE.md`](TODO_COLLECTION_METADATA_PERSISTENCE.md) - Metadata persistence plans
- [`src/chunking/common.py`](../src/chunking/common.py) - Chunking implementation
- [`src/db/vector_db_base.py`](../src/db/vector_db_base.py) - Reassembly logic
- [`docs/MIGRATION_GUIDE.md`](MIGRATION_GUIDE.md) - API reference