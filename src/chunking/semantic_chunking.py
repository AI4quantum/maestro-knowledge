"""Semantic chunking strategy that creates chunks based on semantic similarity between sentences."""

import re
from typing import Dict, List, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


def _split_text_to_sentences(text: str) -> List[Tuple[int, int, str]]:
    """Split text into sentences with their positions and content.

    Returns list of tuples: (start_offset, end_offset, sentence_text)
    Treats code blocks (```...```) as single sentences to preserve context.
    """
    # Find all code blocks and their positions
    code_blocks = []
    for match in re.finditer(r"```.*?```", text, re.DOTALL):
        code_blocks.append((match.start(), match.end(), match.group()))

    # Replace code blocks with placeholders
    placeholder = "CODE_BLOCK_PLACEHOLDER"
    text_with_placeholders = re.sub(r"```.*?```", placeholder, text, flags=re.DOTALL)

    # Split into sentences using regex (lightweight approach)
    sentences = []
    pattern = re.compile(r"([^.!?\n]+[.!?\n]?)", re.M)

    for match in pattern.finditer(text_with_placeholders):
        start = match.start()
        end = match.end()
        sentence_text = match.group()

        # Replace placeholder with actual code block if present
        if placeholder in sentence_text:
            for cb_start, cb_end, cb_text in code_blocks:
                if cb_start >= start and cb_end <= start + len(sentence_text):
                    sentence_text = sentence_text.replace(placeholder, cb_text)
                    break

        sentences.append((start, end, sentence_text))

    # Handle case where no sentences found
    if not sentences and text.strip():
        sentences = [(0, len(text), text)]

    return sentences


def _create_sliding_windows(
    sentences: List[Tuple[int, int, str]], window_size: int = 1
) -> List[Dict[str, object]]:
    """Create sliding window context around each sentence.

    Args:
        sentences: List of (start, end, text) tuples
        window_size: Number of sentences before/after to include in context

    Returns:
        List of dicts with sentence info and combined context
    """
    windowed_sentences = []

    for i, (start, end, text) in enumerate(sentences):
        # Collect sentences before current
        before_text = ""
        before_start = start
        for j in range(max(0, i - window_size), i):
            if j < len(sentences):
                before_text += sentences[j][2] + " "
                before_start = min(before_start, sentences[j][0])

        # Current sentence
        current_text = text

        # Collect sentences after current
        after_text = ""
        after_end = end
        for j in range(i + 1, min(len(sentences), i + 1 + window_size)):
            if j < len(sentences):
                after_text += " " + sentences[j][2]
                after_end = max(after_end, sentences[j][1])

        # Combine all context
        combined_text = (before_text + current_text + after_text).strip()

        windowed_sentences.append(
            {
                "sentence": text,
                "start": start,
                "end": end,
                "combined_text": combined_text,
                "context_start": before_start,
                "context_end": after_end,
                "index": i,
            }
        )

    return windowed_sentences


def _embed_sentences(
    sentences: List[Dict[str, object]], model_name: str = "all-MiniLM-L6-v2"
) -> List[Dict[str, object]]:
    """Create embeddings for the combined sentence contexts."""
    try:
        model = SentenceTransformer(model_name)
        texts = [s["combined_text"] for s in sentences]
        embeddings = model.encode(texts, show_progress_bar=False)

        for i, sentence in enumerate(sentences):
            sentence["embedding"] = embeddings[i]

    except Exception:
        # Fallback: create random embeddings if model fails
        for sentence in sentences:
            sentence["embedding"] = np.random.rand(384)

    return sentences


def _calculate_semantic_distances(sentences: List[Dict[str, object]]) -> List[float]:
    """Calculate semantic distance between consecutive sentence windows."""
    distances = []

    for i in range(len(sentences) - 1):
        try:
            emb1 = sentences[i]["embedding"].reshape(1, -1)
            emb2 = sentences[i + 1]["embedding"].reshape(1, -1)

            similarity = cosine_similarity(emb1, emb2)[0][0]
            distance = 1 - similarity
            distances.append(distance)

        except Exception:
            text1 = sentences[i]["combined_text"]
            text2 = sentences[i + 1]["combined_text"]
            distance = abs(len(text1) - len(text2)) / max(len(text1), len(text2))
            distances.append(distance)

    return distances


def _find_chunk_boundaries(
    distances: List[float], threshold_percentile: float = 95
) -> List[int]:
    """Find indices where chunks should be split based on semantic distance.

    Args:
        distances: List of distances between consecutive sentences
        threshold_percentile: Percentile above which to consider a split point

    Returns:
        List of indices where chunks should be split
    """
    if not distances:
        return []

    threshold = np.percentile(distances, threshold_percentile)
    split_indices = [i for i, distance in enumerate(distances) if distance > threshold]
    return split_indices


