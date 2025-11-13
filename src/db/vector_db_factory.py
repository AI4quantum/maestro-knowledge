# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

from .vector_db_base import VectorDatabase
from .vector_db_milvus import MilvusVectorDatabase
from .vector_db_weaviate import WeaviateVectorDatabase


def create_vector_database(
    db_type: str | None = None, collection_name: str | None = None
) -> VectorDatabase:
    """
    Factory function to create vector database instances.
    Args:
        db_type: Type of vector database ("weaviate", "milvus", etc.)
        collection_name: Name of the collection to use (optional, can be set later)
    Returns:
        VectorDatabase instance
    """
    import os

    if db_type is None:
        db_type = os.getenv("VECTOR_DB_TYPE", "weaviate")

    # Use a placeholder collection name if not provided
    # This will be overridden when create_collection is called
    if collection_name is None:
        collection_name = "_placeholder_"

    if db_type.lower() == "weaviate":
        return WeaviateVectorDatabase(collection_name)
    elif db_type.lower() == "milvus":
        return MilvusVectorDatabase(collection_name)
    else:
        raise ValueError(f"Unsupported vector database type: {db_type}")
