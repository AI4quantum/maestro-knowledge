# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""Document ID generation utilities.

This module provides deterministic document ID generation based on URL or text content.
Document IDs are used as the primary identifier for all document operations.
"""

import hashlib
from typing import Any


def generate_document_id(text: str, url: str | None = None) -> str:
    """Generate a deterministic document ID.

    Strategy:
    1. If URL provided and non-empty: Use hash of URL
    2. Otherwise: Use hash of text content

    This ensures:
    - Same URL always gets same ID (prevents duplicates)
    - Same text gets same ID if no URL (idempotent writes)
    - Deterministic and reproducible

    Args:
        text: Document text content
        url: Optional source URL

    Returns:
        16-character hexadecimal document ID

    Examples:
        >>> generate_document_id("Hello world", "https://example.com/doc")
        'a1b2c3d4e5f6g7h8'  # Based on URL hash

        >>> generate_document_id("Hello world", None)
        'x1y2z3w4v5u6t7s8'  # Based on text hash

        >>> generate_document_id("Hello world", "")
        'x1y2z3w4v5u6t7s8'  # Empty URL treated as None
    """
    if url and url.strip():
        # Use URL-based ID for documents with URLs
        return hashlib.sha256(url.encode()).hexdigest()[:16]
    else:
        # Use content-based ID for documents without URLs
        return hashlib.sha256(text.encode()).hexdigest()[:16]


def extract_document_id_from_metadata(metadata: dict[str, Any]) -> str | None:
    """Extract document_id from metadata dict.

    Args:
        metadata: Metadata dictionary that may contain document_id

    Returns:
        Document ID if present, None otherwise
    """
    return metadata.get("document_id")


def add_document_id_to_metadata(
    metadata: dict[str, Any], document_id: str
) -> dict[str, Any]:
    """Add document_id to metadata dict.

    Args:
        metadata: Metadata dictionary to update
        document_id: Document ID to add

    Returns:
        Updated metadata dictionary (modifies in place and returns)
    """
    metadata["document_id"] = document_id
    return metadata


# Made with Bob
