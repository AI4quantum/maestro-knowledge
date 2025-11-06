#!/usr/bin/env python3
# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""
Simplified document ingestion example showing URL-based document loading.

This example demonstrates the enhanced document ingestion capabilities:
- Automatic fetching from URLs
- Automatic content type detection
- Automatic conversion (HTML, PDF, Markdown, Text)
- Backwards compatible with direct text provision
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.vector_db_factory import create_vector_database


async def main() -> None:
    """Demonstrate simplified document ingestion."""
    print("=" * 70)
    print("Document Ingestion Enhancement Example")
    print("=" * 70)

    # Create a vector database (using Weaviate for this example)
    print("\n1. Creating vector database...")
    try:
        db = create_vector_database("weaviate", "DocumentExample")
        print(f"✓ Created {db.db_type} database")
    except Exception as e:
        print(f"✗ Failed to create database: {e}")
        print("\nNote: This example requires Weaviate to be running.")
        print("See README.md for setup instructions.")
        return

    # Set up the database with chunking configuration
    print("\n2. Setting up database with chunking...")
    try:
        await db.setup(
            embedding="default",
            chunking_config={
                "strategy": "Sentence",
                "parameters": {"chunk_size": 512, "overlap": 24},
            },
        )
        print("✓ Database setup complete")
    except Exception as e:
        print(f"✗ Setup failed: {e}")
        return

    # Example documents - mix of URLs and direct content
    print("\n3. Preparing documents...")
    documents = [
        # Web URL - HTML (will be auto-converted to markdown)
        {
            "url": "https://example.com",
            "metadata": {"source": "web", "type": "html"},
        },
        # Local markdown file (if it exists)
        {
            "url": "file://README.md",
            "metadata": {"source": "local", "type": "markdown"},
        },
        # Direct content (backwards compatible - no fetching needed)
        {
            "url": "manual-entry-1",
            "text": "This is directly provided content about machine learning and AI.",
            "metadata": {"source": "manual", "topic": "AI"},
        },
        # Another direct content example
        {
            "url": "manual-entry-2",
            "text": "This document discusses vector databases and semantic search.",
            "metadata": {"source": "manual", "topic": "databases"},
        },
    ]

    print(f"✓ Prepared {len(documents)} documents")
    print("\nDocument types:")
    for doc in documents:
        url = doc["url"]
        has_text = "text" in doc
        print(f"  - {url}: {'Direct text' if has_text else 'Will fetch and convert'}")

    # Write documents (system handles fetching and conversion automatically)
    print("\n4. Writing documents to database...")
    try:
        result = await db.write_documents(documents, embedding="default")
        print(f"✓ Successfully wrote documents")
        print(f"  Stats: {result}")
    except Exception as e:
        print(f"✗ Failed to write documents: {e}")
        print(f"  Error details: {type(e).__name__}")
        # Continue anyway to show other features

    # Query the documents
    print("\n5. Querying documents...")
    try:
        results = await db.search("machine learning", limit=3)
        print(f"✓ Found {len(results)} results for 'machine learning'")
        for i, result in enumerate(results, 1):
            url = result.get("url", "unknown")
            text_preview = result.get("text", "")[:100]
            print(f"\n  Result {i}:")
            print(f"    URL: {url}")
            print(f"    Text: {text_preview}...")
    except Exception as e:
        print(f"✗ Query failed: {e}")

    # List documents
    print("\n6. Listing documents...")
    try:
        docs = await db.list_documents(limit=10)
        print(f"✓ Found {len(docs)} documents in database")
        for doc in docs:
            url = doc.get("url", "unknown")
            metadata = doc.get("metadata", {})
            print(f"  - {url} (metadata: {metadata})")
    except Exception as e:
        print(f"✗ Failed to list documents: {e}")

    # Clean up
    print("\n7. Cleaning up...")
    try:
        await db.cleanup()
        print("✓ Cleanup complete")
    except Exception as e:
        print(f"✗ Cleanup failed: {e}")

    print("\n" + "=" * 70)
    print("Example completed!")
    print("=" * 70)

    print("\nKey Features Demonstrated:")
    print("  ✓ Automatic URL fetching (HTTP/HTTPS and file://)")
    print("  ✓ Automatic content type detection")
    print("  ✓ Automatic format conversion (HTML, PDF, Markdown, Text)")
    print("  ✓ Backwards compatible (direct text still works)")
    print("  ✓ Simplified API (no manual fetching/conversion needed)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback

        traceback.print_exc()

# Made with Bob
