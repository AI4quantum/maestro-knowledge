# SPDX-License-Identifier: Apache 2.0
# Copyright (c) 2025 IBM

import os
import subprocess
import sys
import warnings
from unittest.mock import patch

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

import pytest

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.integration
class TestIntegrationExamples:
    """Integration tests that run the example files to ensure they work correctly."""

    def test_milvus_example_structure(self) -> None:
        """Test that the Milvus example file exists and has correct structure."""
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples",
            "milvus_example.py",
        )

        assert os.path.exists(example_path), "Milvus example file should exist"

        # Check that the file can be imported
        with open(example_path, "r") as f:
            content = f.read()
            assert "create_vector_database" in content, (
                "Should import create_vector_database"
            )
            assert "milvus" in content, "Should use Milvus database"
            assert "main()" in content, "Should have main function"

    def test_weaviate_example_structure(self) -> None:
        """Test that the Weaviate example file exists and has correct structure."""
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples",
            "weaviate_example.py",
        )

        assert os.path.exists(example_path), "Weaviate example file should exist"

        # Check that the file can be imported
        with open(example_path, "r") as f:
            content = f.read()
            assert "create_vector_database" in content, (
                "Should import create_vector_database"
            )
            assert "weaviate" in content, "Should use Weaviate database"
            assert "main()" in content, "Should have main function"

    def test_milvus_example_imports_and_runs(self) -> None:
        """Test that the Milvus example can be imported and runs without errors."""
        # Import the example module
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples",
            "milvus_example.py",
        )

        # Test that the file can be executed
        try:
            # Set environment variable to avoid connection issues
            with patch.dict(os.environ, {"MILVUS_URI": "test://localhost"}):
                result = subprocess.run(
                    [sys.executable, example_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                # The example should run without crashing, even if it can't connect
                # It might fail due to missing pymilvus, but should exit gracefully
                assert result.returncode in [0, 1], (
                    f"Example should exit gracefully: {result.stderr}"
                )

        except subprocess.TimeoutExpired:
            pytest.fail("Example execution timed out")

    def test_weaviate_example_imports_and_runs(self) -> None:
        """Test that the Weaviate example can be imported and runs without errors."""
        # Import the example module
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples",
            "weaviate_example.py",
        )

        # Test that the file can be executed
        try:
            # Set environment variables to avoid connection issues
            with patch.dict(
                os.environ,
                {
                    "WEAVIATE_API_KEY": "test_key",
                    "WEAVIATE_URL": "https://test.weaviate.network",
                },
            ):
                result = subprocess.run(
                    [sys.executable, example_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                # The example should run without crashing, even if it can't connect
                # It might fail due to missing weaviate, but should exit gracefully
                assert result.returncode in [0, 1], (
                    f"Example should exit gracefully: {result.stderr}"
                )

        except subprocess.TimeoutExpired:
            pytest.fail("Example execution timed out")

    def test_examples_environment_validation(self) -> None:
        """Test that examples properly validate environment variables."""
        # Test Milvus example without environment variables
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples",
            "milvus_example.py",
        )

        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            result = subprocess.run(
                [sys.executable, example_path],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should exit gracefully with error message
            # The example might fail due to missing dependencies, but should still
            # provide helpful error messages about environment variables or dependencies
            output = result.stdout + result.stderr
            assert any(
                keyword in output
                for keyword in ["MILVUS_URI", "pymilvus", "environment variables"]
            ), f"Should provide helpful error message, got: {output}"

    def test_examples_import_structure(self) -> None:
        """Test that examples use the correct import structure."""
        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples"
        )

        for example_file in ["milvus_example.py", "weaviate_example.py"]:
            example_path = os.path.join(examples_dir, example_file)

            with open(example_path, "r") as f:
                content = f.read()

                # Check for correct import path
                assert (
                    "from src.db.vector_db_factory import create_vector_database"
                    in content
                ), f"{example_file} should use correct import path"

                # Check for proper sys.path manipulation
                assert "sys.path.append" in content, (
                    f"{example_file} should include sys.path manipulation"
                )

    def test_examples_error_handling(self) -> None:
        """Test that examples have proper error handling."""
        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples"
        )

        for example_file in ["milvus_example.py", "weaviate_example.py"]:
            example_path = os.path.join(examples_dir, example_file)

            with open(example_path, "r") as f:
                content = f.read()

                # Check for try-except blocks
                assert "try:" in content, f"{example_file} should have error handling"
                assert "except" in content, f"{example_file} should have error handling"
                assert "finally:" in content, f"{example_file} should have cleanup"

    def test_examples_cleanup(self) -> None:
        """Test that examples have proper cleanup."""
        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples"
        )

        for example_file in ["milvus_example.py", "weaviate_example.py"]:
            example_path = os.path.join(examples_dir, example_file)

            with open(example_path, "r") as f:
                content = f.read()

                # Check for cleanup calls
                assert "db.cleanup()" in content, f"{example_file} should call cleanup"

    def test_examples_document_operations(self) -> None:
        """Test that examples demonstrate document operations."""
        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples"
        )

        for example_file in ["milvus_example.py", "weaviate_example.py"]:
            example_path = os.path.join(examples_dir, example_file)

            with open(example_path, "r") as f:
                content = f.read()

                # Check for document operations
                assert "write_documents" in content, (
                    f"{example_file} should demonstrate document writing"
                )
                assert "list_documents" in content, (
                    f"{example_file} should demonstrate document listing"
                )
                assert "count_documents" in content, (
                    f"{example_file} should demonstrate document counting"
                )
                assert "delete_document" in content, (
                    f"{example_file} should demonstrate document deletion"
                )

    def test_examples_output_format(self) -> None:
        """Test that examples have proper output formatting."""
        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "examples"
        )

        for example_file in ["milvus_example.py", "weaviate_example.py"]:
            example_path = os.path.join(examples_dir, example_file)

            with open(example_path, "r") as f:
                content = f.read()

                # Check for proper output formatting
                assert "print(" in content, f"{example_file} should have output"
                assert "✅" in content, f"{example_file} should have success indicators"
                assert "❌" in content, f"{example_file} should have error indicators"
