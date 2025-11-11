# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import os
import warnings
from unittest.mock import MagicMock, patch

import pytest

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

# Import from the new modular structure
from src.db.vector_db_factory import create_vector_database


@pytest.mark.unit
class TestCreateVectorDatabase:
    """Tests for the vector database factory function."""

    def test_create_weaviate_database(self) -> None:
        """Test creating a Weaviate vector database."""
        with patch(
            "src.db.vector_db_factory.WeaviateVectorDatabase"
        ) as mock_weaviate_db:
            mock_instance = MagicMock()
            mock_weaviate_db.return_value = mock_instance
            db = create_vector_database("weaviate", "TestCollection")
            mock_weaviate_db.assert_called_once_with("TestCollection")
            assert db == mock_instance

    def test_create_milvus_database(self) -> None:
        """Test creating a Milvus vector database."""
        with patch("src.db.vector_db_factory.MilvusVectorDatabase") as mock_milvus_db:
            mock_instance = MagicMock()
            mock_milvus_db.return_value = mock_instance
            db = create_vector_database("milvus", "TestCollection")
            mock_milvus_db.assert_called_once_with("TestCollection")
            assert db == mock_instance

    def test_create_unsupported_database(self) -> None:
        """Test creating an unsupported vector database."""
        with pytest.raises(
            ValueError, match="Unsupported vector database type: foobar"
        ):
            create_vector_database("foobar", "TestCollection")

    def test_create_database_case_insensitive(self) -> None:
        """Test that database type is case-insensitive."""
        with patch(
            "src.db.vector_db_factory.WeaviateVectorDatabase"
        ) as mock_weaviate_db:
            create_vector_database("WeAvIaTe", "TestCollection")
            mock_weaviate_db.assert_called_once_with("TestCollection")

    def test_create_database_with_environment_default(self) -> None:
        """Test creating a database using the environment variable default."""
        with patch.dict(os.environ, {"VECTOR_DB_TYPE": "milvus"}):
            with patch(
                "src.db.vector_db_factory.MilvusVectorDatabase"
            ) as mock_milvus_db:
                mock_instance = MagicMock()
                mock_milvus_db.return_value = mock_instance
                db = create_vector_database(collection_name="TestCollection")
                mock_milvus_db.assert_called_once_with("TestCollection")
                assert db == mock_instance

    def test_create_database_with_no_type_and_no_env_var(self) -> None:
        """Test creating a database with no type and no env var, defaulting to weaviate."""
        # Ensure VECTOR_DB_TYPE is not set for this test
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "src.db.vector_db_factory.WeaviateVectorDatabase"
            ) as mock_weaviate_db:
                mock_instance = MagicMock()
                mock_weaviate_db.return_value = mock_instance
                db = create_vector_database(collection_name="TestCollection")
                mock_weaviate_db.assert_called_once_with("TestCollection")
                assert db == mock_instance
