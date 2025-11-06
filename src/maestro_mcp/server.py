# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import asyncio
import json
import logging
import os
import sys
from typing import Any, cast
from collections.abc import Awaitable, Callable

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from pydantic import BaseModel, Field

from src.chunking import ChunkingConfig
from src.db.vector_db_base import VectorDatabase
from src.db.vector_db_factory import create_vector_database


# Load environment variables from .env file
def load_env_file() -> None:
    """Load environment variables from .env file."""
    env_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
    )
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value


# Load environment variables
load_env_file()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dictionary to store vector database instances keyed by name
vector_databases: dict[str, VectorDatabase] = {}

# Default timeout (in seconds) for MCP tool execution. Can be overridden via env.
DEFAULT_TOOL_TIMEOUT = int(os.getenv("MCP_TOOL_TIMEOUT", "15"))

# Per-category timeout defaults (seconds).
# Override via environment variables MCP_TIMEOUT_<CATEGORY>, e.g., MCP_TIMEOUT_QUERY=45
TIMEOUT_DEFAULTS: dict[str, int] = {
    "health": 30,
    "list_databases": 15,
    "list_collections": 15,
    "list_documents": 30,
    "count_documents": 15,
    "get_database_info": 15,
    "get_collection_info": 30,
    "query": 30,
    "search": 30,
    "write_single": 900,  # 15 minutes
    "write_bulk": 3600,  # 60 minutes
    "delete": 60,
    "cleanup": 60,
    "create_collection": 60,
    "setup_database": 60,
    "resync": 60,
}