def _create_chunks_from_boundaries(
    sentences: List[Dict[str, object]], split_indices: List[int]
) -> List[Dict[str, object]]:
    """Create chunks based on the identified split points.

    Args:
        sentences: List of sentence dicts
        split_indices: Indices where chunks should be split

    Returns:
        List of chunk dicts with standard format
    """
    chunks = []
    start_idx = 0

    for split_idx in split_indices:
        end_idx = split_idx

        # Collect all sentences in this chunk
        chunk_sentences = sentences[start_idx : end_idx + 1]
        # Combine text and find boundaries
        chunk_text = " ".join(s["sentence"] for s in chunk_sentences)
        chunk_start = chunk_sentences[0]["context_start"] if chunk_sentences else 0
        chunk_end = chunk_sentences[-1]["context_end"] if chunk_sentences else 0

        chunks.append(
            {
                "text": chunk_text,
                "offset_start": chunk_start,
                "offset_end": chunk_end,
                "chunk_size": len(chunk_text),
                "sequence": len(chunks),
                "total": 0,  # Will be set by caller
                "semantic_info": {
                    "strategy": "Semantic",
                    "sentences_in_chunk": len(chunk_sentences),
                    "split_reason": "semantic_boundary",
                },
            }
        )

        start_idx = split_idx + 1

    # Handle the last chunk
    if start_idx < len(sentences):
        chunk_sentences = sentences[start_idx:]
        chunk_text = " ".join(s["sentence"] for s in chunk_sentences)
        chunk_start = chunk_sentences[0]["context_start"] if chunk_sentences else 0
        chunk_end = chunk_sentences[-1]["context_end"] if chunk_sentences else 0

        chunks.append(
            {
                "text": chunk_text,
                "offset_start": chunk_start,
                "offset_end": chunk_end,
                "chunk_size": len(chunk_text),
                "sequence": len(chunks),
                "total": 0,  # Will be set by caller
                "semantic_info": {
                    "strategy": "Semantic",
                    "sentences_in_chunk": len(chunk_sentences),
                    "split_reason": "final_chunk",
                },
            }
        )

    return chunks


def semantic_chunk(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 0,
    window_size: int = 1,
    threshold_percentile: float = 95,
    model_name: str = "all-MiniLM-L6-v2",
) -> List[Dict[str, object]]:
    """Create semantically coherent chunks based on sentence similarity.

    This strategy finds natural topic boundaries using sentence embeddings
    and similarity, then respects the chunk_size limit.
    """
    if not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0:
        raise ValueError("overlap must be >= 0")
    if overlap > chunk_size:
        raise ValueError("overlap must be <= chunk_size")
    if threshold_percentile < 0 or threshold_percentile > 100:
        raise ValueError("threshold_percentile must be between 0 and 100")

    # Step 1: Split into sentences with positions
    sentences = _split_text_to_sentences(text)

    if len(sentences) <= 1:
        # Single sentence or no sentences - return as single chunk
        start, end, content = sentences[0] if sentences else (0, 0, "")
        return [
            {
                "text": content,
                "offset_start": start,
                "offset_end": end,
                "chunk_size": len(content),
                "sequence": 0,
                "total": 1,
                "semantic_info": {
                    "strategy": "Semantic",
                    "sentences_in_chunk": 1,
                    "split_reason": "single_sentence",
                },
            }
        ]

    # Step 2: Create sliding window context
    windowed_sentences = _create_sliding_windows(sentences, window_size)

    # Step 3: Generate embeddings
    embedded_sentences = _embed_sentences(windowed_sentences, model_name)

    # Step 4: Calculate semantic distances
    distances = _calculate_semantic_distances(embedded_sentences)

    # Step 5: Find semantic split points
    split_indices = _find_chunk_boundaries(distances, threshold_percentile)

    # Step 6: Create initial chunks
    chunks = _create_chunks_from_boundaries(embedded_sentences, split_indices)

    # Step 7: Enforce chunk_size limit by splitting oversized chunks
    final_chunks = []
    for chunk in chunks:
        if chunk["chunk_size"] <= chunk_size:
            final_chunks.append(chunk)
        else:
            # Split oversized chunk using fixed strategy
            text = chunk["text"]
            start_offset = chunk["offset_start"]

            step = max(1, chunk_size - overlap)
            for i in range(0, len(text), step):
                end = min(i + chunk_size, len(text))
                chunk_text = text[i:end]

                final_chunks.append(
                    {
                        "text": chunk_text,
                        "offset_start": start_offset + i,
                        "offset_end": start_offset + end,
                        "chunk_size": len(chunk_text),
                        "sequence": len(final_chunks),
                        "total": 0,  # Will be set by caller
                        "semantic_info": {
                            "strategy": "Semantic",
                            "sentences_in_chunk": 1,  # Approximate
                            "split_reason": "size_limit_enforced",
                        },
                    }
                )

    # Set total count
    for chunk in final_chunks:
        chunk["total"] = len(final_chunks)

    return final_chunks


# Register this strategy with the chunking system
from .common import register_strategy

register_strategy("Semantic", semantic_chunk)
