#!/usr/bin/env python3
# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""
E2E tests for Phase 4 and Phase 5: Search Quality Controls and Citation Format

Phase 4: min_score and metadata_filters parameters
Phase 5: url and source_citation in results

These tests verify the complete end-to-end functionality with real vector databases.
"""

import os
import pytest
from typing import Any

# Mark all tests in this file as e2e
pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_search_with_min_score_e2e() -> None:
    """Test search with min_score parameter end-to-end (Phase 4)."""
    backend = os.getenv("E2E_BACKEND", "milvus")

    if backend == "milvus":
        from src.db.vector_db_milvus import MilvusVectorDatabase

        db = MilvusVectorDatabase()
    else:
        from src.db.vector_db_weaviate import WeaviateVectorDatabase

        db = WeaviateVectorDatabase()

    try:
        # Setup with custom embedding
        await db.setup(
            embedding="custom_local",
            chunking_config={
                "strategy": "Sentence",
                "parameters": {"chunk_size": 256, "overlap": 1},
            },
        )

        # Create collection
        collection_name = "test_min_score_e2e"
        await db.create_collection(collection_name, embedding="custom_local")

        # Write test documents with different relevance
        documents = [
            {
                "url": "doc1",
                "text": "Python is a high-level programming language.",
                "metadata": {"topic": "python", "relevance": "high"},
            },
            {
                "url": "doc2",
                "text": "Programming languages are used to write software.",
                "metadata": {"topic": "general", "relevance": "medium"},
            },
            {
                "url": "doc3",
                "text": "The weather is nice today.",
                "metadata": {"topic": "weather", "relevance": "low"},
            },
        ]

        result = await db.write_documents(documents)
        assert result["documents"] == 3, "Should write 3 documents"

        # Search without min_score - should return all relevant results
        results_all = await db.search("Python programming", limit=10)
        count_all = len(results_all)

        # Search with min_score=0.7 - should filter low-quality results
        results_filtered = await db.search(
            "Python programming", limit=10, min_score=0.7
        )
        count_filtered = len(results_filtered)

        # Filtered results should be <= all results
        assert count_filtered <= count_all, (
            f"Filtered results ({count_filtered}) should be <= all results ({count_all})"
        )

        # All filtered results should have score >= min_score
        for result in results_filtered:
            score = result.get("score", 0)
            assert score >= 0.7, f"Result has score {score} below min_score 0.7"

    finally:
        await db.cleanup()


@pytest.mark.asyncio
async def test_search_with_metadata_filters_e2e() -> None:
    """Test search with metadata_filters parameter end-to-end (Phase 4)."""
    backend = os.getenv("E2E_BACKEND", "milvus")

    if backend == "milvus":
        from src.db.vector_db_milvus import MilvusVectorDatabase

        db = MilvusVectorDatabase()
    else:
        from src.db.vector_db_weaviate import WeaviateVectorDatabase

        db = WeaviateVectorDatabase()

    try:
        # Setup
        await db.setup(
            embedding="custom_local",
            chunking_config={
                "strategy": "Sentence",
                "parameters": {"chunk_size": 256, "overlap": 1},
            },
        )

        # Create collection
        collection_name = "test_metadata_filters_e2e"
        await db.create_collection(collection_name, embedding="custom_local")

        # Write documents with different metadata
        documents = [
            {
                "url": "python_beginner",
                "text": "Python basics for beginners.",
                "metadata": {"language": "python", "level": "beginner"},
            },
            {
                "url": "python_advanced",
                "text": "Advanced Python techniques.",
                "metadata": {"language": "python", "level": "advanced"},
            },
            {
                "url": "javascript_beginner",
                "text": "JavaScript basics for beginners.",
                "metadata": {"language": "javascript", "level": "beginner"},
            },
        ]

        result = await db.write_documents(documents)
        assert result["documents"] == 3, "Should write 3 documents"

        # Search with metadata filter for Python only
        results_python = await db.search(
            "programming basics",
            limit=10,
            metadata_filters={"language": "python"},
        )

        # All results should be Python documents
        for result in results_python:
            metadata = result.get("metadata", {})
            assert metadata.get("language") == "python", (
                f"Result should be Python but got {metadata.get('language')}"
            )

        # Search with multiple metadata filters
        results_python_beginner = await db.search(
            "programming basics",
            limit=10,
            metadata_filters={"language": "python", "level": "beginner"},
        )

        # All results should match both filters
        for result in results_python_beginner:
            metadata = result.get("metadata", {})
            assert metadata.get("language") == "python"
            assert metadata.get("level") == "beginner"

    finally:
        await db.cleanup()


@pytest.mark.asyncio
async def test_search_with_combined_filters_e2e() -> None:
    """Test search with both min_score and metadata_filters (Phase 4)."""
    backend = os.getenv("E2E_BACKEND", "milvus")

    if backend == "milvus":
        from src.db.vector_db_milvus import MilvusVectorDatabase

        db = MilvusVectorDatabase()
    else:
        from src.db.vector_db_weaviate import WeaviateVectorDatabase

        db = WeaviateVectorDatabase()

    try:
        # Setup
        await db.setup(
            embedding="custom_local",
            chunking_config={
                "strategy": "Sentence",
                "parameters": {"chunk_size": 256, "overlap": 1},
            },
        )

        # Create collection
        collection_name = "test_combined_filters_e2e"
        await db.create_collection(collection_name, embedding="custom_local")

        # Write documents
        documents = [
            {
                "url": "python_ml",
                "text": "Python machine learning with scikit-learn.",
                "metadata": {"language": "python", "category": "ml"},
            },
            {
                "url": "python_web",
                "text": "Python web development with Django.",
                "metadata": {"language": "python", "category": "web"},
            },
            {
                "url": "js_ml",
                "text": "JavaScript machine learning with TensorFlow.js.",
                "metadata": {"language": "javascript", "category": "ml"},
            },
        ]

        result = await db.write_documents(documents)
        assert result["documents"] == 3, "Should write 3 documents"

        # Search with both filters
        results = await db.search(
            "machine learning",
            limit=10,
            min_score=0.5,
            metadata_filters={"language": "python"},
        )

        # All results should meet both criteria
        for result in results:
            # Check score threshold
            score = result.get("score", 0)
            assert score >= 0.5, f"Result has score {score} below min_score 0.5"

            # Check metadata filter
            metadata = result.get("metadata", {})
            assert metadata.get("language") == "python", (
                f"Result should be Python but got {metadata.get('language')}"
            )

    finally:
        await db.cleanup()


@pytest.mark.asyncio
async def test_citation_format_e2e() -> None:
    """Test that search results include proper citation format (Phase 5)."""
    backend = os.getenv("E2E_BACKEND", "milvus")

    if backend == "milvus":
        from src.db.vector_db_milvus import MilvusVectorDatabase

        db = MilvusVectorDatabase()
    else:
        from src.db.vector_db_weaviate import WeaviateVectorDatabase

        db = WeaviateVectorDatabase()

    try:
        # Setup
        await db.setup(
            embedding="custom_local",
            chunking_config={
                "strategy": "Sentence",
                "parameters": {"chunk_size": 256, "overlap": 1},
            },
        )

        # Create collection
        collection_name = "test_citation_format_e2e"
        await db.create_collection(collection_name, embedding="custom_local")

        # Write document with URL
        documents = [
            {
                "url": "https://example.com/python-guide",
                "text": "Python programming guide for beginners.",
                "metadata": {"title": "Python Guide", "author": "John Doe"},
            }
        ]

        result = await db.write_documents(documents)
        assert result["documents"] == 1, "Should write 1 document"

        # Search and check citation format
        results = await db.search("Python programming", limit=10)

        assert len(results) > 0, "Should return at least one result"

        result = results[0]

        # Phase 5 requirements: url at top level
        assert "url" in result, "Result should have top-level 'url' field"
        assert result["url"] == "https://example.com/python-guide"

        # Phase 5 requirements: source_citation field
        assert "source_citation" in result, "Result should have 'source_citation' field"
        citation = result["source_citation"]
        assert "https://example.com/python-guide" in citation, (
            f"Citation should include URL: {citation}"
        )

        # Phase 5 requirements: score field at top level
        assert "score" in result, "Result should have top-level 'score' field"
        assert isinstance(result["score"], (int, float)), "Score should be numeric"
        assert 0 <= result["score"] <= 1, "Score should be normalized 0-1"

    finally:
        await db.cleanup()


@pytest.mark.asyncio
async def test_citation_without_url_e2e() -> None:
    """Test citation format when document has no URL (Phase 5)."""
    backend = os.getenv("E2E_BACKEND", "milvus")

    if backend == "milvus":
        from src.db.vector_db_milvus import MilvusVectorDatabase

        db = MilvusVectorDatabase()
    else:
        from src.db.vector_db_weaviate import WeaviateVectorDatabase

        db = WeaviateVectorDatabase()

    try:
        # Setup
        await db.setup(
            embedding="custom_local",
            chunking_config={
                "strategy": "Sentence",
                "parameters": {"chunk_size": 256, "overlap": 1},
            },
        )

        # Create collection
        collection_name = "test_citation_no_url_e2e"
        await db.create_collection(collection_name, embedding="custom_local")

        # Write document without URL (just doc_name)
        documents = [
            {
                "url": "simple_doc",
                "text": "This is a simple document without a URL.",
                "metadata": {"title": "Simple Doc"},
            }
        ]

        result = await db.write_documents(documents)
        assert result["documents"] == 1, "Should write 1 document"

        # Search and check citation
        results = await db.search("simple document", limit=10)

        assert len(results) > 0, "Should return at least one result"

        result = results[0]

        # Should still have source_citation with doc_name
        assert "source_citation" in result, "Result should have 'source_citation' field"
        citation = result["source_citation"]
        assert "simple_doc" in citation.lower(), (
            f"Citation should include doc name: {citation}"
        )

    finally:
        await db.cleanup()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "e2e"])

# Made with Bob
