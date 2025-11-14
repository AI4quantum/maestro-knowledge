# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import asyncio
import json
import logging
import os
import sys
from collections.abc import Awaitable, Callable
from typing import Any, cast

from fastmcp import FastMCP
from fastmcp.tools.tool import ToolResult
from pydantic import BaseModel, Field
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from src.chunking import ChunkingConfig
from src.db.vector_db_base import VectorDatabase
from src.db.vector_db_factory import create_vector_database
from src.maestro_mcp.error_messages import ErrorMessages
from src.maestro_mcp.response_formatter import (
    collection_created_response,
    collection_deleted_response,
    database_created_response,
    database_deleted_response,
    documents_deleted_response,
    documents_written_response,
    error_response,
    search_results_response,
    success_response,
)


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


def get_database_by_name(db_name: str, auto_bootstrap: bool = True) -> VectorDatabase:
    """Get a vector database instance by name, optionally bootstrapping if not found.

    Args:
        db_name: Name of the database to retrieve
        auto_bootstrap: If True, automatically create database entry if it doesn't exist (Phase 8.5)

    Returns:
        VectorDatabase instance

    Raises:
        ValueError: If database not found and auto_bootstrap=False
    """
    if db_name not in vector_databases:
        if not auto_bootstrap:
            raise ValueError(
                f"Collection '{db_name}' not found. Please register it first with register_database()."
            )

        # Bootstrap new database connection (Phase 8.5)
        logger.info(f"Auto-bootstrapping database connection for '{db_name}'")

        # Determine database type from environment
        db_type = None
        if os.getenv("MILVUS_URI"):
            db_type = "milvus"
        elif os.getenv("WEAVIATE_URL"):
            db_type = "weaviate"
        else:
            # Default to Milvus
            db_type = "milvus"
            logger.info(
                "No vector DB environment variables found, defaulting to Milvus"
            )

        # Create database instance
        try:
            from src.db.vector_db_factory import create_vector_database

            db = create_vector_database(db_type)

            # Try to infer embedding config from environment (same logic as resync)
            try:
                env_url = os.getenv("CUSTOM_EMBEDDING_URL")
                env_model = os.getenv("CUSTOM_EMBEDDING_MODEL")
                env_vs = os.getenv("CUSTOM_EMBEDDING_VECTORSIZE")

                if env_url and env_model and env_vs:
                    # Custom embedding is configured - use it
                    db.embedding_model = "custom_local"
                    try:
                        db.dimension = int(env_vs)
                        logger.info(
                            f"Auto-detected custom_local embedding (dim={env_vs}) for '{db_name}'"
                        )
                    except ValueError:
                        logger.warning(f"Invalid CUSTOM_EMBEDDING_VECTORSIZE: {env_vs}")
                else:
                    # No custom embedding - use default OpenAI
                    db.embedding_model = "text-embedding-ada-002"
                    logger.info(f"Using default OpenAI embedding for '{db_name}'")
            except Exception as e:
                logger.warning(f"Failed to infer embedding config for '{db_name}': {e}")
                db.embedding_model = "text-embedding-ada-002"

            vector_databases[db_name] = db
            logger.info(f"Bootstrapped new {db_type} database connection: {db_name}")
            return db
        except Exception as e:
            raise ValueError(f"Failed to bootstrap database '{db_name}': {str(e)}")

    return vector_databases[db_name]


def get_default_database_name() -> str | None:
    """Get the default database name (first registered database).

    Returns None if no databases are registered.
    This is used when database parameter is not provided.
    """
    if not vector_databases:
        return None
    # Return the first registered database
    return next(iter(vector_databases.keys()))


