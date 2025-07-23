# Vector Database Configuration Schema

This directory contains JSON schemas for validating Maestro vector database configurations.

## Files

- `vector-database-schema.json` - JSON schema for vector database configurations

## Schema Overview

The schema validates vector database configurations with the following structure:

```yaml
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: <unique-name>
  labels:
    app: <app-label>
spec:
  type: milvus|weaviate
  uri: <connection-uri>
  collection_name: <collection-name>
  embedding: <embedding-model>
  mode: local|remote
```

## Validation Rules

### Required Fields
- `apiVersion`: Must be exactly "maestro/v1alpha1"
- `kind`: Must be "VectorDatabase"
- `metadata.name`: Unique name for the configuration
- `spec.type`: Must be either "milvus" or "weaviate"
- `spec.uri`: Connection URI (host:port for local, full URL for remote)
- `spec.collection_name`: Name of the collection
- `spec.embedding`: Embedding model identifier
- `spec.mode`: Must be either "local" or "remote"

### Optional Fields
- `metadata.labels`: Key-value pairs for labeling
- `metadata.labels.app`: Application label (common pattern)

## Usage

### Using the Schema with Tests

The schema is validated against the example YAML files in the test suite:

```bash
# Run the YAML validation tests
pytest tests/test_vector_database_yamls.py -v
```

### Using the Schema Directly

You can use any JSON schema validator with the `vector-database-schema.json` file. The schema follows JSON Schema Draft-07 specification.

## Example Valid Configurations

### Local Milvus
```yaml
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: local_milvus
  labels:
    app: testdb
spec:
  type: milvus
  uri: localhost:19530
  collection_name: test_collection
  embedding: text-embedding-3-small
  mode: local
```

### Remote Weaviate
```yaml
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: remote_weaviate
  labels:
    app: testdb
spec:
  type: weaviate
  uri: https://your-weaviate-cluster.weaviate.network
  collection_name: test_collection
  embedding: text-embedding-3-small
  mode: remote
```

## Dependencies

To use the validation script, install the required dependencies:

```bash
pip install pyyaml jsonschema
```

Or using uv:

```bash
uv add pyyaml jsonschema
``` 