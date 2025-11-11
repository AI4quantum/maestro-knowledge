# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import warnings

# Suppress Pydantic deprecation warnings from dependencies
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, message=".*class-based `config`.*"
)
warnings.filterwarnings(
    "ignore", category=DeprecationWarning, message=".*PydanticDeprecatedSince20.*"
)
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=".*Support for class-based `config`.*",
)

# Suppress Milvus connection warnings during tests
warnings.filterwarnings(
    "ignore", category=UserWarning, message=".*Failed to connect to Milvus.*"
)
warnings.filterwarnings(
    "ignore", category=UserWarning, message=".*Milvus client is not available.*"
)

import os
import sys

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from the new modular structure
from src.db.vector_db_base import VectorDatabase
from src.db.vector_db_factory import create_vector_database
from src.db.vector_db_milvus import MilvusVectorDatabase
from src.db.vector_db_weaviate import WeaviateVectorDatabase

# This file now serves as a compatibility layer and re-exports the tests
# The actual test implementations are in the separate test files:
# - test_vector_db_base.py
# - test_vector_db_weaviate.py
# - test_vector_db_milvus.py
# - test_vector_db_factory.py

# Re-export for backward compatibility
__all__ = [
    "VectorDatabase",
    "WeaviateVectorDatabase",
    "MilvusVectorDatabase",
    "create_vector_database",
]
