"""
Tests for vector database YAML configuration validation against JSON schema.
"""

import json
import os
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import ValidationError, validate


def replace_env_vars_in_yaml(content: str) -> str:
    """Replace {{ENV_VAR_NAME}} placeholders with environment variable values."""
    # Regex to match {{ENV_VAR_NAME}} pattern
    pattern = r"\{\{([A-Z_][A-Z0-9_]*)\}\}"

    def replace_match(match: re.Match) -> str:
        env_var_name = match.group(1)
        env_value = os.getenv(env_var_name, "")
        if env_value == "":
            # If environment variable is not set, use a default value for testing
            if env_var_name == "WEAVIATE_URL":
                return "https://your-weaviate-cluster.weaviate.network"
            return match.group(0)  # Keep original if no default
        return env_value

    return re.sub(pattern, replace_match, content)


@pytest.fixture
def schema() -> dict[str, Any]:
    """Load the vector database JSON schema."""
    schema_path = (
        Path(__file__).parent.parent / "schemas" / "vector-database-schema.json"
    )
    with open(schema_path, "r") as f:
        return json.load(f)


@pytest.fixture
def local_milvus_yaml() -> dict[str, Any]:
    """Load the local Milvus YAML configuration."""
    yaml_path = Path(__file__).parent / "yamls" / "test_local_milvus.yaml"
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def remote_weaviate_yaml() -> dict[str, Any]:
    """Load the remote Weaviate YAML configuration."""
    yaml_path = Path(__file__).parent / "yamls" / "test_remote_weaviate.yaml"
    with open(yaml_path, "r") as f:
        content = f.read()

    # Replace environment variable placeholders
    content = replace_env_vars_in_yaml(content)

    return yaml.safe_load(content)


