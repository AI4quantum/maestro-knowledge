# SPDX-License-Identifier: MIT
# Copyright (c) 2025 dr.max

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from ..db.vector_db_factory import create_vector_database
from ..db.vector_db_base import VectorDatabase

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dictionary to store vector database instances keyed by name
vector_databases: Dict[str, VectorDatabase] = {}


def get_database_by_name(db_name: str) -> VectorDatabase:
    """Get a vector database instance by name."""
    if db_name not in vector_databases:
        raise ValueError(
            f"Vector database '{db_name}' not found. Please create it first."
        )
    return vector_databases[db_name]


# Pydantic models for tool inputs
class CreateVectorDatabaseInput(BaseModel):
    db_name: str = Field(
        ..., description="Unique name for the vector database instance"
    )
    db_type: str = Field(
        ...,
        description="Type of vector database to create",
        json_schema_extra={"enum": ["weaviate", "milvus"]},
    )
    collection_name: str = Field(
        default="MaestroDocs", description="Name of the collection to use"
    )
    dimension: int = Field(
        default=None,
        description="The vector dimension for the collection. If None, it will be inferred from the embedding model.",
    )


class SetupDatabaseInput(BaseModel):
    db_name: str = Field(
        ..., description="Name of the vector database instance to set up"
    )
    embedding: str = Field(
        default="default", description="Embedding model to use for the collection"
    )


class GetSupportedEmbeddingsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")


class WriteDocumentsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    documents: List[Dict[str, Any]] = Field(
        ..., description="List of documents to write"
    )
    embedding: str = Field(default="default", description="Embedding strategy to use")


class WriteDocumentInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    url: str = Field(..., description="URL of the document")
    text: str = Field(..., description="Text content of the document")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the document"
    )
    vector: List[float] = Field(
        default=None, description="Pre-computed vector embedding (optional, for Milvus)"
    )
    embedding: str = Field(default="default", description="Embedding strategy to use")


class WriteDocumentToCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(..., description="Name of the collection to write to")
    doc_name: str = Field(..., description="Name of the document")
    text: str = Field(..., description="Text content of the document")
    url: str = Field(..., description="URL of the document")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the document"
    )
    vector: List[float] = Field(
        default=None, description="Pre-computed vector embedding (optional, for Milvus)"
    )
    embedding: str = Field(default="default", description="Embedding strategy to use")


class ListDocumentsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    limit: int = Field(default=10, description="Maximum number of documents to return")
    offset: int = Field(default=0, description="Number of documents to skip")


class ListDocumentsInCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(
        ..., description="Name of the collection to list documents from"
    )
    limit: int = Field(default=10, description="Maximum number of documents to return")
    offset: int = Field(default=0, description="Number of documents to skip")


class CountDocumentsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")


class DeleteDocumentsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    document_ids: List[str] = Field(..., description="List of document IDs to delete")


class DeleteDocumentInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    document_id: str = Field(..., description="Document ID to delete")


class DeleteDocumentFromCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(
        ..., description="Name of the collection containing the document"
    )
    doc_name: str = Field(..., description="Name of the document to delete")


class GetDocumentInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(
        ..., description="Name of the collection containing the document"
    )
    doc_name: str = Field(..., description="Name of the document to retrieve")


class DeleteCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(
        default=None, description="Name of the collection to delete"
    )


class CleanupInput(BaseModel):
    db_name: str = Field(
        ..., description="Name of the vector database instance to clean up"
    )


class GetDatabaseInfoInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")


class ListCollectionsInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")


class GetCollectionInfoInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(
        default=None,
        description="Name of the collection to get info for. If not provided, uses the default collection.",
    )


class CreateCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(..., description="Name of the collection to create")
    embedding: str = Field(
        default="default", description="Embedding model to use for the collection"
    )


