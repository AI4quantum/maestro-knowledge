#!/usr/bin/env python3
"""
Weaviate Vector Database Example

This example demonstrates how to use the maestro-knowledge library with Weaviate.
It shows how to create a vector database, write documents with different embedding models, and list them.

Prerequisites:
- Weaviate cloud instance or local Weaviate server
- Environment variables: WEAVIATE_API_KEY and WEAVIATE_URL
- For OpenAI embeddings: OPENAI_API_KEY

Usage:
    python examples/weaviate_example.py
"""

import json
import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the factory function
from src.db.vector_db_factory import create_vector_database


def main() -> None:
    """Main function demonstrating Weaviate usage."""
    print("🚀 Weaviate Vector Database Example")
    print("=" * 50)

    # Check if required environment variables are set
    if not os.getenv("WEAVIATE_API_KEY"):
        print("❌ Error: WEAVIATE_API_KEY environment variable is not set")
        print("Please set it to your Weaviate API key")
        return

    if not os.getenv("WEAVIATE_URL"):
        print("❌ Error: WEAVIATE_URL environment variable is not set")
        print("Please set it to your Weaviate cluster URL")
        return

    try:
        # 1. Create a Weaviate vector database instance
        print("\n1. Creating Weaviate vector database...")
        db = create_vector_database("weaviate", "WeaviateExampleCollection")
        print("✅ Weaviate database instance created")

        # 2. Display supported embeddings
        print(f"\n2. Supported embeddings: {db.supported_embeddings()}")

        # 3. Set up the database with default embedding (creates collection if it doesn't exist)
        print("\n3. Setting up database with default embedding...")
        db.setup(embedding="default")
        print("✅ Database setup completed with default embedding")

        # 4. Prepare sample documents
        print("\n4. Preparing sample documents...")
        documents = [
            {
                "url": "https://example.com/doc1",
                "text": "This is the first document about artificial intelligence and machine learning.",
                "metadata": {
                    "title": "AI and ML Introduction",
                    "category": "technology",
                    "author": "Dr. Smith",
                },
            },
            {
                "url": "https://example.com/doc2",
                "text": "Vector databases are essential for modern AI applications and semantic search.",
                "metadata": {
                    "title": "Vector Databases Guide",
                    "category": "technology",
                    "author": "Dr. Johnson",
                },
            },
            {
                "url": "https://example.com/doc3",
                "text": "Weaviate is a powerful vector database that supports semantic search and AI applications.",
                "metadata": {
                    "title": "Weaviate Overview",
                    "category": "database",
                    "author": "Dr. Brown",
                },
            },
        ]
        print(f"✅ Prepared {len(documents)} sample documents")

        # 5. Write documents to the database with default embedding
        print("\n5. Writing documents to database with default embedding...")
        db.write_documents(documents, embedding="default")
        print("✅ Documents written successfully with default embedding")

        # 6. Demonstrate different embedding models
        print("\n6. Demonstrating different embedding models...")

        # Check if OpenAI API key is available for OpenAI embeddings
        if os.getenv("OPENAI_API_KEY"):
            print("   - Testing OpenAI embedding model...")
            try:
                # Create a new collection with OpenAI embedding
                db_openai = create_vector_database(
                    "weaviate", "WeaviateOpenAICollection"
                )
                db_openai.setup(embedding="text-embedding-ada-002")

                # Write a single document with OpenAI embedding
                test_doc = [
                    {
                        "url": "https://example.com/openai-test",
                        "text": "This document uses OpenAI's text-embedding-ada-002 model for vectorization.",
                        "metadata": {
                            "title": "OpenAI Embedding Test",
                            "category": "test",
                            "author": "Test Author",
                        },
                    }
                ]

                db_openai.write_documents(test_doc, embedding="text-embedding-ada-002")
                print("   ✅ Successfully wrote document using text-embedding-ada-002")

                # Clean up the test collection
                db_openai.delete_collection()
                db_openai.cleanup()

            except Exception as e:
                print(f"   ⚠️  Failed to test OpenAI embedding: {e}")
        else:
            print("   ⚠️  OPENAI_API_KEY not set, skipping OpenAI embedding test")
            print("   Set OPENAI_API_KEY to test OpenAI embedding models")

        # 7. List documents from the database
        print("\n7. Listing documents from database...")
        retrieved_docs = db.list_documents(limit=5, offset=0)
        print(f"✅ Retrieved {len(retrieved_docs)} documents:")

        for i, doc in enumerate(retrieved_docs, 1):
            print(f"\n   Document {i}:")
            print(f"   - ID: {doc.get('id', 'N/A')}")
            print(f"   - URL: {doc.get('url', 'N/A')}")
            print(f"   - Text: {doc.get('text', 'N/A')[:100]}...")
            if doc.get("metadata"):
                metadata = doc["metadata"]
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except json.JSONDecodeError:
                        pass
                print(f"   - Title: {metadata.get('title', 'N/A')}")
                print(f"   - Category: {metadata.get('category', 'N/A')}")

        # 8. Test database type property
        print(f"\n8. Database type: {db.db_type}")
        print("✅ Database type retrieved successfully")

        # 9. Demonstrate document count
        print("\n9. Document count:")
        count = db.count_documents()
        print(f"   - Total documents in collection: {count}")

        # 10. Demonstrate document deletion
        print("\n10. Demonstrating document deletion:")
        if retrieved_docs:
            first_doc_id = retrieved_docs[0].get("id")
            print(f"   - Deleting document with ID: {first_doc_id}")
            db.delete_document(first_doc_id)

            # Check count after deletion
            new_count = db.count_documents()
            print(f"   - Documents after deletion: {new_count}")

        # 11. Embedding model information
        print("\n11. Available embedding models:")
        print("   - 'default': Uses Weaviate's text2vec-weaviate vectorizer")
        print("   - 'text2vec-weaviate': Weaviate's built-in text vectorizer")
        print("   - 'text2vec-openai': OpenAI's embedding models (requires API key)")
        print("   - 'text2vec-cohere': Cohere's embedding models")
        print("   - 'text2vec-huggingface': Hugging Face models")
        print("   - 'text-embedding-ada-002': OpenAI's Ada-002 model")
        print("   - 'text-embedding-3-small': OpenAI's text-embedding-3-small model")
        print("   - 'text-embedding-3-large': OpenAI's text-embedding-3-large model")

        # 12. Environment variable information
        print("\n12. Environment variable configuration:")
        print(
            f"   - WEAVIATE_API_KEY: {'set' if os.getenv('WEAVIATE_API_KEY') else 'not set'}"
        )
        print(f"   - WEAVIATE_URL: {os.getenv('WEAVIATE_URL', 'not set')}")
        print(
            f"   - OPENAI_API_KEY: {'set' if os.getenv('OPENAI_API_KEY') else 'not set'}"
        )

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting tips:")
        print("- Make sure WEAVIATE_API_KEY and WEAVIATE_URL are set correctly")
        print("- Verify your Weaviate cluster is running and accessible")
        print("- Check that your API key has the necessary permissions")
        print("- For OpenAI embeddings: Set OPENAI_API_KEY environment variable")
        return

    finally:
        # Clean up resources
        print("\n13. Cleaning up...")
        try:
            db.cleanup()
            print("✅ Cleanup completed")
        except Exception:
            print("⚠️  Cleanup failed (this is normal if db wasn't initialized)")

    print("\n🎉 Weaviate example completed successfully!")


if __name__ == "__main__":
    main()
