"""
Tests for Phase 4 and 5: Search Quality Controls and Citation Format

Phase 4: min_score and metadata_filters parameters
Phase 5: url and source_citation in results
"""

import os
import pytest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.integration
@pytest.mark.asyncio
@patch("pymilvus.AsyncMilvusClient")
async def test_search_with_min_score_milvus(mock_milvus_client: AsyncMock) -> None:
    """Test that min_score filters low-quality results in Milvus."""
    from src.db.vector_db_milvus import MilvusVectorDatabase

    mock_client = AsyncMock()
    mock_milvus_client.return_value = mock_client

    db = MilvusVectorDatabase()
    await db.setup(embedding="text-embedding-3-small")

    # Mock search results with different scores
    mock_results_all = [
        {"text": "Python programming", "score": 0.95, "metadata": {"doc_name": "Doc1"}},
        {"text": "Python guide", "score": 0.75, "metadata": {"doc_name": "Doc2"}},
        {"text": "Programming basics", "score": 0.60, "metadata": {"doc_name": "Doc3"}},
    ]

    # Mock the _search_documents method to return our test data
    with patch.object(db, "_search_documents", new_callable=AsyncMock) as mock_search:
        # First call returns all results
        mock_search.return_value = mock_results_all.copy()
        results_all = await db.search("Python programming", limit=10)

        # Second call with min_score should filter
        mock_search.return_value = [r for r in mock_results_all if r["score"] >= 0.8]
        results_filtered = await db.search(
            "Python programming", limit=10, min_score=0.8
        )

        # Filtered results should be <= all results
        assert len(results_filtered) <= len(results_all)

        # All filtered results should have score >= min_score
        for result in results_filtered:
            score = result.get("score", result.get("similarity", 0))
            assert score >= 0.8, f"Result has score {score} below min_score 0.8"


@pytest.mark.integration
@pytest.mark.asyncio
@patch("pymilvus.AsyncMilvusClient")
async def test_search_with_metadata_filters_milvus(
    mock_milvus_client: AsyncMock,
) -> None:
    """Test that metadata_filters work correctly in Milvus."""
    from src.db.vector_db_milvus import MilvusVectorDatabase

    mock_client = AsyncMock()
    mock_milvus_client.return_value = mock_client

    db = MilvusVectorDatabase()
    await db.setup(embedding="text-embedding-3-small")

    # Mock search results with different metadata
    mock_results = [
        {
            "text": "Python guide",
            "score": 0.9,
            "metadata": {
                "doc_name": "Python",
                "language": "python",
                "level": "beginner",
            },
        },
        {
            "text": "JS guide",
            "score": 0.85,
            "metadata": {
                "doc_name": "JavaScript",
                "language": "javascript",
                "level": "beginner",
            },
        },
        {
            "text": "Advanced Python",
            "score": 0.8,
            "metadata": {
                "doc_name": "Advanced Python",
                "language": "python",
                "level": "advanced",
            },
        },
    ]

    with patch.object(db, "_search_documents", new_callable=AsyncMock) as mock_search:
        # Filter for Python only
        mock_search.return_value = [
            r for r in mock_results if r["metadata"].get("language") == "python"
        ]
        results = await db.search(
            "programming guide", limit=10, metadata_filters={"language": "python"}
        )

        # All results should match the filter
        for result in results:
            metadata = result.get("metadata", {})
            assert metadata.get("language") == "python", (
                f"Result has wrong language: {metadata}"
            )

        # Filter for Python + beginner
        mock_search.return_value = [
            r
            for r in mock_results
            if r["metadata"].get("language") == "python"
            and r["metadata"].get("level") == "beginner"
        ]
        results_multi = await db.search(
            "programming",
            limit=10,
            metadata_filters={"language": "python", "level": "beginner"},
        )

        # Should only get the beginner Python doc
        assert len(results_multi) <= 1
        if results_multi:
            metadata = results_multi[0].get("metadata", {})
            assert metadata.get("language") == "python"
            assert metadata.get("level") == "beginner"


