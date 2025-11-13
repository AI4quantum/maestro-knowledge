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
    async def create_database(
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
                return ErrorMessages.invalid_database_type(database_type)

            # Check if database with this name already exists
            if database in vector_databases:
                logger.error(f"Database '{database}' already exists")
                return ErrorMessages.database_already_exists(database)

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
                    resolved_embedding = "default"
                    logger.info(
                        "No custom embedding configured, using default (OpenAI)"
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
                        return ErrorMessages.invalid_embedding(
                            resolved_embedding, supported
                        )
                    return str(res)

            return f"Successfully created and initialized {database_type} vector database '{database}' with '{resolved_embedding}' embedding. Database created. No collections yet. Use create_collection() to add collections."
        except Exception as e:
            error_msg = f"Failed to create vector database '{database}': {str(e)}"
            logger.error(error_msg)
            return f"Error: {error_msg}"

    @app.tool()
    async def write_documents(
        database: str = Field(..., description="Name of the vector database instance"),
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
        ),
    ) -> str:
        """
        Write documents to a vector database with automatic URL fetching and format conversion.

        This tool supports both direct text provision (backwards compatible) and automatic
        fetching from URLs with format detection and conversion.

        IMPORTANT: You must specify the collection parameter to write to a specific collection.
        Collections are NOT created automatically - use create_collection() first.

        Key Features:
        - URL Fetching: Automatically fetches content from http:// or https:// URLs
        - Format Detection: Auto-detects HTML, PDF, Markdown, and plain text
        - Format Conversion: Converts HTML (via html2text) and PDF (via PyPDF2) to plain text
        - Security: Only HTTP/HTTPS allowed; file:// paths restricted to CWD and subdirectories
        - Backwards Compatible: Direct 'text' field still works; takes precedence over URL fetching
        - Metadata Enrichment: Fetched documents get enriched with content_type, fetched_at, etc.
        - Embedding Model: Configured at collection creation time, automatically included in chunk metadata

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

        Returns:
        JSON string with:
        - status: "ok" or "error"
        - message: Summary of operation
        - write_stats: Statistics about chunks written
        - collection_info: Updated collection information
        - sample_query_suggestion: Suggested query to test the collection

        Note: Embedding model is configured at collection creation time via setup_database or create_collection.
        """
        db = get_database_by_name(database)

        stats: Any = None
        try:
            ok, stats_any = await run_with_timeout(
                db.write_documents(documents),
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

                    error_msg = f"{error_msg}\n\nAvailable collections: {available}\n\n"
                    error_msg += f"Collection '{db.collection_name}' not found. "
                    error_msg += "Create it first with create_collection(database='{database}', collection='collection_name')."

                result = {"status": "error", "message": error_msg}
                return json.dumps(result, indent=2)
            stats = stats_any
        except Exception as e:
            error_msg = f"Failed to write documents: {str(e)}"

            # Enhanced error for collection issues
            if "collection" in str(e).lower():
                error_msg += f"\n\nTip: The collection must be created first with create_collection(database='{database}', collection='your_collection_name')."

            result = {
                "status": "error",
                "message": error_msg,
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
            for d in documents:
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
            "message": f"Wrote {len(documents)} document(s)",
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
    async def delete_documents(
        database: str = Field(..., description="Name of the vector database instance"),
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
        """
        db = get_database_by_name(database)

        # Set the collection context
        db.collection_name = collection

        # Safety check: require force=True for deletion
        if not force:
            return (
                f"Error: Cannot delete {len(document_ids)} documents from collection '{collection}' - "
                f"this operation requires force=True to proceed. "
                f"Use: delete_documents(database='{database}', collection='{collection}', "
                f"document_ids=[...], force=True)"
            )

        ok, _ = await run_with_timeout(
            db.delete_documents(document_ids), "delete", get_timeout("delete")
        )
        if not ok:
            return f"Error: Failed to delete documents from collection '{collection}' in database '{database}'"

        return (
            f"Successfully deleted {len(document_ids)} documents from collection '{collection}' "
            f"in database '{database}'. Warning: This operation cannot be undone."
        )

    @app.tool()
    async def get_document(
        database: str = Field(..., description="Name of the vector database instance"),
        collection: str = Field(
            ..., description="Name of the collection containing the document"
        ),
        document_id: str = Field(
            ..., description="Unique identifier of the document to retrieve"
        ),
    ) -> str:
        """Get a specific document by ID from a collection in a vector database."""
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
            raise ValueError(
                f"Collection '{collection}' not found in vector database '{database}'"
            )

        try:
            # Get the document using the new get_document method
            ok, document_any = await run_with_timeout(
                db.get_document(document_id, collection),
                "get_document",
                get_timeout("list_documents"),
            )
            if not ok:
                return str(document_any)
            document: dict[str, Any] = cast("dict[str, Any]", document_any)
            return f"Document '{document_id}' from collection '{collection}' in vector database '{database}':\n{json.dumps(document, indent=2, default=str)}"
        except ValueError as e:
            # Re-raise ValueError as is (these are user-friendly error messages)
            raise e
        except Exception as e:
            raise ValueError(f"Failed to retrieve document '{document_id}': {e}")

    @app.tool()
    async def delete_collection(
        database: str = Field(..., description="Name of the vector database instance"),
        collection: str | None = Field(
            default=None, description="Name of the collection to delete"
        ),
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
                raise ValueError(
                    f"Collection '{collection}' not found in vector database '{database}'"
                )

            # Safety check: if force=False, check if collection is empty
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
                    return (
                        f"Error: Cannot delete collection '{collection}' - it contains {doc_count} documents. "
                        f"This operation requires force=True to proceed. "
                        f"Use: delete_collection(database='{database}', collection='{collection}', force=True)"
                    )

            ok, _ = await run_with_timeout(
                db.delete_collection(collection),
                "delete",
                get_timeout("delete"),
            )
            if not ok:
                return f"Error: Failed to delete collection '{collection}' from vector database '{database}'"

            warning = " Warning: This operation cannot be undone." if force else ""
            return f"Successfully deleted collection '{collection}' from vector database '{database}'.{warning}"
        try:
            from src.db.vector_db_milvus import MilvusVectorDatabase

            if collection is None:
                raise ValueError(
                    "collection_name must be provided to delete a collection"
                )
            temp_db = MilvusVectorDatabase(collection_name=collection)
            ok, _ = await run_with_timeout(
                temp_db.delete_collection(collection),
                "delete",
                get_timeout("delete"),
            )
            if not ok:
                return f"Error: Failed to delete collection '{collection}' from Milvus (untracked)."
            return f"Successfully dropped collection '{collection}' from Milvus (untracked)."
        except Exception as e:
            return f"Delete collection failed: {str(e)}"

    @app.tool()
    async def delete_database(
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
                    return (
                        f"Error: Cannot delete database '{database}' - it contains {len(collections)} collections. "
                        f"Collections: {', '.join(collections)}. "
                        f"This operation requires force=True to proceed. "
                        f"Use: delete_database(database='{database}', force=True)"
                    )

            ok, _ = await run_with_timeout(
                db.cleanup(), "cleanup", get_timeout("cleanup")
            )
            if not ok:
                return f"Error: Failed to cleanup vector database '{database}'"
            del vector_databases[database]

            warning = " Warning: This operation cannot be undone." if force else ""
            return f"Successfully cleaned up and removed vector database '{database}'.{warning}"
        try:
            from src.db.vector_db_milvus import MilvusVectorDatabase

            temp_db = MilvusVectorDatabase(collection_name=database)
            ok, _ = await run_with_timeout(
                temp_db.delete_collection(database),
                "cleanup",
                get_timeout("cleanup"),
            )
            if not ok:
                return f"Error: Failed to cleanup (drop) collection '{database}' from Milvus (untracked)."
            return (
                f"Successfully dropped collection '{database}' from Milvus (untracked)."
            )
        except Exception as e:
            return f"Cleanup failed: {str(e)}"

    @app.tool()
    async def get_database_info(
        database: str = Field(..., description="Name of the vector database instance"),
        include_embeddings: bool = Field(
            default=False,
            description="Include list of supported embedding models in the response",
        ),
        include_chunking: bool = Field(
            default=False,
            description="Include list of supported chunking strategies in the response",
        ),
    ) -> str:
        """
        Get information about a vector database.

        Returns database type, collection name, and document count.
        Optionally includes supported embedding models when include_embeddings=True.
        Optionally includes supported chunking strategies when include_chunking=True.
        """
        db = get_database_by_name(database)
        ok, cnt_any = await run_with_timeout(
            db.count_documents(), "count_documents", get_timeout("count_documents")
        )
        count = int(cnt_any) if ok else -1
        info = {
            "name": database,
            "type": db.db_type,
            "collection": db.collection_name,
            "document_count": count,
        }

        if include_embeddings:
            embeddings = db.supported_embeddings()
            info["supported_embeddings"] = embeddings

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
            info["supported_chunking"] = {
                "strategies": strategies,
                "notes": defaults_behavior,
            }

        return f"Database information for '{database}':\n{json.dumps(info, indent=2)}"

    @app.tool()
    async def list_collections(
        database: str = Field(..., description="Name of the vector database instance"),
    ) -> str:
        """List all collections in a vector database."""
        db = get_database_by_name(database)
        ok, colls_any = await run_with_timeout(
            db.list_collections(), "list_collections", get_timeout("list_collections")
        )
        collections = (
            cast("list[str]", colls_any) if ok and isinstance(colls_any, list) else []
        )

        if not collections:
            return f"No collections found in vector database '{database}'"

        return f"Collections in vector database '{database}':\n{json.dumps(collections, indent=2)}"

    @app.tool()
    async def get_collection_info(
        database: str = Field(..., description="Name of the vector database instance"),
        collection: str | None = Field(
            default=None,
            description="Name of the collection to get info for. If not provided, uses the default collection.",
        ),
        include_count: bool = Field(
            default=False,
            description="Include document count in the response",
        ),
    ) -> str:
        """Get information about a collection in a vector database."""
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
            return str(info_any)
        info: dict[str, Any] = cast("dict[str, Any]", info_any)

        # Add document count if requested
        if include_count:
            ok_count, count_any = await run_with_timeout(
                db.count_documents(), "count_documents", get_timeout("read")
            )
            if ok_count:
                count = int(count_any) if count_any is not None else 0
                info["document_count"] = count

        return (
            f"Collection information for '{info.get('name')}' in vector database "
            f"'{database}':\n{json.dumps(info, indent=2)}"
        )

    @app.tool()
    async def create_collection(
        database: str = Field(..., description="Name of the vector database instance"),
        collection: str = Field(..., description="Name of the collection to create"),
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

        Creates a collection with specified embedding model and optional chunking configuration.
        All documents in the collection will use this embedding model.

        The embedding parameter defaults to 'auto' which automatically detects the best embedding
        model from your environment configuration. You typically don't need to specify it.

        Prerequisites:
        1. Database registered: register_database(database="name", database_type="milvus")
        2. Connection initialized: setup_database(database="name")

        Next steps:
        - Write documents: write_documents(database="name", documents=[...])

        Common errors:
        - Database not found: Register and initialize it first
        - Collection already exists: Use delete_collection() to remove it first
        - Invalid embedding: Use get_supported_embeddings() to see options
        - Database not initialized: Call setup_database() first
        - Missing API key: Set OPENAI_API_KEY or configure custom embeddings (CUSTOM_EMBEDDING_URL, etc.)
        """
        try:
            # Validate database is registered
            if database not in vector_databases:
                available = list(vector_databases.keys())
                return ErrorMessages.database_not_found(database, available)

            db = get_database_by_name(database)

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
                    resolved_embedding = "default"
                    logger.info(
                        "No custom embedding configured, using default (OpenAI)"
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
                return ErrorMessages.collection_already_exists(collection, database)

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
                        return ErrorMessages.invalid_embedding(embedding, supported)
                    elif (
                        "not initialized" in error_str.lower()
                        or "not connected" in error_str.lower()
                    ):
                        return ErrorMessages.database_not_initialized(database)
                    return str(res)
            else:
                return f"Error: Database '{database}' does not support create_collection method"

            return f"Successfully created collection '{collection}' in vector database '{database}' with embedding '{embedding}'"

        except Exception as e:
            error_msg = f"Failed to create collection '{collection}' in vector database '{database}': {str(e)}"
            logger.error(error_msg)
            return ErrorMessages.generic_operation_failed(
                "create collection", database, str(e)
            )

    @app.tool()
    async def query(
        database: str = Field(..., description="Name of the vector database instance"),
        query: str = Field(..., description="The query string to search for"),
        limit: int = Field(
            default=5, description="Maximum number of results to consider (1-100)"
        ),
        collection: str | None = Field(
            default=None, description="Optional collection name to search in"
        ),
    ) -> str:
        """
        Query a vector database using the default query agent.

        Returns a natural language summary of relevant documents.

        Prerequisites:
        - Database must exist and be initialized
        - Collection must contain documents

        Parameters:
        - limit: Number of results (1-100), default 5
        - collection: Optional specific collection, uses default if not provided

        Common errors:
        - Database not found: Check database name with list_databases()
        - Collection not found: Check collection name with list_collections()
        - No results: Collection may be empty or query doesn't match documents
        - Invalid limit: Must be between 1 and 100
        """
        try:
            # Validate limit
            if limit < 1 or limit > 100:
                return ErrorMessages.invalid_limit(limit, 1, 100)

            # Validate database exists
            if database not in vector_databases:
                available = list(vector_databases.keys())
                return ErrorMessages.database_not_found(database, available)

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
                    return ErrorMessages.collection_not_found(
                        collection or "default", database, available_colls
                    )
                return str(response)
            # response is expected to be a string summary
            return str(response)
        except KeyError:
            available = list(vector_databases.keys())
            return ErrorMessages.database_not_found(database, available)
        except Exception as e:
            error_msg = f"Failed to query vector database '{database}': {str(e)}"
            logger.error(error_msg)
            return ErrorMessages.generic_operation_failed("query", database, str(e))

    @app.tool()
    async def search(
        database: str = Field(..., description="Name of the vector database instance"),
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

        Results include:
        - text: The document text content
        - url: Direct link to the source (top-level for easy access)
        - source_citation: Formatted citation string for easy reference
        - score/similarity: Relevance score (0-1, higher is better)
        - metadata: Additional document metadata
        - rank: Position in results (1-based)

        Use min_score to filter low-quality results and metadata_filters to narrow by document properties.
        """
        try:
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
                return str(response)
            # Serialize list of results to JSON string for consistent str tool output
            return json.dumps(response, indent=2, default=str)
        except Exception as e:
            error_msg = f"Failed to search vector database '{database}': {str(e)}"
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
    async def refresh_databases() -> str:
        """Discover and register Milvus and Weaviate collections into the MCP server's in-memory registry."""
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