@pytest.mark.unit
class TestVectorDatabaseYAMLValidation:
    """Test class for vector database YAML validation."""

    def test_local_milvus_yaml_validates_against_schema(
        self, schema: dict[str, Any], local_milvus_yaml: dict[str, Any]
    ) -> None:
        """Test that local Milvus YAML validates against the schema."""
        validate(instance=local_milvus_yaml, schema=schema)

    def test_remote_weaviate_yaml_validates_against_schema(
        self, schema: dict[str, Any], remote_weaviate_yaml: dict[str, Any]
    ) -> None:
        """Test that remote Weaviate YAML validates against the schema."""
        validate(instance=remote_weaviate_yaml, schema=schema)

    def test_local_milvus_has_correct_structure(
        self, local_milvus_yaml: dict[str, Any]
    ) -> None:
        """Test that local Milvus YAML has the expected structure."""
        assert local_milvus_yaml["apiVersion"] == "maestro/v1alpha1"
        assert local_milvus_yaml["kind"] == "VectorDatabase"
        assert local_milvus_yaml["metadata"]["name"] == "test_local_milvus"
        assert local_milvus_yaml["metadata"]["labels"]["app"] == "testdb"
        assert local_milvus_yaml["spec"]["type"] == "milvus"
        assert local_milvus_yaml["spec"]["uri"] == "localhost:19530"
        assert (
            local_milvus_yaml["spec"]["collection_name"] == "Test_collection_lowercase"
        )
        assert local_milvus_yaml["spec"]["embedding"] == "text-embedding-3-small"
        assert local_milvus_yaml["spec"]["mode"] == "local"

    def test_remote_weaviate_has_correct_structure(
        self, remote_weaviate_yaml: dict[str, Any]
    ) -> None:
        """Test that remote Weaviate YAML has the expected structure."""
        assert remote_weaviate_yaml["apiVersion"] == "maestro/v1alpha1"
        assert remote_weaviate_yaml["kind"] == "VectorDatabase"
        assert remote_weaviate_yaml["metadata"]["name"] == "test_remote_weaviate"
        assert remote_weaviate_yaml["metadata"]["labels"]["app"] == "testdb"
        assert remote_weaviate_yaml["spec"]["type"] == "weaviate"
        # The URI should be the substituted value (either from env var or default)
        expected_uri = os.getenv(
            "WEAVIATE_URL", "https://your-weaviate-cluster.weaviate.network"
        )
        assert remote_weaviate_yaml["spec"]["uri"] == expected_uri
        assert (
            remote_weaviate_yaml["spec"]["collection_name"]
            == "Test_collection_lowercase"
        )
        assert remote_weaviate_yaml["spec"]["embedding"] == "text-embedding-3-small"
        assert remote_weaviate_yaml["spec"]["mode"] == "remote"

    def test_schema_enforces_required_fields(self, schema: dict[str, Any]) -> None:
        """Test that the schema enforces all required fields."""
        # Test missing apiVersion
        invalid_config = {
            "kind": "VectorDatabase",
            "metadata": {"name": "test"},
            "spec": {
                "type": "milvus",
                "uri": "localhost:19530",
                "collection_name": "test",
                "embedding": "text-embedding-3-small",
                "mode": "local",
            },
        }
        with pytest.raises(
            ValidationError, match="'apiVersion' is a required property"
        ):
            validate(instance=invalid_config, schema=schema)

        # Test missing kind
        invalid_config = {
            "apiVersion": "maestro/v1alpha1",
            "metadata": {"name": "test"},
            "spec": {
                "type": "milvus",
                "uri": "localhost:19530",
                "collection_name": "test",
                "embedding": "text-embedding-3-small",
                "mode": "local",
            },
        }
        with pytest.raises(ValidationError, match="'kind' is a required property"):
            validate(instance=invalid_config, schema=schema)

        # Test missing metadata.name
        invalid_config = {
            "apiVersion": "maestro/v1alpha1",
            "kind": "VectorDatabase",
            "metadata": {},
            "spec": {
                "type": "milvus",
                "uri": "localhost:19530",
                "collection_name": "test",
                "embedding": "text-embedding-3-small",
                "mode": "local",
            },
        }
        with pytest.raises(ValidationError, match="'name' is a required property"):
            validate(instance=invalid_config, schema=schema)

    def test_schema_enforces_enum_values(self, schema: dict[str, Any]) -> None:
        """Test that the schema enforces enum values for type and mode."""
        # Test invalid type
        invalid_config = {
            "apiVersion": "maestro/v1alpha1",
            "kind": "VectorDatabase",
            "metadata": {"name": "test"},
            "spec": {
                "type": "invalid_type",
                "uri": "localhost:19530",
                "collection_name": "test",
                "embedding": "text-embedding-3-small",
                "mode": "local",
            },
        }
        with pytest.raises(ValidationError, match="'invalid_type' is not one of"):
            validate(instance=invalid_config, schema=schema)

        # Test invalid mode
        invalid_config = {
            "apiVersion": "maestro/v1alpha1",
            "kind": "VectorDatabase",
            "metadata": {"name": "test"},
            "spec": {
                "type": "milvus",
                "uri": "localhost:19530",
                "collection_name": "test",
                "embedding": "text-embedding-3-small",
                "mode": "invalid_mode",
            },
        }
        with pytest.raises(ValidationError, match="'invalid_mode' is not one of"):
            validate(instance=invalid_config, schema=schema)

    def test_schema_enforces_api_version_pattern(self, schema: dict[str, Any]) -> None:
        """Test that the schema enforces the correct API version pattern."""
        invalid_config = {
            "apiVersion": "maestro/v1beta1",  # Wrong version
            "kind": "VectorDatabase",
            "metadata": {"name": "test"},
            "spec": {
                "type": "milvus",
                "uri": "localhost:19530",
                "collection_name": "test",
                "embedding": "text-embedding-3-small",
                "mode": "local",
            },
        }
        with pytest.raises(ValidationError, match="does not match"):
            validate(instance=invalid_config, schema=schema)

    def test_schema_allows_optional_labels(self, schema: dict[str, Any]) -> None:
        """Test that the schema allows optional labels."""
        config_with_labels = {
            "apiVersion": "maestro/v1alpha1",
            "kind": "VectorDatabase",
            "metadata": {
                "name": "test",
                "labels": {
                    "app": "testdb",
                    "environment": "production",
                    "team": "data-science",
                },
            },
            "spec": {
                "type": "milvus",
                "uri": "localhost:19530",
                "collection_name": "test",
                "embedding": "text-embedding-3-small",
                "mode": "local",
            },
        }
        # Should not raise any validation errors
        validate(instance=config_with_labels, schema=schema)

    def test_schema_prevents_additional_properties(
        self, schema: dict[str, Any]
    ) -> None:
        """Test that the schema prevents additional properties at the root level."""
        invalid_config = {
            "apiVersion": "maestro/v1alpha1",
            "kind": "VectorDatabase",
            "metadata": {"name": "test"},
            "spec": {
                "type": "milvus",
                "uri": "localhost:19530",
                "collection_name": "test",
                "embedding": "text-embedding-3-small",
                "mode": "local",
            },
            "extraField": "should_not_be_allowed",
        }
        with pytest.raises(
            ValidationError, match="Additional properties are not allowed"
        ):
            validate(instance=invalid_config, schema=schema)
