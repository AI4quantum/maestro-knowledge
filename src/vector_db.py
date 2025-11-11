# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

# Import from the new modular structure
from .db.vector_db_base import VectorDatabase
from .db.vector_db_factory import create_vector_database
from .db.vector_db_milvus import MilvusVectorDatabase
from .db.vector_db_weaviate import WeaviateVectorDatabase

# Re-export for backward compatibility
__all__ = [
    "VectorDatabase",
    "WeaviateVectorDatabase",
    "MilvusVectorDatabase",
    "create_vector_database",
]
