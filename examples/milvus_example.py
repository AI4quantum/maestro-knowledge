#!/usr/bin/env python3
"""
Example usage of maestro-knowledge with Milvus vector database.

This example demonstrates:
1. Setting up environment variables
2. Creating a vector database instance
3. Writing documents with different embedding strategies
4. Listing and querying documents
5. Cleanup
"""

import json
import os
from typing import Any

# Set environment variables for Milvus (optional - these are the defaults)
os.environ.setdefault("VECTOR_DB_TYPE", "milvus")
os.environ.setdefault("MILVUS_URI", "http://localhost:19530")

# Add the project root to the Python path
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the factory function
from src.db.vector_db_factory import create_vector_database


def create_sample_documents_with_vectors() -> list[dict[str, Any]]:
    """Create sample documents with pre-computed vector embeddings."""
    return [
        {
            "url": "https://example.com/doc1",
            "text": "Machine learning is a subset of artificial intelligence that focuses on algorithms and statistical models.",
            "metadata": {
                "type": "article",
                "author": "Dr. Smith",
                "category": "AI/ML",
                "tags": ["machine learning", "artificial intelligence", "algorithms"],
            },
            "vector": [0.1] * 1536,  # 1536-dimensional vector (example)
        },
        {
            "url": "https://example.com/doc2",
            "text": "Vector databases are specialized databases designed to store and query high-dimensional vector data efficiently.",
            "metadata": {
                "type": "tutorial",
                "author": "Jane Doe",
                "category": "Database",
                "tags": ["vector database", "similarity search", "embeddings"],
            },
            "vector": [0.2] * 1536,  # 1536-dimensional vector (example)
        },
        {
            "url": "https://example.com/doc3",
            "text": "Milvus is an open-source vector database that provides high-performance similarity search and analytics.",
            "metadata": {
                "type": "documentation",
                "author": "Milvus Team",
                "category": "Database",
                "tags": [
                    "milvus",
                    "vector database",
                    "open source",
                    "similarity search",
                ],
            },
            "vector": [0.3] * 1536,  # 1536-dimensional vector (example)
        },
    ]


def create_sample_documents_without_vectors() -> list[dict[str, Any]]:
    """Create sample documents without pre-computed vectors (will use embedding models)."""
    return [
        {
            "url": "https://example.com/doc4",
            "text": "Deep learning models have revolutionized natural language processing tasks.",
            "metadata": {
                "type": "research",
                "author": "Dr. Johnson",
                "category": "AI/ML",
                "tags": ["deep learning", "NLP", "neural networks"],
            },
        },
        {
            "url": "https://example.com/doc5",
            "text": "Semantic search enables finding documents based on meaning rather than exact keyword matches.",
            "metadata": {
                "type": "tutorial",
                "author": "Dr. Brown",
                "category": "Search",
                "tags": ["semantic search", "information retrieval", "AI"],
            },
        },
    ]


def main() -> None:
    """Main example function."""
    print("🚀 Maestro Knowledge - Milvus Vector Database Example")
    print("=" * 60)

    try:
        # Create a vector database instance
        print("\n1. Creating vector database instance...")
        db = create_vector_database("milvus", "ExampleCollection")
        print(f"✅ Created {db.db_type} database with collection: {db.collection_name}")

        # Display supported embeddings
        print(f"\n2. Supported embeddings: {db.supported_embeddings()}")

        # Set up the collection
        print("\n3. Setting up collection...")
        db.setup()
        print("✅ Collection setup complete")

        # Example 1: Write documents with pre-computed vectors
        print("\n4. Writing documents with pre-computed vectors...")
        documents_with_vectors = create_sample_documents_with_vectors()
        db.write_documents(documents_with_vectors, embedding="default")
        print(
            f"✅ Wrote {len(documents_with_vectors)} documents with pre-computed vectors"
        )

        # Example 2: Write documents using embedding model (requires OpenAI API key)
        print("\n5. Writing documents using embedding model...")
        documents_without_vectors = create_sample_documents_without_vectors()

        # Check if OpenAI API key is available
        if os.getenv("OPENAI_API_KEY"):
            try:
                db.write_documents(
                    documents_without_vectors, embedding="text-embedding-ada-002"
                )
                print(
                    f"✅ Wrote {len(documents_without_vectors)} documents using text-embedding-ada-002"
                )
            except Exception as e:
                print(f"⚠️  Failed to write documents with embedding model: {e}")
                print("   This is expected if OpenAI API is not configured properly")
        else:
            print("⚠️  OPENAI_API_KEY not set, skipping embedding model example")
            print("   Set OPENAI_API_KEY to test embedding model functionality")

        # List documents from the database
        print("\n6. Listing documents from database...")
        retrieved_docs = db.list_documents(limit=10)
        print(f"✅ Retrieved {len(retrieved_docs)} documents:")

        for i, doc in enumerate(retrieved_docs, 1):
            print(f"\n   Document {i}:")
            print(f"   - ID: {doc.get('id', 'N/A')}")
            print(f"   - URL: {doc.get('url', 'N/A')}")
            print(f"   - Text: {doc.get('text', 'N/A')[:100]}...")
            print(f"   - Metadata: {json.dumps(doc.get('metadata', {}), indent=6)}")

        # Demonstrate document count
        print("\n7. Document count:")
        count = db.count_documents()
        print(f"   - Total documents in collection: {count}")

        # Demonstrate document deletion
        print("\n8. Demonstrating document deletion:")
        if retrieved_docs:
            first_doc_id = retrieved_docs[0].get("id")
            print(f"   - Deleting document with ID: {first_doc_id}")
            db.delete_document(str(first_doc_id))

            # Check count after deletion
            new_count = db.count_documents()
            print(f"   - Documents after deletion: {new_count}")

        # Demonstrate different embedding models
        print("\n9. Embedding model examples:")
        print(
            "   - 'default': Uses pre-computed vectors if available, otherwise text-embedding-ada-002"
        )
        print("   - 'text-embedding-ada-002': OpenAI's Ada-002 embedding model")
        print("   - 'text-embedding-3-small': OpenAI's text-embedding-3-small model")
        print("   - 'text-embedding-3-large': OpenAI's text-embedding-3-large model")

        # Demonstrate environment variable usage
        print("\n10. Environment variable configuration:")
        print(f"   - VECTOR_DB_TYPE: {os.environ.get('VECTOR_DB_TYPE', 'not set')}")
        print(f"   - MILVUS_URI: {os.environ.get('MILVUS_URI', 'not set')}")
        print(
            f"   - OPENAI_API_KEY: {'set' if os.getenv('OPENAI_API_KEY') else 'not set'}"
        )

        print("\n✅ Example completed successfully!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Make sure you have:")
        print("   - Milvus server running (or use cloud instance)")
        print("   - pymilvus package installed: pip install pymilvus")
        print("   - Proper environment variables set")
        print("   - For embedding models: OpenAI API key set (OPENAI_API_KEY)")

    finally:
        # Clean up resources
        print("\n11. Cleaning up...")
        try:
            db.cleanup()
            print("✅ Cleanup completed")
        except Exception:
            print("⚠️  Cleanup failed (this is normal if db wasn't initialized)")


if __name__ == "__main__":
    main()