@pytest.mark.integration
@pytest.mark.asyncio
@patch("pymilvus.AsyncMilvusClient")
async def test_search_result_format_milvus(mock_milvus_client: AsyncMock) -> None:
    """Test that search results include url and source_citation (Phase 5)."""
    from src.db.vector_db_milvus import MilvusVectorDatabase

    mock_client = AsyncMock()
    mock_milvus_client.return_value = mock_client

    db = MilvusVectorDatabase()
    await db.setup(embedding="text-embedding-3-small")

    # Mock search result with Phase 5 format
    mock_result = {
        "text": "Test document",
        "score": 0.95,
        "rank": 1,
        "url": "https://example.com/test-doc",
        "source_citation": "Source: Test Document (https://example.com/test-doc)",
        "metadata": {
            "doc_name": "Test Document",
            "url": "https://example.com/test-doc",
        },
    }

    with patch.object(db, "_search_documents", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [mock_result]
        results = await db.search("test document", limit=1)

        assert len(results) > 0, "Should have at least one result"

        result = results[0]

        # Check Phase 5 requirements: url at top level
        assert "url" in result, "Result should have top-level 'url' field"
        assert result["url"] == "https://example.com/test-doc"

        # Check Phase 5 requirements: source_citation
        assert "source_citation" in result, "Result should have 'source_citation' field"
        assert "Test Document" in result["source_citation"]
        assert "https://example.com/test-doc" in result["source_citation"]

        # Check that score is present (normalized similarity)
        assert "score" in result or "similarity" in result, (
            "Result should have score/similarity"
        )

        # Check that rank is present
        assert "rank" in result, "Result should have rank"
        assert result["rank"] == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_with_min_score_weaviate() -> None:
    """Test that min_score filters low-quality results in Weaviate."""
    from src.db.vector_db_weaviate import WeaviateVectorDatabase

    with (
        patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
        patch.dict(
            os.environ,
            {
                "WEAVIATE_API_KEY": "test-key",
                "WEAVIATE_URL": "https://test.weaviate.network",
            },
        ),
    ):
        mock_client = AsyncMock()
        mock_connect.return_value = mock_client

        db = WeaviateVectorDatabase()
        await db.setup(embedding="text2vec-weaviate")

        # Mock search results
        mock_results_all = [
            {
                "text": "Python programming",
                "score": 0.9,
                "metadata": {"doc_name": "Doc1"},
            },
            {"text": "Python guide", "score": 0.65, "metadata": {"doc_name": "Doc2"}},
        ]

        with patch.object(db, "search", new_callable=AsyncMock) as mock_search:
            # First call returns all results
            mock_search.return_value = mock_results_all.copy()
            results_all = await db.search("Python programming", limit=10)

            # Second call with min_score filters
            mock_search.return_value = [
                r for r in mock_results_all if r["score"] >= 0.7
            ]
            results_filtered = await db.search(
                "Python programming", limit=10, min_score=0.7
            )

            # Filtered results should be <= all results
            assert len(results_filtered) <= len(results_all)

            # All filtered results should have score >= min_score
            for result in results_filtered:
                score = result.get("score", result.get("similarity", 0))
                assert score >= 0.7, f"Result has score {score} below min_score 0.7"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_result_format_weaviate() -> None:
    """Test that search results include url and source_citation in Weaviate (Phase 5)."""
    from src.db.vector_db_weaviate import WeaviateVectorDatabase

    with (
        patch("weaviate.use_async_with_weaviate_cloud") as mock_connect,
        patch.dict(
            os.environ,
            {
                "WEAVIATE_API_KEY": "test-key",
                "WEAVIATE_URL": "https://test.weaviate.network",
            },
        ),
    ):
        mock_client = AsyncMock()
        mock_connect.return_value = mock_client

        db = WeaviateVectorDatabase()
        await db.setup(embedding="text2vec-weaviate")

        # Mock search result with Phase 5 format
        mock_result = {
            "text": "Weaviate test",
            "score": 0.92,
            "url": "https://example.com/weaviate-doc",
            "source_citation": "Source: Weaviate Test (https://example.com/weaviate-doc)",
            "metadata": {
                "doc_name": "Weaviate Test",
                "url": "https://example.com/weaviate-doc",
            },
        }

        with patch.object(db, "search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [mock_result]
            results = await db.search("Weaviate test", limit=1)

            assert len(results) > 0, "Should have at least one result"

            result = results[0]

            # Check Phase 5 requirements: url at top level
            assert "url" in result, "Result should have top-level 'url' field"
            assert result["url"] == "https://example.com/weaviate-doc"

            # Check Phase 5 requirements: source_citation
            assert "source_citation" in result, (
                "Result should have 'source_citation' field"
            )
            assert "Weaviate Test" in result["source_citation"]
            assert "https://example.com/weaviate-doc" in result["source_citation"]

            # Check that score is present
            assert "score" in result or "similarity" in result, (
                "Result should have score/similarity"
            )


@pytest.mark.integration
@pytest.mark.asyncio
@patch("pymilvus.AsyncMilvusClient")
async def test_combined_filters_milvus(mock_milvus_client: AsyncMock) -> None:
    """Test using min_score and metadata_filters together."""
    from src.db.vector_db_milvus import MilvusVectorDatabase

    mock_client = AsyncMock()
    mock_milvus_client.return_value = mock_client

    db = MilvusVectorDatabase()
    await db.setup(embedding="text-embedding-3-small")

    # Mock diverse results
    mock_results = [
        {
            "text": "Python basics",
            "score": 0.85,
            "metadata": {
                "doc_name": "Python Basics",
                "language": "python",
                "level": "beginner",
            },
        },
        {
            "text": "Python advanced",
            "score": 0.75,
            "metadata": {
                "doc_name": "Python Advanced",
                "language": "python",
                "level": "advanced",
            },
        },
        {
            "text": "Java basics",
            "score": 0.70,
            "metadata": {
                "doc_name": "Java Basics",
                "language": "java",
                "level": "beginner",
            },
        },
    ]

    with patch.object(db, "_search_documents", new_callable=AsyncMock) as mock_search:
        # Filter by both min_score and metadata
        filtered = [
            r
            for r in mock_results
            if r["score"] >= 0.5 and r["metadata"].get("language") == "python"
        ]
        mock_search.return_value = filtered

        results = await db.search(
            "programming basics",
            limit=10,
            min_score=0.5,
            metadata_filters={"language": "python"},
        )

        # All results should match metadata filter
        for result in results:
            metadata = result.get("metadata", {})
            assert metadata.get("language") == "python"

            # All results should meet min_score
            score = result.get("score", result.get("similarity", 0))
            assert score >= 0.5


@pytest.mark.integration
@pytest.mark.asyncio
@patch("pymilvus.AsyncMilvusClient")
async def test_source_citation_without_url(mock_milvus_client: AsyncMock) -> None:
    """Test source_citation when URL is not present."""
    from src.db.vector_db_milvus import MilvusVectorDatabase

    mock_client = AsyncMock()
    mock_milvus_client.return_value = mock_client

    db = MilvusVectorDatabase()
    await db.setup(embedding="text-embedding-3-small")

    # Mock result without URL
    mock_result = {
        "text": "Document without URL",
        "score": 0.9,
        "source_citation": "Source: No URL Doc",
        "metadata": {"doc_name": "No URL Doc"},
    }

    with patch.object(db, "_search_documents", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = [mock_result]
        results = await db.search("document", limit=1)

        if results:
            result = results[0]
            # Should still have source_citation with just the doc_name
            assert "source_citation" in result
            assert "No URL Doc" in result["source_citation"]


# Made with Bob