def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server with vector database tools."""

    # Create FastMCP server directly
    app = FastMCP("maestro-vector-db")

    @app.tool()
    async def create_vector_database_tool(input: CreateVectorDatabaseInput) -> str:
        """Create a new vector database instance."""
        try:
            logger.info(
                f"Creating vector database: {input.db_name} of type {input.db_type}"
            )
            logger.info(
                f"Current vector_databases keys: {list(vector_databases.keys())}"
            )

            # Check if database with this name already exists
            if input.db_name in vector_databases:
                error_msg = f"Vector database '{input.db_name}' already exists"
                logger.error(error_msg)
                return f"Error: {error_msg}"

            # Create new database instance
            vector_databases[input.db_name] = create_vector_database(
                input.db_type, input.collection_name, input.dimension
            )

            logger.info(
                f"Created database. Updated vector_databases keys: {list(vector_databases.keys())}"
            )

            return f"Successfully created {input.db_type} vector database '{input.db_name}' with collection '{input.collection_name}'"
        except Exception as e:
            error_msg = f"Failed to create vector database '{input.db_name}': {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    @app.tool()
    async def setup_database(input: SetupDatabaseInput) -> str:
        """Set up a vector database and create collections."""
        try:
            db = get_database_by_name(input.db_name)

            # Check if the database supports the setup method with embedding parameter
            if hasattr(db, "setup") and len(db.setup.__code__.co_varnames) > 1:
                db.setup(embedding=input.embedding)
            else:
                db.setup()

            return f"Successfully set up {db.db_type} vector database '{input.db_name}' with embedding '{input.embedding}'"
        except Exception as e:
            error_msg = f"Failed to set up vector database '{input.db_name}': {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    @app.tool()
    async def get_supported_embeddings(input: GetSupportedEmbeddingsInput) -> str:
        """Get list of supported embedding models for a vector database."""
        db = get_database_by_name(input.db_name)
        embeddings = db.supported_embeddings()

        return f"Supported embeddings for {db.db_type} vector database '{input.db_name}': {json.dumps(embeddings, indent=2)}"

    @app.tool()
    async def write_documents(input: WriteDocumentsInput) -> str:
        """Write documents to a vector database with specified embedding strategy."""
        db = get_database_by_name(input.db_name)
        db.write_documents(input.documents, embedding=input.embedding)

        return f"Successfully wrote {len(input.documents)} documents to vector database '{input.db_name}' using embedding '{input.embedding}'"

    @app.tool()
    async def write_document(input: WriteDocumentInput) -> str:
        """Write a single document to a vector database with specified embedding strategy."""
        db = get_database_by_name(input.db_name)
        document = {
            "url": input.url,
            "text": input.text,
            "metadata": input.metadata,
        }

        # Add vector if provided (for Milvus)
        if input.vector is not None:
            document["vector"] = input.vector

        db.write_document(document, embedding=input.embedding)

        return f"Successfully wrote document '{input.url}' to vector database '{input.db_name}' using embedding '{input.embedding}'"

    @app.tool()
    async def write_document_to_collection(
        input: WriteDocumentToCollectionInput,
    ) -> str:
        """Write a single document to a specific collection in a vector database with specified embedding strategy."""
        db = get_database_by_name(input.db_name)

        # Check if the collection exists
        collections = db.list_collections()
        normalized_input = input.collection_name.strip().lower()
        normalized_collections = [str(c).strip().lower() for c in collections]
        if normalized_input not in normalized_collections:
            raise ValueError(
                f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
            )

        # Create document with collection-specific metadata
        document = {
            "url": input.url,
            "text": input.text,
            "metadata": {
                **input.metadata,
                "collection_name": input.collection_name,
                "doc_name": input.doc_name,
            },
        }

        # Add vector if provided (for Milvus)
        if input.vector is not None:
            document["vector"] = input.vector

        # For now, we'll use the default collection behavior
        # TODO: Implement collection-specific document writing in the vector database classes
        db.write_document(document, embedding=input.embedding)

        return f"Successfully wrote document '{input.doc_name}' to collection '{input.collection_name}' in vector database '{input.db_name}' using embedding '{input.embedding}'"

    @app.tool()
    async def list_documents(input: ListDocumentsInput) -> str:
        """List documents from a vector database."""
        db = get_database_by_name(input.db_name)
        documents = db.list_documents(input.limit, input.offset)

        return f"Found {len(documents)} documents in vector database '{input.db_name}':\n{json.dumps(documents, indent=2, default=str)}"

    @app.tool()
    async def list_documents_in_collection(
        input: ListDocumentsInCollectionInput,
    ) -> str:
        """List documents from a specific collection in a vector database."""
        db = get_database_by_name(input.db_name)

        # Check if the collection exists
        collections = db.list_collections()
        print(
            f"[DEBUG] input.collection_name: {repr(input.collection_name)} (type: {type(input.collection_name)})"
        )
        for c in collections:
            print(f"[DEBUG] collection in list: {repr(c)} (type: {type(c)})")
        # Normalize both sides for comparison
        normalized_input = input.collection_name.strip().lower()
        normalized_collections = [str(c).strip().lower() for c in collections]
        if normalized_input not in normalized_collections:
            print(
                f"[DEBUG] Raising ValueError: Collection '{input.collection_name}' not found in vector database '{input.db_name}' (normalized check)"
            )
            raise ValueError(
                f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
            )

        # Use the new list_documents_in_collection method
        documents = db.list_documents_in_collection(
            input.collection_name, input.limit, input.offset
        )
        return f"Found {len(documents)} documents in collection '{input.collection_name}' of vector database '{input.db_name}':\n{json.dumps(documents, indent=2, default=str)}"

    @app.tool()
    async def count_documents(input: CountDocumentsInput) -> str:
        """Get the current count of documents in a collection."""
        db = get_database_by_name(input.db_name)
        count = db.count_documents()

        return f"Document count in vector database '{input.db_name}': {count}"

    @app.tool()
    async def delete_documents(input: DeleteDocumentsInput) -> str:
        """Delete documents from a vector database by their IDs."""
        db = get_database_by_name(input.db_name)
        db.delete_documents(input.document_ids)

        return f"Successfully deleted {len(input.document_ids)} documents from vector database '{input.db_name}'"

    @app.tool()
    async def delete_document(input: DeleteDocumentInput) -> str:
        """Delete a single document from a vector database."""
        db = get_database_by_name(input.db_name)
        db.delete_document(input.document_id)

        return f"Successfully deleted document '{input.document_id}' from vector database '{input.db_name}'"

    @app.tool()
    async def delete_document_from_collection(
        input: DeleteDocumentFromCollectionInput,
    ) -> str:
        """Delete a document from a specific collection in a vector database by document name."""
        db = get_database_by_name(input.db_name)

        # Check if the collection exists
        collections = db.list_collections()
        if input.collection_name not in collections:
            raise ValueError(
                f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
            )

        # Temporarily switch to the target collection
        original_collection = db.collection_name
        db.collection_name = input.collection_name

        try:
            # List documents to find the one with the matching name
            documents = db.list_documents(
                limit=1000, offset=0
            )  # Get all documents to search by name
            document_id = None

            for doc in documents:
                if (
                    doc.get("name") == input.doc_name
                    or doc.get("doc_name") == input.doc_name
                ):
                    document_id = doc.get("id")
                    break

            if document_id is None:
                raise ValueError(
                    f"Document '{input.doc_name}' not found in collection '{input.collection_name}' of vector database '{input.db_name}'"
                )

            # Delete the document
            db.delete_document(document_id)

            return f"Successfully deleted document '{input.doc_name}' from collection '{input.collection_name}' in vector database '{input.db_name}'"
        finally:
            # Restore original collection
            db.collection_name = original_collection

    @app.tool()
    async def get_document(input: GetDocumentInput) -> str:
        """Get a specific document by name from a collection in a vector database."""
        db = get_database_by_name(input.db_name)

        # Check if the collection exists
        collections = db.list_collections()
        if input.collection_name not in collections:
            raise ValueError(
                f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
            )

        try:
            # Get the document using the new get_document method
            document = db.get_document(input.doc_name, input.collection_name)
            return f"Document '{input.doc_name}' from collection '{input.collection_name}' in vector database '{input.db_name}':\n{json.dumps(document, indent=2, default=str)}"
        except ValueError as e:
            # Re-raise ValueError as is (these are user-friendly error messages)
            raise e
        except Exception as e:
            raise ValueError(f"Failed to retrieve document '{input.doc_name}': {e}")

    @app.tool()
    async def delete_collection(input: DeleteCollectionInput) -> str:
        """Delete an entire collection from a vector database."""
        if input.db_name in vector_databases:
            db = get_database_by_name(input.db_name)

            # Check if the collection exists
            collections = db.list_collections()
            # Normalize both sides for comparison

            normalized_input = input.collection_name.strip().lower()
            normalized_collections = [str(c).strip().lower() for c in collections]
            if normalized_input not in normalized_collections:
                raise ValueError(
                    f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
                )

            db.delete_collection(input.collection_name)

            return f"Successfully deleted collection '{input.collection_name}' from vector database '{input.db_name}'"
        try:
            from ..db.vector_db_milvus import MilvusVectorDatabase

            temp_db = MilvusVectorDatabase(collection_name=input.collection_name)
            temp_db.delete_collection(input.collection_name)
            return f"Successfully dropped collection '{input.collection_name}' from Milvus (untracked)."
        except Exception as e:
            return f"Delete collection failed: {str(e)}"

    @app.tool()
    async def cleanup(input: CleanupInput) -> str:
        """Clean up resources and close connections for a vector database."""
        if input.db_name in vector_databases:
            db = get_database_by_name(input.db_name)
            db.cleanup()
            del vector_databases[input.db_name]
            return (
                f"Successfully cleaned up and removed vector database '{input.db_name}'"
            )
        try:
            from ..db.vector_db_milvus import MilvusVectorDatabase

            temp_db = MilvusVectorDatabase(collection_name=input.db_name)
            temp_db.delete_collection(input.db_name)
            return f"Successfully dropped collection '{input.db_name}' from Milvus (untracked)."
        except Exception as e:
            return f"Cleanup failed: {str(e)}"

    @app.tool()
    async def get_database_info(input: GetDatabaseInfoInput) -> str:
        """Get information about a vector database."""
        db = get_database_by_name(input.db_name)
        info = {
            "name": input.db_name,
            "type": db.db_type,
            "collection": db.collection_name,
            "document_count": db.count_documents(),
        }

        return (
            f"Database information for '{input.db_name}':\n{json.dumps(info, indent=2)}"
        )

    @app.tool()
    async def list_collections(input: ListCollectionsInput) -> str:
        """List all collections in a vector database."""
        db = get_database_by_name(input.db_name)
        collections = db.list_collections()

        if not collections:
            return f"No collections found in vector database '{input.db_name}'"

        return f"Collections in vector database '{input.db_name}':\n{json.dumps(collections, indent=2)}"

    @app.tool()
    async def get_collection_info(input: GetCollectionInfoInput) -> str:
        """Get information about a specific collection in a vector database."""
        db = get_database_by_name(input.db_name)

        # Check if the collection exists
        collections = db.list_collections()
        if input.collection_name not in collections:
            raise ValueError(
                f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
            )

        # Get collection information using the new method
        info = db.get_collection_info(input.collection_name)

        return f"Collection information for '{info['name']}' in vector database '{input.db_name}':\n{json.dumps(info, indent=2)}"

    @app.tool()
    async def create_collection(input: CreateCollectionInput) -> str:
        """Create a new collection in a vector database."""
        try:
            db = get_database_by_name(input.db_name)

            # Check if collection already exists
            existing_collections = db.list_collections()
            if input.collection_name in existing_collections:
                return f"Error: Collection '{input.collection_name}' already exists in vector database '{input.db_name}'"

            # Temporarily switch to the new collection name
            original_collection = db.collection_name
            db.collection_name = input.collection_name

            try:
                # Create the collection using the setup method
                if hasattr(db, "setup") and len(db.setup.__code__.co_varnames) > 1:
                    db.setup(embedding=input.embedding)
                else:
                    db.setup()

                return f"Successfully created collection '{input.collection_name}' in vector database '{input.db_name}' with embedding '{input.embedding}'"
            finally:
                # Restore the original collection name
                db.collection_name = original_collection

        except Exception as e:
            error_msg = f"Failed to create collection '{input.collection_name}' in vector database '{input.db_name}': {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    @app.tool()
    async def list_databases() -> str:
        """List all available vector database instances."""
        logger.info(
            f"Listing databases. Current vector_databases keys: {list(vector_databases.keys())}"
        )

        if not vector_databases:
            return "No vector databases are currently active"

        db_list = []
        for db_name, db in vector_databases.items():
            db_list.append(
                {
                    "name": db_name,
                    "type": db.db_type,
                    "collection": db.collection_name,
                    "document_count": db.count_documents(),
                }
            )

        logger.info(f"Returning {len(db_list)} databases")
        return f"Available vector databases:\n{json.dumps(db_list, indent=2)}"

    return app


async def main():
    """Main entry point for the MCP server."""
    app = create_mcp_server()
    await app.run()


async def run_http_server(host: str = "localhost", port: int = 8030):
    """Run the MCP server with HTTP interface."""
    # Create the MCP server
    mcp_app = create_mcp_server()

    print(f"Starting FastMCP HTTP server on http://{host}:{port}")
    print(f"Open your browser to http://{host}:{port} to access the MCP server")
    print(f"📖 OpenAPI docs: http://{host}:{port}/docs")
    print(f"📚 ReDoc docs: http://{host}:{port}/redoc")

    import os

    custom_url = os.getenv("CUSTOM_EMBEDDING_URL")
    if custom_url:
        custom_model = os.getenv("CUSTOM_EMBEDDING_MODEL", "nomic-embed-text")
        print("🧬 Custom Embedding Endpoint is configured:")
        print(f"   - URL:    {custom_url}")
        print(f"   - Model:  {custom_model}")
    else:
        print("🧬 Using default OpenAI embedding configuration.")

    # Run the MCP server directly
    await mcp_app.run_http_async(host=host, port=port)


def run_server():
    """Entry point for running the server."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error running server: {e}")
        sys.exit(1)


def run_http_server_sync(host: str = "localhost", port: int = 8030):
    """Synchronous entry point for running the HTTP server."""
    try:
        asyncio.run(run_http_server(host, port))
    except KeyboardInterrupt:
        print("\nHTTP server stopped by user")
    except Exception as e:
        print(f"Error running HTTP server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    run_server()