# Pydantic models for tool inputs


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

    # DISABLED: Confusing terminology - "database" actually means "collection"
    # Use create_collection() instead for clearer semantics
    # @app.tool()
    async def create_database_DISABLED(
        database: str = Field(
            ..., description="Unique name for the vector database instance"
        ),
        database_type: str = Field(
            ...,
            description="Type of vector database to create",
            json_schema_extra={"enum": ["weaviate", "milvus"]},
        ),
        embedding: str = Field(
            default="auto",
            description=(
                "Embedding model to use. Options: 'auto' (auto-detect from environment), "
                "'text-embedding-ada-002', 'text-embedding-3-small', 'text-embedding-3-large', "
                "or 'custom_local'. 'auto' will use custom_local if configured, otherwise "
                "falls back to OpenAI text-embedding-ada-002."
            ),
        ),
    ) -> str:
        """
        Create and initialize a vector database instance.

        This creates the database connection but does NOT create any collections.
        You must explicitly create collections using create_collection() before writing documents.

        The embedding parameter defaults to 'auto' which automatically detects the best embedding
        model from your environment configuration. You typically don't need to specify it.

        Prerequisites: None (first step in database setup)

        Next steps:
        - Create collection: create_collection(database="name", collection="name")
        - Write documents: write_documents(database="name", documents=[...])

        Common errors:
        - Database already exists: Use delete_database() to remove existing database first
        - Invalid database_type: Must be 'milvus' or 'weaviate'
        - Missing API key: Set OPENAI_API_KEY or configure custom embeddings
        """
        try:
            logger.info(f"Creating vector database: {database} of type {database_type}")
            logger.info(
                f"Current vector_databases keys: {list(vector_databases.keys())}"
            )

            # Validate database type
            if database_type not in ["milvus", "weaviate"]:
                return error_response(
                    error_code="PARAM_INVALID_VALUE",
                    message=f"Invalid database_type: '{database_type}'",
                    details={
                        "database_type": database_type,
                        "valid_types": ["milvus", "weaviate"],
                    },
                    suggestion="Use database_type='milvus' or database_type='weaviate'",
                )

            # Check if database with this name already exists
            if database in vector_databases:
                logger.error(f"Database '{database}' already exists")
                return error_response(
                    error_code="DB_ALREADY_EXISTS",
                    message=f"Database '{database}' already exists",
                    details={
                        "database": database,
                        "existing_databases": list(vector_databases.keys()),
                    },
                    suggestion=f"Use a different name or delete the existing database: delete_database(database='{database}', force=True)",
                )

            # Create new database instance (no default collection)
            vector_databases[database] = create_vector_database(database_type)

            logger.info(
                f"Registered database. Updated vector_databases keys: {list(vector_databases.keys())}"
            )

            logger.info(
                f"Created database. Updated vector_databases keys: {list(vector_databases.keys())}"
            )

            # Auto-initialize the connection (merged setup step)
            db = vector_databases[database]

            # Auto-detect embedding from environment
            resolved_embedding = embedding
            if embedding == "auto":
                # Check if custom embedding is configured
                if os.getenv("CUSTOM_EMBEDDING_URL") and os.getenv(
                    "CUSTOM_EMBEDDING_MODEL"
                ):
                    resolved_embedding = "custom_local"
                    logger.info("Auto-detected custom_local embedding from environment")
                else:
                    resolved_embedding = "text-embedding-ada-002"
                    logger.info(
                        "No custom embedding configured, using default OpenAI (text-embedding-ada-002)"
                    )

            # Call setup to initialize the database connection
            if hasattr(db, "setup"):
                ok, res = await run_with_timeout(
                    db.setup(embedding=resolved_embedding),
                    "setup_database",
                    get_timeout("setup_database"),
                )
                if not ok:
                    # Check if it's an embedding error
                    if "embedding" in str(res).lower():
                        supported: list[str] = []
                        if hasattr(db, "supported_embeddings"):
                            supported_attr = getattr(db, "supported_embeddings")
                            if callable(supported_attr):
                                result = supported_attr()
                                supported = result if isinstance(result, list) else []
                            elif isinstance(supported_attr, list):
                                supported = supported_attr
                        return error_response(
                            error_code="CONFIG_EMBEDDING_INVALID",
                            message=f"Invalid embedding model: '{resolved_embedding}'",
                            details={
                                "embedding": resolved_embedding,
                                "supported_embeddings": supported,
                            },
                            suggestion=f"Use one of the supported embeddings: {', '.join(supported)}",
                        )
                    return error_response(
                        error_code="DB_CONNECTION_FAILED",
                        message=f"Failed to initialize database connection: {str(res)}",
                        details={"database": database, "error": str(res)},
                    )

            return database_created_response(
                database=database,
                database_type=database_type,
                embedding=resolved_embedding,
                connection_status="connected",
                collections_count=0,
            )
        except Exception as e:
            error_msg = f"Failed to create vector database '{database}': {str(e)}"
            logger.error(error_msg)
            return error_response(
                error_code="DB_CREATION_FAILED",
                message=error_msg,
                details={"database": database, "database_type": database_type},
            )

    @app.tool()
    async def write_documents(
        collection: str = Field(
            ..., description="Name of the collection to write documents to"
        ),
        documents: list[dict[str, Any]] = Field(
            ...,
            description=(
                "List of documents to write. Each document is a dict with:\n"
                "- 'text' (required): Document content\n"
                "- 'url' (optional): Source URL or identifier (auto-generated from text hash if empty)\n"
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
                "If 'url' is empty or not provided, it will be auto-generated from the text content hash."
            ),
        ),
    ) -> str:
        """
        Write documents to a vector database with automatic URL fetching and format conversion.

        Collection Management:
        - If the collection exists: Documents are added to it
        - If the collection doesn't exist: You'll get a COLL_NOT_FOUND error with available collections
        - To create a new collection: Use create_collection() first

        Document Format:
        Each document in the 'documents' list should be a dict with:
        - 'text' (required): Document content
        - 'url' (optional): Source URL or identifier (recommended for document identification)
        - 'metadata' (optional): Additional metadata dict (can include 'doc_name' for human-readable names)

        Key Features:
        - URL Fetching: Automatically fetches content from http:// or https:// URLs
        - Format Detection: Auto-detects HTML, PDF, Markdown, and plain text
        - Format Conversion: Converts HTML (via html2text) and PDF (via PyPDF2) to plain text
        - Security: Only HTTP/HTTPS allowed; file:// paths restricted to CWD and subdirectories
        - Auto-generated URLs: If 'url' is empty, generates unique ID from text content hash
        - Metadata Enrichment: Fetched documents get enriched with content_type, fetched_at, etc.
        - Embedding Model: Configured at collection creation time, automatically included in chunk metadata

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

        Returns:
        JSON string with:
        - status: "success" or "error"
        - message: Summary of operation
        - data: Statistics about documents and chunks written
        - metadata: Collection info and sample query suggestion

        Common Errors:
        - COLL_NOT_FOUND: Collection doesn't exist - create it first with create_collection()
        - DOC_WRITE_FAILED: Write operation failed - check error details
        """
        # Internal: database defaults to collection name
        database: str | None = None
        if database is None:
            database = collection
            logger.info(
                f"Database parameter not provided, defaulting to collection name: {database}"
            )

        db = get_database_by_name(database)

        stats: Any = None
        try:
            # Pass collection_name directly to write_documents (stateless)
            ok, stats_any = await run_with_timeout(
                db.write_documents(documents, collection_name=collection),
                "write_documents",
                get_timeout("write_bulk"),
            )
            if not ok:
                # Enhanced error message
                error_msg = str(stats_any)
                if (
                    "collection" in error_msg.lower()
                    and "not found" in error_msg.lower()
                ):
                    # Get available collections
                    ok_list, collections_any = await run_with_timeout(
                        db.list_collections(),
                        "list_collections",
                        get_timeout("list_collections"),
                    )
                    available = (
                        cast("list[str]", collections_any)
                        if ok_list and isinstance(collections_any, list)
                        else []
                    )

                    return error_response(
                        error_code="COLL_NOT_FOUND",
                        message=f"Collection '{collection}' not found",
                        details={
                            "collection": collection,
                            "database": database,
                            "available_collections": available,
                        },
                        suggestion=f"Create the collection first: create_collection(database='{database}', collection='{collection}')",
                    )

                return error_response(
                    error_code="DOC_WRITE_FAILED",
                    message=f"Failed to write documents: {error_msg}",
                    details={"database": database, "collection": collection},
                )
            stats = stats_any
        except Exception as e:
            error_msg = f"Failed to write documents: {str(e)}"

            # Enhanced error for collection issues
            if "collection" in str(e).lower():
                return error_response(
                    error_code="COLL_NOT_FOUND",
                    message=error_msg,
                    details={"database": database, "collection": collection},
                    suggestion=f"Create the collection first: create_collection(database='{database}', collection='{collection}')",
                )

            return error_response(
                error_code="DOC_WRITE_FAILED",
                message=error_msg,
                details={"database": database, "error": str(e)},
            )

        # Get collection info for embedding model details
        post_info: dict[str, Any] | None = None
        try:
            ok, post_info_any = await run_with_timeout(
                db.get_collection_info(collection),
                "get_collection_info",
                get_timeout("get_collection_info"),
            )
            post_info = cast("dict[str, Any]", post_info_any) if ok else None
        except Exception:
            post_info = None

        # Extract stats - backend returns "chunks", not "chunks_written"
        chunks_created = (
            stats.get("chunks", stats.get("chunks_written", 0))
            if isinstance(stats, dict)
            else 0
        )
        embedding_model = (
            (post_info or {}).get("embedding_details", {}).get("name", "unknown")
            if post_info
            else "unknown"
        )
        collection_name = (
            (post_info or {}).get("name", collection) if post_info else collection
        )

        # Extract document IDs from stats if available
        document_ids = stats.get("document_ids", []) if isinstance(stats, dict) else []

        return documents_written_response(
            collection=collection_name,
            documents_written=len(documents),
            chunks_created=chunks_created,
            embedding_model=embedding_model,
            document_ids=document_ids,
        )

    @app.tool()
    async def delete_documents(
        collection: str = Field(
            ..., description="Name of the collection containing the documents"
        ),
        document_ids: list[str] = Field(
            ..., description="List of document IDs to delete"
        ),
        force: bool = Field(
            default=False,
            description="If False, returns error if operation would delete data. If True, proceeds with deletion.",
        ),
    ) -> str:
        """Delete documents from a collection in a vector database by their IDs.

        Safety: By default (force=False), this operation requires explicit confirmation.
        Set force=True to proceed with deletion.

        Note: If a document_id doesn't exist, the operation continues without error.
        The response indicates how many documents were successfully deleted.
        """
        # Internal: database defaults to collection name
        database: str | None = None
        if database is None:
            database = collection
            logger.info(
                f"Database parameter not provided, defaulting to collection name: {database}"
            )

        db = get_database_by_name(database)

        # Set the collection context
        db.collection_name = collection

        # Safety check: require force=True for deletion
        if not force:
            return error_response(
                error_code="DOC_DELETE_REQUIRES_FORCE",
                message=f"Cannot delete {len(document_ids)} document{'s' if len(document_ids) != 1 else ''} - force=True required",
                details={
                    "database": database,
                    "collection": collection,
                    "document_count": len(document_ids),
                    "document_ids": document_ids[:5]
                    if len(document_ids) > 5
                    else document_ids,
                },
                suggestion=f"Use force=True to proceed: delete_documents(database='{database}', collection='{collection}', document_ids=[...], force=True)",
            )

        ok, _ = await run_with_timeout(
            db.delete_documents(document_ids), "delete", get_timeout("delete")
        )
        if not ok:
            return error_response(
                error_code="DOC_DELETE_FAILED",
                message=f"Failed to delete documents from collection '{collection}'",
                details={
                    "database": database,
                    "collection": collection,
                    "document_ids": document_ids,
                },
            )

        return documents_deleted_response(
            collection=collection,
            documents_deleted=len(document_ids),
            forced=True,
        )

    @app.tool()
    async def get_document(
        collection: str = Field(
            ..., description="Name of the collection containing the document"
        ),
        document_id: str = Field(
            ..., description="Unique identifier of the document to retrieve"
        ),
    ) -> str:
        """Get a specific document by ID from a collection in a vector database."""
        # Internal: database defaults to collection name
        database: str | None = None
        if database is None:
            database = collection
            logger.info(
                f"Database parameter not provided, defaulting to collection name: {database}"
            )

        db = get_database_by_name(database)

        # Check if the collection exists
        ok, collections_any = await run_with_timeout(
            db.list_collections(), "list_collections", get_timeout("list_collections")
        )
        collections = (
            cast("list[str]", collections_any)
            if ok and isinstance(collections_any, list)
            else []
        )
        if collection not in collections:
            return error_response(
                error_code="COLL_NOT_FOUND",
                message=f"Collection '{collection}' not found",
                details={
                    "collection": collection,
                    "database": database,
                    "available_collections": collections,
                },
                suggestion="Check available collections: list_collections()",
            )

        try:
            # Get the document using the new get_document method
            ok, document_any = await run_with_timeout(
                db.get_document(document_id, collection),
                "get_document",
                get_timeout("list_documents"),
            )
            if not ok:
                return error_response(
                    error_code="DOC_NOT_FOUND",
                    message=f"Document '{document_id}' not found in collection '{collection}'",
                    details={
                        "document_id": document_id,
                        "collection": collection,
                        "database": database,
                    },
                )
            document: dict[str, Any] = cast("dict[str, Any]", document_any)

            return success_response(
                message=f"Retrieved document '{document_id}'",
                data={
                    "document_id": document_id,
                    "document": document,
                },
                operation="get_document",
                database=database,
                collection=collection,
            )
        except ValueError as e:
            return error_response(
                error_code="DOC_RETRIEVAL_FAILED",
                message=str(e),
                details={
                    "document_id": document_id,
                    "collection": collection,
                    "database": database,
                },
            )
        except Exception as e:
            return error_response(
                error_code="DOC_RETRIEVAL_FAILED",
                message=f"Failed to retrieve document '{document_id}': {str(e)}",
                details={
                    "document_id": document_id,
                    "collection": collection,
                    "database": database,
                },
            )

    @app.tool()
    async def delete_collection(
        collection: str = Field(..., description="Name of the collection to delete"),
        force: bool = Field(
            default=False,
            description="If False, checks if collection is empty before deletion. If True, deletes regardless of contents.",
        ),
    ) -> str:
        """Delete an entire collection from a vector database.

        Safety: By default (force=False), this operation checks if the collection is empty.
        If the collection contains documents, it will return an error with statistics.
        Set force=True to delete the collection and all its contents.
        """
        # Internal: database defaults to collection name
        database: str | None = None
        if database is None:
            database = collection
            logger.info(
                f"Database parameter not provided, defaulting to collection name: {database}"
            )

        if database in vector_databases:
            db = get_database_by_name(database)

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
            if collection is None or collection not in collections:
                return error_response(
                    error_code="COLL_NOT_FOUND",
                    message=f"Collection '{collection}' not found",
                    details={
                        "collection": collection,
                        "database": database,
                        "available_collections": collections,
                    },
                    suggestion="Check available collections: list_collections()",
                )

            # Safety check: if force=False, check if collection is empty
            documents_deleted = 0
            if not force:
                # Get document count for the collection
                ok, count_any = await run_with_timeout(
                    db.count_documents_in_collection(collection),
                    "count_documents",
                    get_timeout("list_documents"),
                )
                doc_count = (
                    cast("int", count_any) if ok and isinstance(count_any, int) else 0
                )

                if doc_count > 0:
                    return error_response(
                        error_code="COLL_NOT_EMPTY",
                        message=f"Cannot delete collection '{collection}' - it contains {doc_count} documents",
                        details={
                            "collection": collection,
                            "database": database,
                            "document_count": doc_count,
                        },
                        suggestion=f"Use force=True to delete: delete_collection(database='{database}', collection='{collection}', force=True)",
                    )
            else:
                # Count documents for response
                ok, count_any = await run_with_timeout(
                    db.count_documents_in_collection(collection),
                    "count_documents",
                    get_timeout("list_documents"),
                )
                documents_deleted = (
                    cast("int", count_any) if ok and isinstance(count_any, int) else 0
                )

            ok, _ = await run_with_timeout(
                db.delete_collection(collection),
                "delete",
                get_timeout("delete"),
            )
            if not ok:
                return error_response(
                    error_code="COLL_DELETE_FAILED",
                    message=f"Failed to delete collection '{collection}' from database '{database}'",
                    details={"collection": collection, "database": database},
                )

            # CRITICAL FIX: Remove from in-memory registry after successful deletion
            # In the current architecture, each "database" entry represents a collection
            # When we delete the collection from the backend, we must also remove it from memory
            if database in vector_databases:
                del vector_databases[database]
                logger.info(
                    f"Removed database '{database}' from in-memory registry after collection deletion"
                )

            return collection_deleted_response(
                collection=collection,
                documents_deleted=documents_deleted,
                forced=force,
            )
        try:
            from src.db.vector_db_milvus import MilvusVectorDatabase

            if collection is None:
                return error_response(
                    error_code="PARAM_MISSING",
                    message="collection parameter is required",
                    details={"parameter": "collection"},
                )
            temp_db = MilvusVectorDatabase(collection_name=collection)
            ok, _ = await run_with_timeout(
                temp_db.delete_collection(collection),
                "delete",
                get_timeout("delete"),
            )
            if not ok:
                return error_response(
                    error_code="COLL_DELETE_FAILED",
                    message=f"Failed to delete collection '{collection}' from Milvus (untracked)",
                    details={"collection": collection},
                )
            return success_response(
                message=f"Successfully dropped collection '{collection}' from Milvus (untracked)",
                data={"collection": collection, "untracked": True},
                operation="delete_collection",
            )
        except Exception as e:
            return error_response(
                error_code="COLL_DELETE_FAILED",
                message=f"Delete collection failed: {str(e)}",
                details={"collection": collection, "error": str(e)},
            )

    # DISABLED: Confusing terminology - "database" actually means "collection"
    # Use delete_collection() instead for clearer semantics
    # @app.tool()
    async def delete_database_DISABLED(
        database: str = Field(
            ..., description="Name of the vector database instance to delete"
        ),
        force: bool = Field(
            default=False,
            description="If False, checks if database has collections before deletion. If True, deletes regardless of contents.",
        ),
    ) -> str:
        """Delete a vector database and clean up all resources.

        Safety: By default (force=False), this operation checks if the database has collections.
        If the database contains collections, it will return an error with statistics.
        Set force=True to delete the database and all its collections.
        """
        if database in vector_databases:
            db = get_database_by_name(database)

            # Safety check: if force=False, check if database has collections
            collections_deleted = 0
            if not force:
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

                if len(collections) > 0:
                    return error_response(
                        error_code="DB_NOT_EMPTY",
                        message=f"Cannot delete database '{database}' - it contains {len(collections)} collections",
                        details={
                            "database": database,
                            "collections_count": len(collections),
                            "collections": collections,
                        },
                        suggestion=f"Use force=True to delete: delete_database(database='{database}', force=True)",
                    )
            else:
                # Count collections for response
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
                collections_deleted = len(collections)

            ok, _ = await run_with_timeout(
                db.cleanup(), "cleanup", get_timeout("cleanup")
            )
            if not ok:
                return error_response(
                    error_code="DB_CLEANUP_FAILED",
                    message=f"Failed to cleanup vector database '{database}'",
                    details={"database": database},
                )
            del vector_databases[database]

            return database_deleted_response(
                database=database,
                collections_deleted=collections_deleted,
                forced=force,
            )
        try:
            from src.db.vector_db_milvus import MilvusVectorDatabase

            temp_db = MilvusVectorDatabase(collection_name=database)
            ok, _ = await run_with_timeout(
                temp_db.delete_collection(database),
                "cleanup",
                get_timeout("cleanup"),
            )
            if not ok:
                return error_response(
                    error_code="COLL_DELETE_FAILED",
                    message=f"Failed to cleanup (drop) collection '{database}' from Milvus (untracked)",
                    details={"collection": database},
                )
            return success_response(
                message=f"Successfully dropped collection '{database}' from Milvus (untracked)",
                data={"collection": database, "untracked": True},
                operation="delete_database",
            )
        except Exception as e:
            return error_response(
                error_code="DB_CLEANUP_FAILED",
                message=f"Cleanup failed: {str(e)}",
                details={"database": database, "error": str(e)},
            )

    @app.tool()
    async def get_config(
        include_embeddings: bool = Field(
            default=False,
            description="Include list of supported embedding models in the response",
        ),
        include_chunking: bool = Field(
            default=False,
            description="Include list of supported chunking strategies in the response",
        ),
        include_collections: bool = Field(
            default=False,
            description="Include detailed information about each collection including their embedding configurations",
        ),
    ) -> str:
        """Get system-wide configuration and capabilities.

        Returns backend type (Milvus/Weaviate), collections count, and total document count.

        Optionally includes:
        - Supported embedding models (include_embeddings=True) - Shows what embeddings are available
        - Supported chunking strategies (include_chunking=True) - Shows chunking options
        - Collection summaries (include_collections=True) - Brief overview of all collections

        IMPORTANT: To get detailed embedding configuration for a SPECIFIC collection,
        use get_collection(collection="name") instead. That tool provides:
        - Exact embedding model being used
        - Custom embedding configuration (URL, model name, API keys)
        - Vector dimensions
        - Document counts

        Use get_config() for:
        - Discovering what embedding models are supported
        - Seeing custom embedding environment configuration
        - Getting an overview of all collections

        Use get_collection() for:
        - Getting embedding details for a specific collection
        - Seeing what model a collection actually uses
        """
        # Internal: database defaults to first registered (excluding _health_check)
        database: str | None = None
        if database is None:
            database = get_default_database_name()
            # Skip _health_check database if it's the only one
            if database == "_health_check" and len(vector_databases) > 1:
                # Find first non-health-check database
                for db_name in vector_databases:
                    if db_name != "_health_check":
                        database = db_name
                        break

            if database is None or (
                database == "_health_check" and len(vector_databases) == 1
            ):
                return error_response(
                    error_code="NO_COLLECTIONS",
                    message="No collections registered yet",
                    suggestion="Create a collection first: create_collection(collection='name')",
                )
            logger.info(
                f"Database parameter not provided, using first registered database: {database}"
            )

        db = get_database_by_name(database)
        ok, cnt_any = await run_with_timeout(
            db.count_documents(), "count_documents", get_timeout("count_documents")
        )
        count = int(cnt_any) if ok else -1

        # Get collections list
        ok_colls, colls_any = await run_with_timeout(
            db.list_collections(), "list_collections", get_timeout("list_collections")
        )
        collections = (
            cast("list[str]", colls_any)
            if ok_colls and isinstance(colls_any, list)
            else []
        )

        data: dict[str, Any] = {
            "database": database,
            "database_type": db.db_type,
            "collections_count": len(collections),
            "total_documents": count,
        }

        if include_embeddings:
            embeddings = db.supported_embeddings()
            data["supported_embeddings"] = embeddings

            # Add custom embedding environment configuration if present
            custom_url = os.getenv("CUSTOM_EMBEDDING_URL")
            custom_model = os.getenv("CUSTOM_EMBEDDING_MODEL")
            custom_size = os.getenv("CUSTOM_EMBEDDING_VECTORSIZE")

            if custom_url or custom_model or custom_size:
                data["custom_embedding_config"] = {
                    "url": custom_url,
                    "model": custom_model,
                    "vector_size": custom_size,
                    "configured": bool(custom_url and custom_model and custom_size),
                    "note": "This is the environment configuration. Use get_collection(collection='name') to see which collections actually use this configuration.",
                }

        if include_chunking:
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
            data["supported_chunking"] = {
                "strategies": strategies,
                "notes": defaults_behavior,
            }

        # Add detailed collection information if requested
        if include_collections and collections:
            collection_details = []
            for coll_name in collections:
                try:
                    ok_info, info_any = await run_with_timeout(
                        db.get_collection_info(coll_name),
                        "get_collection_info",
                        get_timeout("get_collection_info"),
                    )
                    if ok_info and isinstance(info_any, dict):
                        info = cast("dict[str, Any]", info_any)
                        coll_data: dict[str, Any] = {
                            "name": coll_name,
                        }

                        # Add embedding details
                        if "embedding_details" in info:
                            emb = info["embedding_details"]
                            coll_data["embedding"] = {
                                "model": emb.get("name", "unknown"),
                                "provider": emb.get("provider", "unknown"),
                                "vector_size": emb.get("vector_size"),
                            }
                            # Add custom embedding config if present
                            if emb.get("config"):
                                coll_data["embedding"]["config"] = emb["config"]

                        # Add document/chunk counts
                        if "document_count" in info:
                            coll_data["document_count"] = info["document_count"]
                        if "chunk_count" in info:
                            coll_data["chunk_count"] = info["chunk_count"]

                        # Add chunking config if present
                        if "chunking_config" in info:
                            coll_data["chunking_config"] = info["chunking_config"]

                        collection_details.append(coll_data)
                except Exception as e:
                    logger.warning(
                        f"Failed to get info for collection '{coll_name}': {e}"
                    )
                    collection_details.append({"name": coll_name, "error": str(e)})

            data["collections"] = collection_details

        return success_response(
            message=f"Database '{database}' information",
            data=data,
            operation="get_database_info",
            database=database,
        )

    @app.tool()
    async def list_collections() -> str:
        """
        List all collections in the vector database.

        Returns a list of all collections with their embedding models.
        Each collection is an independent vector database that stores documents.

        Response includes:
        - Collection names
        - Embedding model for each collection
        - Total count of collections

        Use this to see what collections exist before performing operations like
        write_documents, query, or delete_collection.
        """
        # Internal: database defaults to first registered
        database: str | None = None
        if database is None:
            database = get_default_database_name()
            if database is None:
                # Try to bootstrap a connection to check if backend is available
                try:
                    db = get_database_by_name("_health_check", auto_bootstrap=True)
                    # Test backend connectivity
                    ok, colls_any = await run_with_timeout(
                        db.list_collections(),
                        "list_collections",
                        get_timeout("list_collections"),
                    )
                    if not ok:
                        # Backend unreachable
                        return error_response(
                            error_code="BACKEND_UNAVAILABLE",
                            message="Vector database backend is not responding",
                            details={"timeout": get_timeout("list_collections")},
                            suggestion="Check that your vector database (Milvus/Weaviate) is running and accessible. Verify MILVUS_URI or WEAVIATE_URL environment variables.",
                        )
                    # Backend is reachable but no collections exist
                    return error_response(
                        error_code="NO_COLLECTIONS",
                        message="No collections exist yet",
                        suggestion="Create a collection first: create_collection(collection='name')",
                    )
                except Exception as e:
                    # Backend connection failed
                    return error_response(
                        error_code="BACKEND_CONNECTION_FAILED",
                        message=f"Failed to connect to vector database backend: {str(e)}",
                        suggestion="Ensure your vector database is running and environment variables (MILVUS_URI or WEAVIATE_URL) are correctly configured.",
                    )
            logger.info(
                f"Database parameter not provided, using first registered database: {database}"
            )

        db = get_database_by_name(database)
        ok, colls_any = await run_with_timeout(
            db.list_collections(), "list_collections", get_timeout("list_collections")
        )
        collections = (
            cast("list[str]", colls_any) if ok and isinstance(colls_any, list) else []
        )

        if not collections:
            return success_response(
                message="No collections found",
                data={
                    "collections": [],
                    "total_collections": 0,
                },
                operation="list_collections",
                database=database,
            )

        # Build collection details list
        collections_data = []
        for coll in collections:
            coll_data = {"name": coll}
            # Try to get basic info for each collection
            try:
                ok_info, info_any = await run_with_timeout(
                    db.get_collection_info(coll),
                    "get_collection_info",
                    get_timeout("get_collection_info"),
                )
                if ok_info and isinstance(info_any, dict):
                    info = cast("dict[str, Any]", info_any)
                    if "embedding_details" in info:
                        emb = info["embedding_details"]
                        coll_data["embedding"] = emb.get("name", "unknown")
                    if "created_at" in info:
                        coll_data["created_at"] = info["created_at"]
            except Exception:
                pass  # Best effort
            collections_data.append(coll_data)

        return success_response(
            message=f"Found {len(collections)} collection{'s' if len(collections) != 1 else ''}",
            data={
                "collections": collections_data,
                "total_collections": len(collections),
            },
            operation="list_collections",
            database=database,
        )

    @app.tool()
    async def get_collection(
        collection: str | None = Field(
            default=None,
            description="Name of the collection (defaults to first registered if not provided)",
        ),
        include_count: bool = Field(
            default=False,
            description="Include document count in the response",
        ),
    ) -> str:
        """Get detailed information about a specific collection.

        This is the PRIMARY tool for getting embedding configuration for a collection.

        Returns:
        - Collection name
        - Embedding model details (model name, provider, vector size, custom config)
        - Document and chunk counts
        - Chunking configuration
        - Timestamps (created_at, last_updated)

        Use this tool when you need to know:
        - What embedding model a collection uses
        - Custom embedding configuration (URL, model name, etc.)
        - How many documents are in the collection
        - What chunking strategy is configured

        Example: get_collection(collection="mydocs")
        """
        # Internal: database defaults to collection name or first registered
        database: str | None = None
        if database is None:
            if collection is not None:
                database = collection
                logger.info(
                    f"Database parameter not provided, defaulting to collection name: {database}"
                )
            else:
                database = get_default_database_name()
                if database is None:
                    return error_response(
                        error_code="NO_DATABASES",
                        message="No databases registered",
                        suggestion="Register a database first: register_database(database='name', database_type='milvus')",
                    )
                logger.info(
                    f"Neither database nor collection provided, using first registered database: {database}"
                )

        db = get_database_by_name(database)
        # Always delegate to the backend which can surface metadata even if
        # the collection doesn't exist (including chunking config and errors)
        if collection is None:
            ok, info_any = await run_with_timeout(
                db.get_collection_info(),
                "get_collection_info",
                get_timeout("get_collection_info"),
            )
        else:
            ok, info_any = await run_with_timeout(
                db.get_collection_info(collection),
                "get_collection_info",
                get_timeout("get_collection_info"),
            )
        if not ok:
            return error_response(
                error_code="COLL_INFO_FAILED",
                message=f"Failed to get collection info: {str(info_any)}",
                details={"database": database, "collection": collection},
            )
        info: dict[str, Any] = cast("dict[str, Any]", info_any)

        # Build structured response data
        coll_name = info.get("name", collection or "default")
        data: dict[str, Any] = {
            "name": coll_name,
        }

        # Add document/chunk counts
        if "document_count" in info:
            data["document_count"] = info["document_count"]
        if "chunk_count" in info:
            data["chunk_count"] = info["chunk_count"]

        # Add document count if requested and not already present
        if include_count and "document_count" not in data:
            ok_count, count_any = await run_with_timeout(
                db.count_documents(), "count_documents", get_timeout("read")
            )
            if ok_count:
                count = int(count_any) if count_any is not None else 0
                data["document_count"] = count

        # Add embedding details
        if "embedding_details" in info:
            emb = info["embedding_details"]
            data["embedding"] = {
                "model": emb.get("name", "unknown"),
                "provider": emb.get("provider", "unknown"),
                "vector_size": emb.get("vector_size"),
            }
            # Add custom embedding URL if present
            if "url" in emb:
                data["embedding"]["url"] = emb["url"]
            # Add full custom embedding config if present
            if "config" in emb and emb["config"]:
                data["embedding"]["config"] = emb["config"]

        # Add chunking details (check both "chunking_config" and "chunking" keys)
        chunk_info = info.get("chunking_config") or info.get("chunking")
        if chunk_info:
            data["chunking"] = {
                "strategy": chunk_info.get("strategy", "unknown"),
                "chunk_size": chunk_info.get("chunk_size"),
                "overlap": chunk_info.get("overlap"),
            }
        else:
            # If no chunking config stored, show default (Phase 8.5 default is Sentence)
            data["chunking"] = {
                "strategy": "Sentence",
                "chunk_size": 512,
                "overlap": 0,
                "note": "Default chunking configuration (not explicitly set during collection creation)",
            }

        # Add timestamps if available
        if "created_at" in info:
            data["created_at"] = info["created_at"]
        if "last_updated" in info:
            data["last_updated"] = info["last_updated"]

        return success_response(
            message=f"Collection '{coll_name}' information",
            data=data,
            operation="get_collection_info",
            database=database,
            collection=coll_name,
        )

    @app.tool()
    async def create_collection(
        collection: str = Field(..., description="Name of the collection to create"),
        database: str | None = Field(
            default=None,
            description="**Internal use only** - Auto-resolved to collection name. Do not specify this parameter.",
        ),
        embedding: str = Field(
            default="auto",
            description=(
                "Embedding model to use. Options: 'auto' (auto-detect from environment), "
                "'text-embedding-ada-002', 'text-embedding-3-small', 'text-embedding-3-large', "
                "or 'custom_local' (requires CUSTOM_EMBEDDING_URL, CUSTOM_EMBEDDING_MODEL, and "
                "CUSTOM_EMBEDDING_VECTORSIZE environment variables). 'auto' will use custom_local "
                "if configured, otherwise falls back to OpenAI text-embedding-ada-002."
            ),
        ),
        chunking_config: dict[str, Any] | None = Field(
            default=None,
            description="Optional chunking configuration for the collection. Example: {'strategy':'Sentence','parameters':{'chunk_size':256,'overlap':1}}",
        ),
    ) -> str:
        """
        Create a new collection in a vector database.

        This is the primary tool for setting up a new collection. It automatically:
        1. Creates or bootstraps the database connection if needed (Phase 8.5)
        2. Auto-detects embedding model from environment variables
        3. Registers the collection for immediate use

        All documents in the collection will use the same embedding model configured here.

        Embedding Auto-Detection (embedding="auto"):
        - Checks for custom embedding environment variables:
          * CUSTOM_EMBEDDING_URL (e.g., http://localhost:11434/api/embeddings)
          * CUSTOM_EMBEDDING_MODEL (e.g., nomic-embed-text)
          * CUSTOM_EMBEDDING_VECTORSIZE (e.g., 768)
        - If all three are set: Uses custom_local embedding
        - Otherwise: Falls back to text-embedding-ada-002 (requires OPENAI_API_KEY)

        Parameters:
        - collection: Name of the collection to create (required)
        - database: **Internal use only** - Auto-resolved, do not specify
        - embedding: Embedding model (default: "auto" - auto-detects from environment)
        - chunking_config: Optional chunking configuration (default: Sentence-based, 512 chars)

        Next steps:
        - Write documents: write_documents(collection="docs", documents=[...])
        - Query documents: query(query="...", collection="docs")

        Common errors:
        - COLL_ALREADY_EXISTS: Collection already exists - use delete_collection() first
        - CONFIG_EMBEDDING_INVALID: Invalid embedding model - use get_config(include_embeddings=True)
        - DB_BOOTSTRAP_FAILED: Failed to create database connection - check environment variables
        - Missing API key: Set OPENAI_API_KEY or configure custom embeddings
        """
        try:
            # Default database to collection name if not provided
            if database is None:
                database = collection
                logger.info(
                    f"Database parameter not provided, defaulting to collection name: {database}"
                )

            # Get or bootstrap database connection (Phase 8.5: auto-bootstrap)
            try:
                db = get_database_by_name(database, auto_bootstrap=True)
            except ValueError as e:
                return error_response(
                    error_code="DB_BOOTSTRAP_FAILED",
                    message=f"Failed to get or bootstrap database connection for '{database}'",
                    details={
                        "database": database,
                        "error": str(e),
                    },
                    suggestion="Ensure vector database environment variables are set correctly (MILVUS_URI or WEAVIATE_URL)",
                )

            # Auto-detect embedding from environment
            resolved_embedding = embedding
            if embedding == "auto":
                # Check if custom embedding is configured
                if os.getenv("CUSTOM_EMBEDDING_URL") and os.getenv(
                    "CUSTOM_EMBEDDING_MODEL"
                ):
                    resolved_embedding = "custom_local"
                    logger.info("Auto-detected custom_local embedding from environment")
                else:
                    resolved_embedding = "text-embedding-ada-002"
                    logger.info(
                        "No custom embedding configured, using default OpenAI (text-embedding-ada-002)"
                    )

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
            if collection in existing_collections:
                return error_response(
                    error_code="COLL_ALREADY_EXISTS",
                    message=f"Collection '{collection}' already exists",
                    details={
                        "collection": collection,
                        "database": database,
                        "existing_collections": existing_collections,
                    },
                    suggestion=f"Collection already exists. To add documents to it, use: write_document(collection='{collection}', text='...', document_name='...'). To replace it, first delete: delete_collection(collection='{collection}', force=True)",
                )

            # Create the collection using the create_collection method
            if hasattr(db, "create_collection"):
                ok, res = await run_with_timeout(
                    db.create_collection(
                        collection_name=collection,
                        embedding=resolved_embedding,
                        chunking_config=chunking_config,
                    ),
                    "create_collection",
                    get_timeout("create_collection"),
                )
                if not ok:
                    # Check for specific error types
                    error_str = str(res)
                    if "embedding" in error_str.lower():
                        supported: list[str] = []
                        if hasattr(db, "supported_embeddings"):
                            supported_attr = getattr(db, "supported_embeddings")
                            if callable(supported_attr):
                                result = supported_attr()
                                supported = result if isinstance(result, list) else []
                            elif isinstance(supported_attr, list):
                                supported = supported_attr
                        return error_response(
                            error_code="CONFIG_EMBEDDING_INVALID",
                            message=f"Invalid embedding model: '{resolved_embedding}'",
                            details={
                                "embedding": resolved_embedding,
                                "supported_embeddings": supported,
                            },
                            suggestion=f"Use one of the supported embeddings: {', '.join(supported)}",
                        )
                    elif (
                        "not initialized" in error_str.lower()
                        or "not connected" in error_str.lower()
                    ):
                        return error_response(
                            error_code="DB_NOT_INITIALIZED",
                            message=f"Database '{database}' is not initialized",
                            details={"database": database},
                            suggestion=f"The database connection may have failed during creation",
                        )
                    return error_response(
                        error_code="COLL_CREATION_FAILED",
                        message=f"Failed to create collection: {error_str}",
                        details={"database": database, "collection": collection},
                    )
            else:
                return error_response(
                    error_code="COLL_CREATION_FAILED",
                    message=f"Database '{database}' does not support create_collection method",
                    details={"database": database, "database_type": db.db_type},
                )

            # Determine chunking strategy for response
            chunking_strategy = "Sentence"  # default
            if chunking_config and "strategy" in chunking_config:
                chunking_strategy = chunking_config["strategy"]

            return collection_created_response(
                database=database,
                collection=collection,
                embedding=resolved_embedding,
                chunking_strategy=chunking_strategy,
            )

        except Exception as e:
            error_msg = f"Failed to create collection '{collection}' in vector database '{database}': {str(e)}"
            logger.error(error_msg)
            return error_response(
                error_code="COLL_CREATION_FAILED",
                message=error_msg,
                details={"database": database, "collection": collection},
            )

    @app.tool()
    async def query(
        query: str = Field(..., description="The query string to search for"),
        limit: int = Field(
            default=5, description="Maximum number of results to consider (1-100)"
        ),
        collection: str | None = Field(
            default=None, description="Optional collection name to search in"
        ),
    ) -> str:
        """
        Query a vector database using semantic search with LLM summarization.

        Returns a natural language summary of relevant documents, ideal for conversational
        interfaces where you want a synthesized answer rather than raw search results.

        Parameters:
        - query: The search query string (required)
        - limit: Number of results to consider (1-100), default 5
        - collection: Optional collection name (uses first registered if not provided)

        Returns:
        JSON response with:
        - status: "success" or "error"
        - message: Operation summary
        - data:
          - query: The search query
          - summary: Natural language summary of results
          - limit: Number of results considered
        - metadata: Timestamp, operation, database, collection

        Difference from 'search':
        - query: Returns LLM-generated natural language summary
        - search: Returns raw results with scores, metadata, and citations

        Common errors:
        - NO_DATABASES: No collections registered - use refresh_databases()
        - DB_NOT_FOUND: Collection doesn't exist - check with list_collections()
        - COLL_NOT_FOUND: Collection not found - verify name
        - PARAM_INVALID_VALUE: Limit must be between 1 and 100
        - QUERY_FAILED: Query execution failed - check error details
        """
        try:
            # Internal: database defaults to collection name or first registered
            database: str | None = None
            if database is None:
                if collection is not None:
                    database = collection
                    logger.info(
                        f"Database parameter not provided, defaulting to collection name: {database}"
                    )
                else:
                    database = get_default_database_name()
                    if database is None:
                        return error_response(
                            error_code="NO_DATABASES",
                            message="No databases registered",
                            suggestion="Register a database first: register_database(database='name', database_type='milvus')",
                        )
                    logger.info(
                        f"Neither database nor collection provided, using first registered database: {database}"
                    )

            # Validate limit
            if limit < 1 or limit > 100:
                return error_response(
                    error_code="PARAM_INVALID_VALUE",
                    message=f"Invalid limit: {limit}. Must be between 1 and 100",
                    details={"limit": limit, "min": 1, "max": 100},
                    suggestion="Use a limit value between 1 and 100",
                )

            # Validate database exists
            if database not in vector_databases:
                available = list(vector_databases.keys())
                return error_response(
                    error_code="DB_NOT_FOUND",
                    message=f"Database '{database}' not found",
                    details={
                        "database": database,
                        "available_databases": available,
                    },
                    suggestion=f"Create the database first: create_database(database='{database}', database_type='milvus')",
                )

            db = get_database_by_name(database)
            kwargs: dict[str, Any] = {"limit": limit}
            if collection is not None:
                kwargs["collection_name"] = collection
            ok, response = await run_with_timeout(
                db.query(query, **kwargs), "query", get_timeout("query")
            )
            if not ok:
                error_str = str(response)
                if (
                    "collection" in error_str.lower()
                    and "not found" in error_str.lower()
                ):
                    # Get available collections
                    ok_list, colls_any = await run_with_timeout(
                        db.list_collections(),
                        "list_collections",
                        get_timeout("list_collections"),
                    )
                    available_colls = (
                        cast("list[str]", colls_any)
                        if ok_list and isinstance(colls_any, list)
                        else []
                    )
                    return error_response(
                        error_code="COLL_NOT_FOUND",
                        message=f"Collection '{collection or 'default'}' not found",
                        details={
                            "collection": collection or "default",
                            "database": database,
                            "available_collections": available_colls,
                        },
                        suggestion="Check available collections: list_collections()",
                    )
                return error_response(
                    error_code="QUERY_FAILED",
                    message=f"Query failed: {error_str}",
                    details={
                        "database": database,
                        "query": query,
                        "collection": collection,
                    },
                )

            # response is expected to be a string summary
            return success_response(
                message=f"Query completed for '{query}'",
                data={
                    "query": query,
                    "summary": str(response),
                    "limit": limit,
                },
                operation="query",
                database=database,
                collection=collection,
            )
        except KeyError:
            available = list(vector_databases.keys())
            db_name = locals().get("database", "unknown")
            return error_response(
                error_code="DB_NOT_FOUND",
                message=f"Database '{db_name}' not found",
                details={
                    "database": db_name,
                    "available_databases": available,
                },
                suggestion=f"Create the database first: create_database(database='{db_name}', database_type='milvus')",
            )
        except Exception as e:
            db_name = locals().get("database", "unknown")
            error_msg = f"Failed to query vector database '{db_name}': {str(e)}"
            logger.error(error_msg)
            return error_response(
                error_code="QUERY_FAILED",
                message=error_msg,
                details={
                    "database": db_name,
                    "query": query,
                    "collection": collection,
                },
            )

    @app.tool()
    async def search(
        query: str = Field(..., description="The query string to search for"),
        limit: int = Field(
            default=5, description="Maximum number of results to consider"
        ),
        collection: str | None = Field(
            default=None, description="Optional collection name to search in"
        ),
        min_score: float | None = Field(
            default=None,
            description="Minimum similarity score threshold (0-1). Results below this score are filtered out. Higher scores indicate better matches.",
        ),
        metadata_filters: dict[str, Any] | None = Field(
            default=None,
            description="Filter results by metadata fields. Provide a dictionary where keys are metadata field names and values are the required values. Only results matching ALL filters are returned. Example: {'doc_type': 'technical', 'language': 'python'}",
        ),
    ) -> str:
        """
        Search a vector database using vector similarity search with optional quality controls.

        Returns raw search results with scores and metadata, ideal for applications that need
        detailed result information or want to implement custom ranking/filtering.

        Parameters:
        - query: The search query string (required)
        - limit: Maximum number of results (default: 5)
        - collection: Optional collection name (uses first registered if not provided)
        - min_score: Minimum similarity score threshold (0-1, optional)
        - metadata_filters: Filter by metadata fields (dict, optional)

        Results include:
        - text: The document text content
        - url: Direct link to the source (top-level for easy access)
        - source_citation: Formatted citation string for easy reference
        - score/similarity: Relevance score normalized to 0-1 range (higher is better)
        - metadata: Additional document metadata
        - rank: Position in results (1-based)

        Score Interpretation:
        - 1.0: Perfect match
        - 0.8-0.99: Very high similarity
        - 0.6-0.79: Good similarity
        - 0.4-0.59: Moderate similarity
        - 0.0-0.39: Low similarity

        Use min_score to filter low-quality results and metadata_filters to narrow by document properties.

        Difference from 'query':
        - search: Returns raw results with scores, metadata, and citations
        - query: Returns LLM-generated natural language summary
        """
        try:
            # Internal: database defaults to collection name or first registered
            database: str | None = None
            if database is None:
                if collection is not None:
                    database = collection
                    logger.info(
                        f"Database parameter not provided, defaulting to collection name: {database}"
                    )
                else:
                    database = get_default_database_name()
                    if database is None:
                        return error_response(
                            error_code="NO_DATABASES",
                            message="No databases registered",
                            suggestion="Register a database first: register_database(database='name', database_type='milvus')",
                        )
                    logger.info(
                        f"Neither database nor collection provided, using first registered database: {database}"
                    )

            db = get_database_by_name(database)
            kwargs: dict[str, Any] = {"limit": limit}
            if collection is not None:
                kwargs["collection_name"] = collection
            if min_score is not None:
                kwargs["min_score"] = min_score
            if metadata_filters is not None:
                kwargs["metadata_filters"] = metadata_filters
            ok, response = await run_with_timeout(
                db.search(query, **kwargs), "search", get_timeout("search")
            )
            if not ok:
                return error_response(
                    error_code="SEARCH_FAILED",
                    message=f"Search failed: {str(response)}",
                    details={
                        "database": database,
                        "query": query,
                        "collection": collection,
                    },
                )

            # response should be a list of results
            results = response if isinstance(response, list) else []

            return search_results_response(
                query=query,
                results_count=len(results),
                results=results,
                collection=collection,
                limit=limit,
            )
        except KeyError:
            available = list(vector_databases.keys())
            db_name = locals().get("database", "unknown")
            return error_response(
                error_code="DB_NOT_FOUND",
                message=f"Database '{db_name}' not found",
                details={
                    "database": db_name,
                    "available_databases": available,
                },
                suggestion=f"Create the database first: create_database(database='{db_name}', database_type='milvus')",
            )
        except Exception as e:
            db_name = locals().get("database", "unknown")
            error_msg = f"Failed to search vector database '{db_name}': {str(e)}"
            logger.error(error_msg)
            return error_response(
                error_code="SEARCH_FAILED",
                message=error_msg,
                details={
                    "database": db_name,
                    "query": query,
                    "collection": collection,
                },
            )

    # DISABLED: Confusing terminology - lists "databases" but actually shows collections
    # Use list_collections() or get_collection_info() instead
    # @app.tool()
    async def list_databases_DISABLED() -> str:
        """List all registered vector database instances.

        Note: In the current architecture, each registered 'database' represents a collection.
        The terminology is confusing because 'database' parameter actually refers to a collection instance.
        This is a known limitation where database and collection concepts are conflated.
        """
        logger.info(
            f"Listing databases. Current vector_databases keys: {list(vector_databases.keys())}"
        )

        if not vector_databases:
            return success_response(
                message="No collections are currently registered. Use create_database() to register a collection.",
                data={"databases": [], "count": 0},
                operation="list_databases",
            )

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
        return success_response(
            message=f"Found {len(db_list)} vector database(s)",
            data={"databases": db_list, "count": len(db_list)},
            operation="list_databases",
        )

    @app.tool()
    async def refresh_databases() -> str:
        """Discover and register Milvus and Weaviate collections into the MCP server's in-memory registry."""
        try:
            added_milvus = await resync_vector_databases()
            added_weaviate = await resync_weaviate_databases()

            total_added = len(added_milvus) + len(added_weaviate)

            return success_response(
                message=f"Refreshed databases: {total_added} collection{'s' if total_added != 1 else ''} discovered",
                data={
                    "milvus": {"added": added_milvus, "count": len(added_milvus)},
                    "weaviate": {
                        "added": added_weaviate,
                        "count": len(added_weaviate),
                    },
                    "total_added": total_added,
                },
                operation="refresh_databases",
            )
        except Exception as e:
            logger.exception("Failed to run resync_databases tool")
            return error_response(
                error_code="REFRESH_FAILED",
                message=f"Failed to refresh databases: {str(e)}",
                details={"error": str(e)},
            )

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

    allowed_origins = [
        x.strip() for x in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    ]
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_methods=["GET", "POST"],
            allow_headers=[
                "mcp-protocol-version",
                "mcp-session-id",
                "Authorization",
                "Content-Type",
            ],
            expose_headers=["mcp-session-id"],
        )
    ]

    print(f"Starting FastMCP HTTP server on http://{host}:{port}")
    print(f"Open your browser to http://{host}:{port} to access the MCP server")
    print(f"📖 OpenAPI docs: http://{host}:{port}/docs")
    print(f"📚 ReDoc docs: http://{host}:{port}/redoc")

    custom_url = os.getenv("CUSTOM_EMBEDDING_URL")
    if custom_url:
        custom_model = os.getenv("CUSTOM_EMBEDDING_MODEL", "nomic-embed-text")
        print(f"   - URL:    {custom_url}")
        print(f"   - Model:  {custom_model}")
    else:
        print("🧬 Using default OpenAI embedding configuration.")
    await mcp_app.run_http_async(host=host, port=port, middleware=middleware)


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
