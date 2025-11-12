# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

"""Database registry and synchronization for MCP server."""

import asyncio
import logging
import os
from typing import Any

from src.db.vector_db_base import VectorDatabase

logger = logging.getLogger(__name__)

# Dictionary to store vector database instances keyed by name
vector_databases: dict[str, VectorDatabase] = {}


def get_database_by_name(db_name: str) -> VectorDatabase:
    """Get a vector database instance by name."""
    if db_name not in vector_databases:
        raise ValueError(
            f"Vector database '{db_name}' not found. Please create it first."
        )
    return vector_databases[db_name]


async def resync_vector_databases() -> list[str]:
    """Discover Milvus collections and register them in memory.

    Returns a list of collection names that were registered.
    This is a best-effort helper to recover state after a server restart.
    """
    added: list[str] = []
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


# Made with Bob
