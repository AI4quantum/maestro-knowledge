# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""Tests for document ID generation and usage."""

import pytest
from src.db.document_id import generate_document_id


@pytest.mark.unit
class TestDocumentIDGeneration:
    """Test document ID generation logic."""

    def test_generate_id_from_url(self) -> None:
        """Test document ID generation from URL."""
        url = "https://example.com/doc.pdf"
        text = "Some content"

        doc_id = generate_document_id(text, url)

        # Should be 16-char hex string
        assert len(doc_id) == 16
        assert all(c in "0123456789abcdef" for c in doc_id)

        # Same URL should generate same ID
        doc_id2 = generate_document_id("Different text", url)
        assert doc_id == doc_id2

    def test_generate_id_from_text(self) -> None:
        """Test document ID generation from text when no URL."""
        text = "Some content"

        doc_id = generate_document_id(text, None)

        # Should be 16-char hex string
        assert len(doc_id) == 16
        assert all(c in "0123456789abcdef" for c in doc_id)

        # Same text should generate same ID
        doc_id2 = generate_document_id(text, None)
        assert doc_id == doc_id2

        # Different text should generate different ID
        doc_id3 = generate_document_id("Different content", None)
        assert doc_id != doc_id3

    def test_url_takes_precedence(self) -> None:
        """Test that URL-based ID takes precedence over text-based."""
        url = "https://example.com/doc.pdf"
        text1 = "Content 1"
        text2 = "Content 2"

        # Same URL with different text should give same ID
        doc_id1 = generate_document_id(text1, url)
        doc_id2 = generate_document_id(text2, url)
        assert doc_id1 == doc_id2


# Made with Bob