def get_timeout(category: str, fallback: int | None = None) -> int:
    """Resolve timeout for a category from env or defaults.

    Env var format: MCP_TIMEOUT_<CATEGORY>, e.g., MCP_TIMEOUT_QUERY=45
    """
    env_key = f"MCP_TIMEOUT_{category.upper()}"
    val = os.getenv(env_key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    if fallback is not None:
        return fallback
    return TIMEOUT_DEFAULTS.get(category, DEFAULT_TOOL_TIMEOUT)


def tool_timeout(
    seconds: int | None = None,
) -> Callable[[Callable[..., Awaitable[object]]], Callable[..., Awaitable[object]]]:
    """Decorator to enforce a timeout and guaranteed response for MCP tools.

    Ensures that every tool returns a response even if an operation hangs or raises.
    Timeout is configurable via MCP_TOOL_TIMEOUT env var or the decorator argument.
    """

    def decorator(
        func: Callable[..., Awaitable[object]],
    ) -> Callable[..., Awaitable[object]]:
        async def wrapper(*args: object, **kwargs: object) -> object:
            timeout_s = seconds if seconds is not None else DEFAULT_TOOL_TIMEOUT
            func_name = getattr(func, "__name__", "tool")

            # Create task explicitly to enable proper cancellation on timeout
            task = asyncio.create_task(func(*args, **kwargs))  # type: ignore[arg-type]
            try:
                return await asyncio.wait_for(task, timeout=timeout_s)
            except asyncio.TimeoutError:
                logger.error(
                    "Tool '%s' timed out after %s seconds", func_name, timeout_s
                )
                # Properly cancel the task to avoid resource leaks
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected when we cancel
                return f"Error: '{func_name}' timed out after {timeout_s} seconds"
            except Exception as e:
                # Catch any uncaught exceptions so we always return a response
                logger.exception("Tool '%s' failed: %s", func_name, e)
                return f"Error: {str(e)}"

        return wrapper

    return decorator


async def run_with_timeout(
    awaitable: Awaitable[Any], tool_name: str, timeout_s: int | None = None
) -> tuple[bool, Any]:
    """Run an awaitable with a timeout, return (ok, result_or_error_message).

    If the awaitable completes, returns (True, result). If it times out, returns
    (False, error_message). Any other exception is caught and returned as (False, error_message).
    """
    to = timeout_s if timeout_s is not None else DEFAULT_TOOL_TIMEOUT

    # Create task explicitly to enable proper cancellation on timeout
    # Use type: ignore to handle Awaitable -> Coroutine conversion
    task = asyncio.create_task(awaitable)  # type: ignore[arg-type]
    try:
        result = await asyncio.wait_for(task, timeout=to)
        return True, result
    except asyncio.TimeoutError:
        logger.error("Tool '%s' timed out after %s seconds", tool_name, to)
        # Properly cancel the task to avoid resource leaks
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected when we cancel
        return False, f"Error: '{tool_name}' timed out after {to} seconds"
    except Exception as e:
        logger.exception("Tool '%s' failed: %s", tool_name, e)
        return False, f"Error: {str(e)}"


async def resync_vector_databases() -> list[str]:
    """Discover Milvus collections and register them in memory.

    Returns a list of collection names that were registered.
    This is a best-effort helper to recover state after a server restart.
    """
    added = []
    try:
        # Allow tests to monkeypatch a MilvusVectorDatabase on this module.
        # If not provided, import the real implementation.
        import sys

        module = sys.modules[__name__]
        MilvusVectorDatabase = getattr(module, "MilvusVectorDatabase", None)
        if MilvusVectorDatabase is None:
            # Import here to avoid optional-dependency import at module load time
            from src.db.vector_db_milvus import MilvusVectorDatabase

        # Add timeout protection for the entire resync operation
        timeout_seconds = int(os.getenv("MILVUS_RESYNC_TIMEOUT", "15"))

        try:
            # Create a temporary Milvus handle to list collections with timeout
            temp = MilvusVectorDatabase()
            temp._ensure_client()
            if temp.client is None:
                logger.info(
                    "Milvus client not available during resync; skipping resync"
                )
                return added

            # List collections with timeout protection and proper task cleanup
            list_task = asyncio.create_task(temp.list_collections())
            try:
                collections = await asyncio.wait_for(list_task, timeout=timeout_seconds)
                collections = collections or []
            except asyncio.TimeoutError:
                logger.warning(
                    f"Milvus resync timed out after {timeout_seconds} seconds"
                )
                # Properly cancel the task to avoid orphaned futures
                list_task.cancel()
                try:
                    await list_task
                except asyncio.CancelledError:
                    pass  # Expected when we cancel
                return added
        except asyncio.TimeoutError:
            logger.warning(f"Milvus resync timed out after {timeout_seconds} seconds")
            return added
        except Exception as e:
            logger.warning(f"Failed to connect to Milvus during resync: {e}")
            return added
            logger.warning(f"Failed to list Milvus collections during resync: {e}")
            return added

        for coll in collections:
            if coll not in vector_databases:
                try:
                    db = MilvusVectorDatabase(collection_name=coll)
                    # Try to infer collection-level embedding config and set on the instance
                    try:
                        info = await db.get_collection_info(coll)
                        emb_details = info.get("embedding_details") or {}
                        # If the backend stored embedding config, prefer that
                        if emb_details.get("config"):
                            db.embedding_model = "custom_local"
                            # try to set dimension if available
                            try:
                                db.dimension = emb_details.get("vector_size")
                                db._collections_metadata[coll] = (
                                    db._collections_metadata.get(coll, {})
                                )
                                db._collections_metadata[coll]["vector_size"] = (
                                    db.dimension
                                )
                            except Exception:
                                pass
                        else:
                            # If environment config exists and vector size matches, assume custom_local
                            try:
                                env_url = os.getenv("CUSTOM_EMBEDDING_URL")
                                env_vs = os.getenv("CUSTOM_EMBEDDING_VECTORSIZE")
                                if env_url and env_vs:
                                    try:
                                        vs_int = int(env_vs)
                                        if (
                                            info.get("embedding_details", {}).get(
                                                "vector_size"
                                            )
                                            == vs_int
                                        ):
                                            db.embedding_model = "custom_local"
                                            db.dimension = vs_int
                                            db._collections_metadata[coll] = (
                                                db._collections_metadata.get(coll, {})
                                            )
                                            db._collections_metadata[coll][
                                                "vector_size"
                                            ] = db.dimension
                                    except Exception:
                                        pass
                            except Exception:
                                pass

                    except Exception:
                        # best-effort: ignore failures to query collection info
                        pass

                    vector_databases[coll] = db
                    added.append(coll)
                except Exception as e:
                    logger.warning(
                        f"Failed to register collection '{coll}' during resync: {e}"
                    )
    except Exception as e:
        logger.warning(f"Resync helper failed: {e}")

    if added:
        logger.info(f"Resynced and registered Milvus collections: {added}")
    return added


async def resync_weaviate_databases() -> list[str]:
    """Discover Weaviate collections and register them in memory.

    Returns a list of collection names that were registered.
    Best-effort: skips if Weaviate environment/config is not available.
    """
    added: list[str] = []
    try:
        import os

        # Check if Weaviate is properly configured before attempting connection
        weaviate_api_key = os.getenv("WEAVIATE_API_KEY")
        weaviate_url = os.getenv("WEAVIATE_URL")

        if not weaviate_api_key or not weaviate_url:
            logger.debug(
                "Weaviate not configured (missing WEAVIATE_API_KEY or WEAVIATE_URL), skipping resync"
            )
            return added

        # Import lazily to avoid mandatory dependency when Weaviate isn't used
        from src.db.vector_db_weaviate import WeaviateVectorDatabase

        # Add timeout protection for the entire resync operation
        timeout_seconds = int(os.getenv("WEAVIATE_RESYNC_TIMEOUT", "10"))

        # Attempt to create a temporary client with timeout protection
        temp = None
        try:
            # WeaviateVectorDatabase constructor is synchronous but may hang on client creation
            # Wrap it in an executor with timeout
            loop = asyncio.get_event_loop()
            executor_future = loop.run_in_executor(None, WeaviateVectorDatabase)
            try:
                temp = await asyncio.wait_for(executor_future, timeout=timeout_seconds)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Weaviate client creation timed out after {timeout_seconds} seconds"
                )
                # Cancel the executor future to avoid resource leaks
                executor_future.cancel()
                return added
        except Exception as e:
            logger.warning(f"Failed to create Weaviate client during resync: {e}")
            return added

        # Create task for proper cancellation on timeout
        list_task = asyncio.create_task(temp.list_collections())
        try:
            collections = await asyncio.wait_for(list_task, timeout=timeout_seconds)
            collections = collections or []
        except asyncio.TimeoutError:
            logger.warning(
                f"Weaviate collection listing timed out after {timeout_seconds} seconds"
            )
            # Properly cancel the task to avoid resource leaks
            list_task.cancel()
            try:
                await list_task
            except asyncio.CancelledError:
                pass  # Expected when we cancel
            return added
        except Exception as e:
            logger.warning(f"Failed to list Weaviate collections during resync: {e}")
            return added
        finally:
            # Close the temporary connection to avoid resource warnings/leaks
            try:
                if temp:
                    await temp.cleanup()
            except Exception:
                pass

        for coll in collections:
            if coll not in vector_databases:
                try:
                    db = WeaviateVectorDatabase(collection_name=coll)
                    # Best-effort: set embedding info on instance if available
                    try:
                        info = await db.get_collection_info(coll)
                        emb_details = (info or {}).get("embedding_details", {})
                        name = emb_details.get("name")
                        if name:
                            db.embedding_model = name
                    except Exception:
                        pass

                    vector_databases[coll] = db
                    added.append(coll)
                except Exception as e:
                    logger.warning(
                        f"Failed to register Weaviate collection '{coll}' during resync: {e}"
                    )
    except Exception as e:
        # Likely missing environment variables or dependency; skip silently but log
        logger.info(f"Weaviate resync skipped: {e}")

    if added:
        logger.info(f"Resynced and registered Weaviate collections: {added}")
    return added


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
    documents: list[dict[str, Any]] = Field(
        ...,
        description=(
            "List of documents to write. Each document is a dict with:\n"
            "- 'url' (required): Document identifier or URL to fetch from\n"
            "- 'text' (optional): Direct text content (backwards compatible)\n"
            "- 'metadata' (optional): Additional metadata dict\n\n"
            "URL Fetching: If 'url' starts with http:// or https://, the system will:\n"
            "1. Fetch the content from the URL\n"
            "2. Auto-detect format (HTML, PDF, Markdown, Text)\n"
            "3. Convert to plain text\n"
            "4. Enrich metadata with fetch details\n\n"
            "Supported formats: HTML (converted via html2text), PDF (requires PyPDF2), "
            "Markdown (.md), Plain text (.txt)\n\n"
            "Security: Only HTTP/HTTPS URLs allowed. File paths (file://) restricted to "
            "current working directory and subdirectories.\n\n"
            "Backwards Compatible: Providing 'text' directly still works. If both 'url' and 'text' "
            "are provided, 'text' takes precedence (no fetching occurs)."
        ),
    )
    # TODO(deprecate): embedding at write-time is deprecated and ignored; embedding is per-collection
    embedding: str = Field(
        default="default",
        description="(DEPRECATED) Embedding strategy to use; ignored at write time",
    )


class WriteDocumentInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    url: str = Field(..., description="URL of the document")
    text: str = Field(..., description="Text content of the document")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the document"
    )
    vector: list[float] | None = Field(
        default=None,
        description="Pre-computed vector embedding (optional, for Milvus)",
    )
    # TODO(deprecate): embedding at write-time is deprecated and ignored; embedding is per-collection
    embedding: str = Field(
        default="default",
        description="(DEPRECATED) Embedding strategy to use; ignored at write time",
    )


class WriteDocumentToCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(..., description="Name of the collection to write to")
    doc_name: str = Field(..., description="Name of the document")
    text: str = Field(..., description="Text content of the document")
    url: str = Field(..., description="URL of the document")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the document"
    )
    vector: list[float] | None = Field(
        default=None,
        description="Pre-computed vector embedding (optional, for Milvus)",
    )
    # TODO(deprecate): embedding at write-time is deprecated and ignored; embedding is per-collection
    embedding: str = Field(
        default="default",
        description="(DEPRECATED) Embedding strategy to use; ignored at write time",
    )


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
    document_ids: list[str] = Field(..., description="List of document IDs to delete")


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
    collection_name: str | None = Field(
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
    collection_name: str | None = Field(
        default=None,
        description="Name of the collection to get info for. If not provided, uses the default collection.",
    )


class CreateCollectionInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    collection_name: str = Field(..., description="Name of the collection to create")
    embedding: str = Field(
        default="default", description="Embedding model to use for the collection"
    )
    chunking_config: dict[str, Any] | None = Field(
        default=None,
        description="Optional chunking configuration for the collection. Example: {'strategy':'Sentence','parameters':{'chunk_size':256,'overlap':1}}",
    )


class QueryInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    query: str = Field(..., description="The query string to search for")
    limit: int = Field(default=5, description="Maximum number of results to consider")
    collection_name: str | None = Field(
        default=None, description="Optional collection name to search in"
    )


class SearchInput(BaseModel):
    db_name: str = Field(..., description="Name of the vector database instance")
    query: str = Field(..., description="The query string to search for")
    limit: int = Field(default=5, description="Maximum number of results to consider")
    collection_name: str | None = Field(
        default=None, description="Optional collection name to search in"
    )


async def create_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server with vector database tools."""

    # Create FastMCP server directly
    app = FastMCP("maestro-vector-db")

    @app.custom_route("/health", methods=["GET"])
    async def health_check(request: Request) -> PlainTextResponse:
        # Liveness by default; readiness when "ready" param is present (value ignored)
        if request.query_params.get("ready") is None:
            return PlainTextResponse("OK")

        # Readiness: perform light checks with timeouts
        if not vector_databases:
            return PlainTextResponse("Ready: no databases configured")

        db_list: list[dict[str, Any]] = []
        for db_name, db in vector_databases.items():
            # Protect per-db count with a timeout so /health never hangs
            count_task = asyncio.create_task(db.count_documents())
            try:
                count = await asyncio.wait_for(
                    count_task, timeout=get_timeout("health")
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "health_check(readiness): count_documents timed out for db '%s'",
                    db_name,
                )
                # Properly cancel the task to avoid resource leaks
                count_task.cancel()
                try:
                    await count_task
                except asyncio.CancelledError:
                    pass  # Expected when we cancel
                count = -1  # indicate unknown
            except Exception as e:
                logger.warning(
                    "health_check(readiness): count_documents failed for db '%s': %s",
                    db_name,
                    e,
                )
                count = -1

            db_list.append(
                {
                    "name": db_name,
                    "type": db.db_type,
                    "collection": db.collection_name,
                    "document_count": count,
                }
            )

        return PlainTextResponse(
            "Ready\n" + json.dumps({"databases": db_list}, indent=2)
        )

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
                input.db_type, input.collection_name
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
            if hasattr(db, "setup"):
                # Get the number of parameters in the setup method
                param_count = len(db.setup.__code__.co_varnames)
                if param_count > 2:  # self, embedding, collection_name
                    ok, res = await run_with_timeout(
                        db.setup(embedding=input.embedding),
                        "setup_database",
                        get_timeout("setup_database"),
                    )
                elif param_count > 1:  # self, embedding
                    ok, res = await run_with_timeout(
                        db.setup(embedding=input.embedding),
                        "setup_database",
                        get_timeout("setup_database"),
                    )
                else:  # self only
                    ok, res = await run_with_timeout(
                        db.setup(), "setup_database", get_timeout("setup_database")
                    )
                if not ok:
                    return str(res)

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
    async def get_supported_chunking_strategies() -> str:
        """Return the supported chunking strategies and their parameters."""
        # Keep this in sync with the src/chunking/ package defaults
        strategies = [
            {
                "name": "None",
                "parameters": {},
                "description": "No chunking; the entire document is a single chunk.",
                "defaults": {},
            },
            {
                "name": "Fixed",
                "parameters": {
                    "chunk_size": "int > 0",
                    "overlap": "int >= 0",
                },
                "description": "Fixed-size windows with optional overlap.",
                "defaults": {"chunk_size": 512, "overlap": 0},
            },
            {
                "name": "Sentence",
                "parameters": {
                    "chunk_size": "int > 0",
                    "overlap": "int >= 0",
                },
                "description": "Sentence-aware packing up to chunk_size with optional overlap; long sentences are split.",
                "defaults": {"chunk_size": 512, "overlap": 0},
            },
            {
                "name": "Semantic",
                "parameters": {
                    "chunk_size": "int > 0",
                    "overlap": "int >= 0",
                    "window_size": "int >= 0",
                    "threshold_percentile": "float 0-100",
                    "model_name": "string",
                },
                "description": "Semantic chunking using sentence embeddings and similarity to create coherent chunks.",
                "defaults": {
                    "chunk_size": 768,
                    "overlap": 0,
                    "window_size": 1,
                    "threshold_percentile": 95.0,
                    "model_name": "all-MiniLM-L6-v2",
                },
            },
        ]
        defaults_behavior = {
            "chunk_text_default_strategy": ChunkingConfig().strategy,
            "default_params_when_strategy_set": {"chunk_size": 512, "overlap": 0},
        }
        return json.dumps(
            {"strategies": strategies, "notes": defaults_behavior}, indent=2
        )

    @app.tool()
    async def write_documents(input: WriteDocumentsInput) -> str:
        """
        Write documents to a vector database with automatic URL fetching and format conversion.

        This tool supports both direct text provision (backwards compatible) and automatic
        fetching from URLs with format detection and conversion.

        Key Features:
        - URL Fetching: Automatically fetches content from http:// or https:// URLs
        - Format Detection: Auto-detects HTML, PDF, Markdown, and plain text
        - Format Conversion: Converts HTML (via html2text) and PDF (via PyPDF2) to plain text
        - Security: Only HTTP/HTTPS allowed; file:// paths restricted to CWD and subdirectories
        - Backwards Compatible: Direct 'text' field still works; takes precedence over URL fetching
        - Metadata Enrichment: Fetched documents get enriched with content_type, fetched_at, etc.

        Document Format:
        Each document in the 'documents' list should be a dict with:
        - 'url' (required): Document identifier or URL to fetch from
        - 'text' (optional): Direct text content (if provided, no fetching occurs)
        - 'metadata' (optional): Additional metadata dict

        Supported URL Formats:
        - HTML pages: Converted to markdown-style text
        - PDF files: Text extracted (requires PyPDF2 installed)
        - Markdown files (.md): Preserved as-is
        - Text files (.txt): Preserved as-is

        Security Restrictions:
        - Only http:// and https:// protocols allowed for remote URLs
        - file:// URLs restricted to current working directory and subdirectories
        - No directory traversal (../) allowed in file paths
        - 30-second timeout for URL fetching

        Limitations:
        - PDF conversion is basic text extraction (no OCR, no complex layouts)
        - HTML conversion may not preserve all formatting
        - Large files may hit timeout limits
        - Embedding is configured per-collection, not per-document

        Returns:
        JSON string with:
        - status: "ok" or "error"
        - message: Summary of operation
        - write_stats: Statistics about chunks written
        - collection_info: Updated collection information
        - sample_query_suggestion: Suggested query to test the collection

        Note: Embedding at write-time is deprecated; collection-level embedding is used.
        """
        db = get_database_by_name(input.db_name)
        # Deprecation: ignore per-document embedding; use collection embedding
        if input.embedding and input.embedding != "default":
            logger.warning(
                "Deprecation: embedding specified at write_documents is ignored; embedding is configured per collection."
            )
        # Use the database's current collection embedding where applicable
        coll_info: dict[str, Any] | None = None
        try:
            # Best effort: fetch current collection info to get embedding
            ok, coll_info_any = await run_with_timeout(
                db.get_collection_info(),
                "get_collection_info",
                get_timeout("get_collection_info"),
            )
            if ok:
                coll_info = cast("dict[str, Any]", coll_info_any)
        except Exception:
            pass
        collection_embedding = (coll_info or {}).get("embedding", "default")
        stats: Any = None
        try:
            ok, stats_any = await run_with_timeout(
                db.write_documents(input.documents, embedding=collection_embedding),
                "write_documents",
                get_timeout("write_bulk"),
            )
            if not ok:
                result = {"status": "error", "message": str(stats_any)}
                return json.dumps(result, indent=2)
            stats = stats_any
        except Exception as e:
            # surface error in JSON result
            result = {
                "status": "error",
                "message": f"Failed to write documents: {str(e)}",
            }
            return json.dumps(result, indent=2)

        # Refresh collection info after write
        post_info: dict[str, Any] | None = None
        try:
            ok, post_info_any = await run_with_timeout(
                db.get_collection_info(),
                "get_collection_info",
                get_timeout("get_collection_info"),
            )
            post_info = cast("dict[str, Any]", post_info_any) if ok else None
        except Exception:
            post_info = None

        # Build a sample query suggestion without executing a search (avoid network/API calls here)
        sample_query = "What is this collection about?"
        try:
            # Take first non-empty document text and use first few words as query
            for d in input.documents:
                t = (d or {}).get("text") or ""
                if t:
                    words = t.strip().split()
                    if words:
                        sample_query = " ".join(words[:8])
                        break
        except Exception:
            pass

        result = {
            "status": "ok",
            "message": f"Wrote {len(input.documents)} document(s)",
            "write_stats": stats,
            "collection_info": post_info,
            "sample_query_suggestion": {
                "query": sample_query,
                "limit": 3,
                "collection": (post_info or {}).get("name"),
            },
        }
        return json.dumps(result, indent=2, default=str)

    @app.tool()
    async def write_document(input: WriteDocumentInput) -> str:
        """
        Write a single document to a vector database with automatic URL fetching and format conversion.

        This is a convenience wrapper around write_documents for single document operations.
        Supports the same URL fetching and format conversion features.

        Parameters:
        - db_name: Name of the vector database instance
        - url: Document identifier or URL to fetch from (http://, https://, or file://)
        - text: Direct text content (if provided, no URL fetching occurs)
        - metadata: Additional metadata dict (optional)
        - vector: Pre-computed embedding vector for Milvus (optional)

        URL Fetching Behavior:
        - If 'text' is provided: Uses text directly, no fetching
        - If 'text' is empty and 'url' starts with http/https: Fetches and converts content
        - Supported formats: HTML, PDF, Markdown, Plain text
        - Security: Same restrictions as write_documents

        Returns:
        JSON string with status, message, write_stats, and collection_info.

        Note: For batch operations, use write_documents instead for better performance.
        Embedding is configured per-collection, not per-document.
        """
        db = get_database_by_name(input.db_name)
        document: dict[str, Any] = {
            "url": input.url,
            "text": input.text,
            "metadata": input.metadata,
        }

        # Add vector if provided (for Milvus)
        if input.vector is not None:
            document["vector"] = input.vector

        # Deprecation: ignore per-document embedding; use collection embedding
        if input.embedding and input.embedding != "default":
            logger.warning(
                "Deprecation: embedding specified at write_document is ignored; embedding is configured per collection."
            )
        coll_info: dict[str, Any] | None = None
        try:
            ok, coll_info_any = await run_with_timeout(
                db.get_collection_info(),
                "get_collection_info",
                get_timeout("get_collection_info"),
            )
            if ok:
                coll_info = cast("dict[str, Any]", coll_info_any)
        except Exception:
            pass
        collection_embedding = (coll_info or {}).get("embedding", "default")
        stats = None
        try:
            ok, stats = await run_with_timeout(
                db.write_document(document, embedding=collection_embedding),
                "write_document",
                get_timeout("write_single"),
            )
            if not ok:
                return json.dumps({"status": "error", "message": str(stats)}, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to write document: {str(e)}",
                },
                indent=2,
            )

        # Post-write info and suggestion
        post_info: dict[str, Any] | None = None
        try:
            ok, post_info_any = await run_with_timeout(
                db.get_collection_info(),
                "get_collection_info",
                get_timeout("get_collection_info"),
            )
            post_info = cast("dict[str, Any]", post_info_any) if ok else None
        except Exception:
            post_info = None
        sample_query = (
            " ".join(((input.text or "").strip().split())[:8]) or "What is this about?"
        )
        return json.dumps(
            {
                "status": "ok",
                "message": "Wrote 1 document",
                "write_stats": stats,
                "collection_info": post_info,
                "sample_query_suggestion": {
                    "query": sample_query,
                    "limit": 3,
                    "collection": (post_info or {}).get("name"),
                },
            },
            indent=2,
            default=str,
        )

    @app.tool()
    async def write_document_to_collection(
        input: WriteDocumentToCollectionInput,
    ) -> str:
        """Write a single document to a specific collection. Embedding at write-time is deprecated; collection embedding is used. Returns JSON with stats and collection info."""
        db = get_database_by_name(input.db_name)

        # Check if the collection exists
        ok, collections_any = await run_with_timeout(
            db.list_collections(), "list_collections", get_timeout("list_collections")
        )
        collections: list[str] = (
            cast("list[str]", collections_any)
            if ok and isinstance(collections_any, list)
            else []
        )
        if input.collection_name not in collections:
            raise ValueError(
                f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
            )

        # Create document with collection-specific metadata
        document: dict[str, Any] = {
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

        # Deprecation: ignore per-document embedding; use target collection embedding
        if input.embedding and input.embedding != "default":
            logger.warning(
                "Deprecation: embedding specified at write_document_to_collection is ignored; embedding is configured per collection."
            )
        collection_embedding = "default"
        try:
            ok, info_any = await run_with_timeout(
                db.get_collection_info(input.collection_name),
                "get_collection_info",
                get_timeout("get_collection_info"),
            )
            info: dict[str, Any] = (
                cast("dict[str, Any]", info_any)
                if ok and isinstance(info_any, dict)
                else {}
            )
            collection_embedding = info.get("embedding", "default")
        except Exception:
            pass
        # Use the new write_documents_to_collection method
        stats = None
        try:
            ok, stats = await run_with_timeout(
                db.write_documents_to_collection(
                    [document], input.collection_name, embedding=collection_embedding
                ),
                "write_document_to_collection",
                get_timeout("write_single"),
            )
            if not ok:
                return json.dumps({"status": "error", "message": str(stats)}, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to write document to collection: {str(e)}",
                },
                indent=2,
            )

        # Post-write info and suggestion
        post_info = None
        try:
            post_info = await db.get_collection_info(input.collection_name)
        except Exception:
            post_info = None
        sample_query = (
            " ".join(((input.text or "").strip().split())[:8]) or "What is this about?"
        )
        return json.dumps(
            {
                "status": "ok",
                "message": f"Wrote 1 document to collection '{input.collection_name}'",
                "write_stats": stats,
                "collection_info": post_info,
                "sample_query_suggestion": {
                    "query": sample_query,
                    "limit": 3,
                    "collection": input.collection_name,
                },
            },
            indent=2,
            default=str,
        )

    @app.tool()
    async def list_documents(input: ListDocumentsInput) -> str:
        """List documents from a vector database."""
        db = get_database_by_name(input.db_name)
        ok, documents_any = await run_with_timeout(
            db.list_documents(input.limit, input.offset),
            "list_documents",
            get_timeout("list_documents"),
        )
        documents: list[dict[str, Any]] = (
            cast("list[dict[str, Any]]", documents_any)
            if ok and isinstance(documents_any, list)
            else []
        )

        return f"Found {len(documents)} documents in vector database '{input.db_name}':\n{json.dumps(documents, indent=2, default=str)}"

    @app.tool()
    async def list_documents_in_collection(
        input: ListDocumentsInCollectionInput,
    ) -> str:
        """List documents from a specific collection in a vector database."""
        db = get_database_by_name(input.db_name)

        # Check if the collection exists
        ok, collections_any = await run_with_timeout(
            db.list_collections(), "list_collections", get_timeout("list_collections")
        )
        collections = (
            cast("list[str]", collections_any)
            if ok and isinstance(collections_any, list)
            else []
        )
        # Use case-sensitive comparison
        if input.collection_name not in collections:
            raise ValueError(
                f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
            )

        # Use the new list_documents_in_collection method
        ok, documents_any = await run_with_timeout(
            db.list_documents_in_collection(
                input.collection_name, input.limit, input.offset
            ),
            "list_documents",
            get_timeout("list_documents"),
        )
        documents = (
            cast("list[dict[str, Any]]", documents_any)
            if ok and isinstance(documents_any, list)
            else []
        )
        return f"Found {len(documents)} documents in collection '{input.collection_name}' of vector database '{input.db_name}':\n{json.dumps(documents, indent=2, default=str)}"

    @app.tool()
    async def count_documents(input: CountDocumentsInput) -> str:
        """Get the current count of documents in a collection."""
        db = get_database_by_name(input.db_name)
        ok, count_any = await run_with_timeout(
            db.count_documents(), "count_documents", get_timeout("count_documents")
        )
        count: int = int(count_any) if ok else -1

        return f"Document count in vector database '{input.db_name}': {count}"

    @app.tool()
    async def delete_documents(input: DeleteDocumentsInput) -> str:
        """Delete documents from a vector database by their IDs."""
        db = get_database_by_name(input.db_name)
        ok, _ = await run_with_timeout(
            db.delete_documents(input.document_ids), "delete", get_timeout("delete")
        )
        if not ok:
            return f"Error: Failed to delete documents in vector database '{input.db_name}'"

        return f"Successfully deleted {len(input.document_ids)} documents from vector database '{input.db_name}'"

    @app.tool()
    async def delete_document(input: DeleteDocumentInput) -> str:
        """Delete a single document from a vector database."""
        db = get_database_by_name(input.db_name)
        ok, _ = await run_with_timeout(
            db.delete_document(input.document_id), "delete", get_timeout("delete")
        )
        if not ok:
            return f"Error: Failed to delete document '{input.document_id}' from vector database '{input.db_name}'"

        return f"Successfully deleted document '{input.document_id}' from vector database '{input.db_name}'"

    @app.tool()
    async def delete_document_from_collection(
        input: DeleteDocumentFromCollectionInput,
    ) -> str:
        """Delete a document from a specific collection in a vector database by document name."""
        db = get_database_by_name(input.db_name)

        # Check if the collection exists
        ok, collections_any = await run_with_timeout(
            db.list_collections(), "list_collections", get_timeout("list_collections")
        )
        collections = (
            cast("list[str]", collections_any)
            if ok and isinstance(collections_any, list)
            else []
        )
        if input.collection_name not in collections:
            raise ValueError(
                f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
            )

        # Temporarily switch to the target collection
        original_collection = db.collection_name
        db.collection_name = input.collection_name

        try:
            # List documents to find the one with the matching name
            ok, documents_any = await run_with_timeout(
                db.list_documents(limit=1000, offset=0),
                "list_documents",
                get_timeout("list_documents"),
            )
            documents = (
                cast("list[dict[str, Any]]", documents_any)
                if ok and isinstance(documents_any, list)
                else []
            )
            document_id = None

            for doc in documents:
                if doc.get("metadata", {}).get("doc_name") == input.doc_name:
                    document_id = doc.get("id")
                    break

            if document_id is None:
                raise ValueError(
                    f"Document '{input.doc_name}' not found in collection '{input.collection_name}' of vector database '{input.db_name}'"
                )

            # Delete the document
            ok, _ = await run_with_timeout(
                db.delete_document(document_id), "delete", get_timeout("delete")
            )
            if not ok:
                return f"Error: Failed to delete document '{input.doc_name}' from collection '{input.collection_name}'"

            return f"Successfully deleted document '{input.doc_name}' from collection '{input.collection_name}' in vector database '{input.db_name}'"
        finally:
            # Restore original collection
            db.collection_name = original_collection

    @app.tool()
    async def get_document(input: GetDocumentInput) -> str:
        """Get a specific document by name from a collection in a vector database."""
        db = get_database_by_name(input.db_name)

        # Check if the collection exists
        ok, collections_any = await run_with_timeout(
            db.list_collections(), "list_collections", get_timeout("list_collections")
        )
        collections = (
            cast("list[str]", collections_any)
            if ok and isinstance(collections_any, list)
            else []
        )
        if input.collection_name not in collections:
            raise ValueError(
                f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
            )

        try:
            # Get the document using the new get_document method
            ok, document_any = await run_with_timeout(
                db.get_document(input.doc_name, input.collection_name),
                "get_document",
                get_timeout("list_documents"),
            )
            if not ok:
                return str(document_any)
            document: dict[str, Any] = cast("dict[str, Any]", document_any)
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
            ok, colls_any = await run_with_timeout(
                db.list_collections(),
                "list_collections",
                get_timeout("list_collections"),
            )
            collections = (
                cast("list[str]", colls_any)
                if ok and isinstance(colls_any, list)
                else []
            )
            if (
                input.collection_name is None
                or input.collection_name not in collections
            ):
                raise ValueError(
                    f"Collection '{input.collection_name}' not found in vector database '{input.db_name}'"
                )
            ok, _ = await run_with_timeout(
                db.delete_collection(input.collection_name),
                "delete",
                get_timeout("delete"),
            )
            if not ok:
                return f"Error: Failed to delete collection '{input.collection_name}' from vector database '{input.db_name}'"

            return f"Successfully deleted collection '{input.collection_name}' from vector database '{input.db_name}'"
        try:
            from src.db.vector_db_milvus import MilvusVectorDatabase

            if input.collection_name is None:
                raise ValueError(
                    "collection_name must be provided to delete a collection"
                )
            temp_db = MilvusVectorDatabase(collection_name=input.collection_name)
            ok, _ = await run_with_timeout(
                temp_db.delete_collection(input.collection_name),
                "delete",
                get_timeout("delete"),
            )
            if not ok:
                return f"Error: Failed to delete collection '{input.collection_name}' from Milvus (untracked)."
            return f"Successfully dropped collection '{input.collection_name}' from Milvus (untracked)."
        except Exception as e:
            return f"Delete collection failed: {str(e)}"

    @app.tool()
    async def cleanup(input: CleanupInput) -> str:
        """Clean up resources and close connections for a vector database."""
        if input.db_name in vector_databases:
            db = get_database_by_name(input.db_name)
            ok, _ = await run_with_timeout(
                db.cleanup(), "cleanup", get_timeout("cleanup")
            )
            if not ok:
                return f"Error: Failed to cleanup vector database '{input.db_name}'"
            del vector_databases[input.db_name]
            return (
                f"Successfully cleaned up and removed vector database '{input.db_name}'"
            )
        try:
            from src.db.vector_db_milvus import MilvusVectorDatabase

            temp_db = MilvusVectorDatabase(collection_name=input.db_name)
            ok, _ = await run_with_timeout(
                temp_db.delete_collection(input.db_name),
                "cleanup",
                get_timeout("cleanup"),
            )
            if not ok:
                return f"Error: Failed to cleanup (drop) collection '{input.db_name}' from Milvus (untracked)."
            return f"Successfully dropped collection '{input.db_name}' from Milvus (untracked)."
        except Exception as e:
            return f"Cleanup failed: {str(e)}"

    @app.tool()
    async def get_database_info(input: GetDatabaseInfoInput) -> str:
        """Get information about a vector database."""
        db = get_database_by_name(input.db_name)
        ok, cnt_any = await run_with_timeout(
            db.count_documents(), "count_documents", get_timeout("count_documents")
        )
        count = int(cnt_any) if ok else -1
        info = {
            "name": input.db_name,
            "type": db.db_type,
            "collection": db.collection_name,
            "document_count": count,
        }

        return (
            f"Database information for '{input.db_name}':\n{json.dumps(info, indent=2)}"
        )

    @app.tool()
    async def list_collections(input: ListCollectionsInput) -> str:
        """List all collections in a vector database."""
        db = get_database_by_name(input.db_name)
        ok, colls_any = await run_with_timeout(
            db.list_collections(), "list_collections", get_timeout("list_collections")
        )
        collections = (
            cast("list[str]", colls_any) if ok and isinstance(colls_any, list) else []
        )

        if not collections:
            return f"No collections found in vector database '{input.db_name}'"

        return f"Collections in vector database '{input.db_name}':\n{json.dumps(collections, indent=2)}"

    @app.tool()
    async def get_collection_info(input: GetCollectionInfoInput) -> str:
        """Get information about a collection in a vector database."""
        db = get_database_by_name(input.db_name)
        # Always delegate to the backend which can surface metadata even if
        # the collection doesn't exist (including chunking config and errors)
        if input.collection_name is None:
            ok, info_any = await run_with_timeout(
                db.get_collection_info(),
                "get_collection_info",
                get_timeout("get_collection_info"),
            )
        else:
            ok, info_any = await run_with_timeout(
                db.get_collection_info(input.collection_name),
                "get_collection_info",
                get_timeout("get_collection_info"),
            )
        if not ok:
            return str(info_any)
        info: dict[str, Any] = cast("dict[str, Any]", info_any)

        return (
            f"Collection information for '{info.get('name')}' in vector database "
            f"'{input.db_name}':\n{json.dumps(info, indent=2)}"
        )

    @app.tool()
    async def create_collection(input: CreateCollectionInput) -> str:
        """Create a new collection in a vector database."""
        try:
            db = get_database_by_name(input.db_name)

            # Check if collection already exists
            ok, existing_any = await run_with_timeout(
                db.list_collections(),
                "list_collections",
                get_timeout("list_collections"),
            )
            existing_collections = (
                cast("list[str]", existing_any)
                if ok and isinstance(existing_any, list)
                else []
            )
            if input.collection_name in existing_collections:
                return f"Error: Collection '{input.collection_name}' already exists in vector database '{input.db_name}'"

            # Temporarily switch to the new collection name
            original_collection = db.collection_name
            db.collection_name = input.collection_name

            try:
                # Create the collection using the setup method
                if hasattr(db, "setup"):
                    # Get the number of parameters in the setup method
                    param_count = len(db.setup.__code__.co_varnames)
                    # Try to call setup with embedding and chunking_config where supported
                    if (param_count > 3) and (input.chunking_config is not None):
                        # self, embedding, collection_name, chunking_config
                        ok, res = await run_with_timeout(
                            db.setup(
                                embedding=input.embedding,
                                collection_name=input.collection_name,
                                chunking_config=input.chunking_config,
                            ),
                            "create_collection",
                            get_timeout("create_collection"),
                        )
                    elif param_count > 2:  # self, embedding, collection_name
                        ok, res = await run_with_timeout(
                            db.setup(
                                embedding=input.embedding,
                                collection_name=input.collection_name,
                            ),
                            "create_collection",
                            get_timeout("create_collection"),
                        )
                    elif param_count > 1:  # self, embedding
                        ok, res = await run_with_timeout(
                            db.setup(embedding=input.embedding),
                            "create_collection",
                            get_timeout("create_collection"),
                        )
                    else:  # self only
                        ok, res = await run_with_timeout(
                            db.setup(),
                            "create_collection",
                            get_timeout("create_collection"),
                        )
                else:
                    ok, res = await run_with_timeout(
                        db.setup(),
                        "create_collection",
                        get_timeout("create_collection"),
                    )
                if not ok:
                    return str(res)

                # NOTE: Embedding is configured per-collection at creation time.
                # TODO(deprecate): Remove write-time embedding parameters from write tools in a future release.
                return f"Successfully created collection '{input.collection_name}' in vector database '{input.db_name}' with embedding '{input.embedding}'"
            finally:
                # Restore the original collection name
                db.collection_name = original_collection

        except Exception as e:
            error_msg = f"Failed to create collection '{input.collection_name}' in vector database '{input.db_name}': {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    @app.tool()
    async def query(input: QueryInput) -> str:
        """Query a vector database using the default query agent."""
        try:
            db = get_database_by_name(input.db_name)
            kwargs: dict[str, Any] = {"limit": input.limit}
            if input.collection_name is not None:
                kwargs["collection_name"] = input.collection_name
            ok, response = await run_with_timeout(
                db.query(input.query, **kwargs), "query", get_timeout("query")
            )
            if not ok:
                return str(response)
            # response is expected to be a string summary
            return str(response)
        except Exception as e:
            error_msg = f"Failed to query vector database '{input.db_name}': {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    @app.tool()
    async def search(input: SearchInput) -> str:
        """Search a vector database using vector similarity search."""
        try:
            db = get_database_by_name(input.db_name)
            kwargs: dict[str, Any] = {"limit": input.limit}
            if input.collection_name is not None:
                kwargs["collection_name"] = input.collection_name
            ok, response = await run_with_timeout(
                db.search(input.query, **kwargs), "search", get_timeout("search")
            )
            if not ok:
                return str(response)
            # Serialize list of results to JSON string for consistent str tool output
            return json.dumps(response, indent=2, default=str)
        except Exception as e:
            error_msg = f"Failed to search vector database '{input.db_name}': {str(e)}"
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
            ok, count = await run_with_timeout(
                db.count_documents(),
                "list_databases/count",
                get_timeout("list_databases"),
            )
            if not ok:
                count = -1
            db_list.append(
                {
                    "name": db_name,
                    "type": db.db_type,
                    "collection": db.collection_name,
                    "document_count": count,
                }
            )

        logger.info(f"Returning {len(db_list)} databases")
        return f"Available vector databases:\n{json.dumps(db_list, indent=2)}"

    @app.tool()
    async def resync_databases_tool() -> str:
        """Discover and register Milvus collections into the MCP server's in-memory registry."""
        try:
            added_milvus = await resync_vector_databases()
            added_weaviate = await resync_weaviate_databases()
            return json.dumps(
                {
                    "milvus": {"added": added_milvus, "count": len(added_milvus)},
                    "weaviate": {
                        "added": added_weaviate,
                        "count": len(added_weaviate),
                    },
                    "total_count": len(added_milvus) + len(added_weaviate),
                },
                indent=2,
            )
        except Exception as e:
            logger.exception("Failed to run resync_databases tool")
            return json.dumps({"error": str(e)}, indent=2)

    # Attempt an automatic resync on startup so that in-memory registry reflects
    # any pre-existing Milvus collections created outside this process.
    try:
        added_m = await resync_vector_databases()
        added_w = await resync_weaviate_databases()
        if added_m or added_w:
            logger.info(
                f"Auto-resynced vector databases at startup: milvus={added_m}, weaviate={added_w}"
            )
    except Exception:
        logger.exception("Error while auto-resyncing vector databases at startup")

    return app


async def main() -> None:
    """Main entry point for the MCP server."""
    app = await create_mcp_server()
    app.run()


async def run_http_server(host: str = "localhost", port: int = 8030) -> None:
    """Run the MCP server with HTTP interface."""
    # Create the MCP server
    mcp_app = await create_mcp_server()

    print(f"Starting FastMCP HTTP server on http://{host}:{port}")
    print(f"Open your browser to http://{host}:{port} to access the MCP server")
    print(f"📖 OpenAPI docs: http://{host}:{port}/docs")
    print(f"📚 ReDoc docs: http://{host}:{port}/redoc")

    import os

    custom_url = os.getenv("CUSTOM_EMBEDDING_URL")
    if custom_url:
        custom_model = os.getenv("CUSTOM_EMBEDDING_MODEL", "nomic-embed-text")
        print(f"   - URL:    {custom_url}")
        print(f"   - Model:  {custom_model}")
    else:
        print("🧬 Using default OpenAI embedding configuration.")
    await mcp_app.run_http_async(host=host, port=port)


def run_server() -> None:
    """Entry point for running the server."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error running server: {e}")
        sys.exit(1)


def run_http_server_sync(host: str = "localhost", port: int = 8030) -> None:
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
