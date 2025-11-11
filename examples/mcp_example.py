#!/usr/bin/env python3
# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""
Example demonstrating how to use the Maestro Vector Database MCP server.
This example shows how an AI agent might interact with the vector database with flexible embedding strategies.
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db.vector_db_factory import create_vector_database
from src.maestro_mcp.server import create_mcp_server


def demonstrate_mcp_server() -> None:
    """Demonstrate the MCP server functionality with the new 3-step workflow."""
    print("Maestro Vector Database MCP Server Example")
    print("=" * 50)

    # Create the MCP server
    print("\n1. Creating MCP server...")
    server = create_mcp_server()
    print(f"✓ Server created: {server.name}")

    # Show what tools are available
    print("\n2. Available tools in the MCP server:")
    expected_tools = [
        "register_database",  # Step 1: Register database instance
        "setup_database",  # Step 2: Initialize connection
        "create_collection",  # Step 3: Create collections
        "get_supported_embeddings",
        "write_documents",
        "write_document",
        "list_documents",
        "count_documents",
        "delete_documents",
        "delete_document",
        "delete_collection",
        "cleanup",
        "get_database_info",
    ]

    for tool in expected_tools:
        print(f"   - {tool}")

    print(f"\n✓ Total tools available: {len(expected_tools)}")

    # Demonstrate the 3-step workflow
    print("\n3. Typical workflow for setting up a vector database:")
    print("   Step 1: register_database() - Register database instance")
    print("   Step 2: setup_database() - Initialize connection")
    print("   Step 3: create_collection() - Create collections")
    print("   Then: Use write_documents(), query(), search(), etc.")

    # Demonstrate direct vector database usage (what the MCP server does internally)
    print("\n3. Demonstrating vector database operations with embedding strategies:")

    try:
        # Create a vector database
        print("\n   Creating Weaviate vector database...")
        db = create_vector_database("weaviate", "ExampleDocs")
        print(f"   ✓ Created {db.db_type} database with collection 'ExampleDocs'")

        # Show supported embeddings
        print("\n   Getting supported embeddings...")
        embeddings = db.supported_embeddings()
        print(f"   ✓ Supported embeddings: {embeddings}")

        # Set up the database with default embedding
        print("\n   Setting up database with default embedding...")
        db.setup(embedding="default")
        print("   ✓ Database setup complete with default embedding")

        # Write some documents with default embedding
        documents = [
            {
                "url": "https://example.com/doc1",
                "text": "This is the first document about machine learning.",
                "metadata": {"topic": "ML", "author": "Alice"},
            },
            {
                "url": "https://example.com/doc2",
                "text": "This is the second document about data science.",
                "metadata": {"topic": "Data Science", "author": "Bob"},
            },
            {
                "url": "https://example.com/doc3",
                "text": "This is the third document about artificial intelligence.",
                "metadata": {"topic": "AI", "author": "Charlie"},
            },
        ]

        print("\n   Writing documents with default embedding...")
        for doc in documents:
            db.write_document(doc, embedding="default")
            print(f"   ✓ Wrote document: {doc['url']}")

        # Demonstrate Milvus with pre-computed vectors
        print("\n4. Demonstrating Milvus with pre-computed vectors:")
        try:
            milvus_db = create_vector_database("milvus", "MilvusExampleDocs")
            print(f"   ✓ Created {milvus_db.db_type} database")

            # Show Milvus supported embeddings
            milvus_embeddings = milvus_db.supported_embeddings()
            print(f"   ✓ Milvus supported embeddings: {milvus_embeddings}")

            # Write document with pre-computed vector
            doc_with_vector = {
                "url": "https://example.com/milvus-doc",
                "text": "This document has a pre-computed vector embedding.",
                "metadata": {"topic": "Vector Databases", "author": "David"},
                "vector": [0.1] * 1536,  # 1536-dimensional vector
            }

            milvus_db.write_document(doc_with_vector, embedding="default")
            print("   ✓ Wrote document with pre-computed vector")

            # Clean up Milvus
            milvus_db.cleanup()
            print("   ✓ Milvus cleanup complete")

        except Exception as e:
            print(f"   ⚠️  Milvus demonstration skipped: {e}")

        # Demonstrate different embedding models (if OpenAI API key is available)
        print("\n5. Demonstrating different embedding models:")
        import os

        if os.getenv("OPENAI_API_KEY"):
            try:
                # Create a new collection with OpenAI embedding
                openai_db = create_vector_database("weaviate", "OpenAIExampleDocs")
                openai_db.setup(embedding="text-embedding-ada-002")
                print("   ✓ Created database with OpenAI embedding")

                # Write document with OpenAI embedding
                openai_doc = {
                    "url": "https://example.com/openai-doc",
                    "text": "This document uses OpenAI's text-embedding-ada-002 model.",
                    "metadata": {"topic": "OpenAI", "author": "Eve"},
                }

                openai_db.write_document(openai_doc, embedding="text-embedding-ada-002")
                print("   ✓ Wrote document with OpenAI embedding")

                # Clean up OpenAI collection
                openai_db.delete_collection()
                openai_db.cleanup()
                print("   ✓ OpenAI collection cleanup complete")

            except Exception as e:
                print(f"   ⚠️  OpenAI embedding demonstration failed: {e}")
        else:
            print(
                "   ⚠️  OpenAI API key not set, skipping OpenAI embedding demonstration"
            )

        # Get database info
        print("\n   Getting database info...")
        count = db.count_documents()
        print(f"   ✓ Document count: {count}")

        # List documents
        print("\n   Listing documents...")
        docs = db.list_documents(limit=5)
        print(f"   ✓ Found {len(docs)} documents")
        for doc in docs:
            print(
                f"      - {doc.get('url', 'No URL')}: {doc.get('text', 'No text')[:50]}..."
            )

        # Clean up
        print("\n   Cleaning up...")
        db.cleanup()
        print("   ✓ Cleanup complete")

    except Exception as e:
        print(f"   ✗ Error during database operations: {e}")
        print("   Note: This is expected if Weaviate/Milvus is not running")

    print("\n" + "=" * 50)
    print("Example completed!")
    print("\nTo use this MCP server with an AI agent:")
    print("1. Start the server: ./start.sh")
    print("2. Configure your MCP client with the server")
    print("3. Use the tools listed above to interact with vector databases")
    print("4. Try different embedding strategies:")
    print("   - Use 'default' for database's default embedding")
    print("   - Use 'text-embedding-ada-002' for OpenAI embeddings (requires API key)")
    print("   - Use pre-computed vectors with Milvus")
    print("5. Stop the server: ./stop.sh")


def main() -> None:
    """Main entry point."""
    try:
        demonstrate_mcp_server()
    except Exception as e:
        print(f"Error running example: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
