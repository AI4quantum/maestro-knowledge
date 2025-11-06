# Testing Guide

## Quick Reference

### Run All Standard Tests (Recommended)
```bash
./test.sh standard
# or just
./test.sh
```

### Run Specific Test Categories
```bash
# Unit tests only (fast, ~5s)
./test.sh unit

# Integration tests only (~5s)
./test.sh integration

# End-to-end tests (requires external services)
./test.sh e2e

# Everything (all tests including external deps)
./test.sh all
```

### Run Tests with Milvus
```bash
# 1. Start Milvus container
docker-compose -f tests/setup/docker-compose-milvus.yml up -d

# Or use the setup script
./tests/setup/milvus_e2e.sh

# 2. Run tests
E2E_BACKEND=milvus E2E_MILVUS=1 \
  MILVUS_URI=http://localhost:19530 \
  CUSTOM_EMBEDDING_URL=http://localhost:11434/v1 \
  CUSTOM_EMBEDDING_MODEL=nomic-embed-text \
  CUSTOM_EMBEDDING_VECTORSIZE=768 \
  pytest tests/e2e/test_mcp_milvus_e2e.py -m e2e -vv

# 3. Stop Milvus
docker-compose -f tests/setup/docker-compose-milvus.yml down
```

## Test Categories

### Unit Tests
**Purpose**: Test individual components in isolation with mocked dependencies.

**Characteristics**:
- Fast execution (~5 seconds)
- No external services required
- Pure Python logic validation
- Mocked database connections

**Run**:
```bash
./test.sh unit
```

**Examples**:
- `tests/test_chunking.py` - Chunking strategies
- `tests/test_converters.py` - Document converters
- `tests/test_vector_db_base.py` - Base class logic

### Integration Tests
**Purpose**: Test multiple components working together.

**Characteristics**:
- Medium execution time (~5 seconds)
- No external services required
- Tests component interactions
- Still uses mocks for external services

**Run**:
```bash
./test.sh integration
```

**Examples**:
- `tests/test_vector_db_factory.py` - Database factory
- `tests/test_integration_examples.py` - Example scripts
- `tests/test_mcp_server.py` - MCP server integration

### End-to-End Tests
**Purpose**: Test complete workflows with real external services.

**Characteristics**:
- Slower execution (varies)
- Requires external services (Milvus, Weaviate)
- Tests real database operations
- Complete workflow validation

**Run**:
```bash
# Requires external services to be running
./test.sh e2e
```

**Examples**:
- `tests/e2e/test_mcp_milvus_e2e.py` - Milvus E2E
- `tests/e2e/test_mcp_weaviate_e2e.py` - Weaviate E2E

## CI Integration

### GitHub Actions Workflow

The CI pipeline runs automatically on:
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`

**Jobs**:
1. **unit-tests**: Runs across Python 3.11, 3.12, 3.13
2. **integration-tests**: Runs across Python 3.11, 3.12, 3.13
3. **lint**: Code quality checks (Python 3.12)
4. **security**: Security scans (Python 3.12)
5. **test-summary**: Aggregates results

**Configuration**: `.github/workflows/ci.yml`

### What CI Tests

✅ **Included in CI**:
- All unit tests
- All integration tests
- Linting (ruff)
- Security checks (bandit, safety)

❌ **Not Included in CI** (require external services):
- End-to-end tests with real databases
- Tests marked with `@pytest.mark.e2e`

### Viewing CI Results

After a CI run, check the **Actions** tab on GitHub:
- Individual job logs for detailed output
- Test summary with pass/fail counts
- Artifacts with test results and logs

## Test Markers

Tests use pytest markers to categorize:

```python
@pytest.mark.unit          # Unit test
@pytest.mark.integration   # Integration test
@pytest.mark.e2e          # End-to-end test
```

**Run specific markers**:
```bash
# Only unit tests
pytest -m unit

# Only integration tests
pytest -m integration

# Only e2e tests
pytest -m e2e

# Everything except e2e
pytest -m "not e2e"
```

## Testing New Features

### Document Ingestion Tests

The new document ingestion feature has comprehensive tests in `tests/test_converters.py`:

**Run converter tests**:
```bash
# All converter tests
pytest tests/test_converters.py -v

# Specific test class
pytest tests/test_converters.py::TestContentDetector -v

# With coverage
pytest tests/test_converters.py --cov=src/converters
```

**Test coverage**:
- Content type detection (URL, headers, magic bytes)
- Converter registry (registration, lookup)
- Individual converters (text, markdown, HTML, PDF)
- Fallback converter
- Security restrictions (file path validation)

### Security Tests

File path security is tested in `tests/test_converters.py`:

```python
def test_file_path_security():
    """Test that file access is restricted to allowed paths."""
    fetcher = DocumentFetcher(allowed_paths=["/tmp"])
    
    # Should fail - outside allowed path
    with pytest.raises(PermissionError):
        await fetcher.fetch("file:///etc/passwd")
    
    # Should succeed - within allowed path
    content, metadata = await fetcher.fetch("file:///tmp/test.txt")
```

## Environment Variables for Testing

### Required for Tests
```bash
# Fake credentials for unit/integration tests
export OPENAI_API_KEY=fake-openai-key
export WEAVIATE_API_KEY=fake-weaviate-key
export WEAVIATE_URL=fake-weaviate-url.com
```

### Optional for E2E Tests
```bash
# Milvus E2E
export E2E_BACKEND=milvus
export E2E_MILVUS=1
export MILVUS_URI=http://localhost:19530
export CUSTOM_EMBEDDING_URL=http://localhost:11434/v1
export CUSTOM_EMBEDDING_MODEL=nomic-embed-text
export CUSTOM_EMBEDDING_VECTORSIZE=768

# Weaviate E2E
export E2E_BACKEND=weaviate
export E2E_WEAVIATE=1
export WEAVIATE_API_KEY=your-real-key
export WEAVIATE_URL=your-cluster.weaviate.network
```

### Security Configuration
```bash
# Configure allowed file paths for document ingestion
export MAESTRO_ALLOWED_FILE_PATHS="/path/to/docs:/another/path"

# Default: Current working directory only
```

## Pre-Commit Checklist

Before submitting a PR, run:

```bash
# 1. Linting
./tools/lint.sh

# 2. Standard tests (unit + integration)
./test.sh standard

# 3. Optional: Full test suite
./test.sh all
```

**Recommended one-liner**:
```bash
./tools/lint.sh && ./test.sh standard
```

## Debugging Tests

### Run with Verbose Output
```bash
pytest -vv tests/test_converters.py
```

### Run Specific Test
```bash
pytest tests/test_converters.py::TestContentDetector::test_detect_from_url -v
```

### Run with Debugging
```bash
pytest --pdb tests/test_converters.py
```

### Show Print Statements
```bash
pytest -s tests/test_converters.py
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=html tests/
# Open htmlcov/index.html in browser
```

## Common Issues

### Issue: Tests fail with import errors
**Solution**: Ensure PYTHONPATH is set:
```bash
PYTHONPATH=src pytest tests/
```

### Issue: Milvus E2E tests fail
**Solution**: Ensure Milvus is running:
```bash
docker ps | grep milvus
# If not running:
./tests/setup/milvus_e2e.sh
```

### Issue: File path security tests fail
**Solution**: Check MAESTRO_ALLOWED_FILE_PATHS:
```bash
# Unset to use default (current directory)
unset MAESTRO_ALLOWED_FILE_PATHS

# Or set to specific paths
export MAESTRO_ALLOWED_FILE_PATHS="/tmp:/var/tmp"
```

### Issue: PDF converter tests skipped
**Solution**: Install PDF dependencies:
```bash
pip install pypdf
# or
pip install pdfplumber
```

## Test File Organization

```
tests/
├── test_*.py              # Unit and integration tests
├── test_converters.py     # NEW: Document converter tests
├── e2e/                   # End-to-end tests
│   ├── test_mcp_milvus_e2e.py
│   └── test_mcp_weaviate_e2e.py
├── chunking/              # Chunking strategy tests
├── setup/                 # Test setup scripts
│   ├── milvus_e2e.sh
│   └── weaviate_e2e.sh
└── yamls/                 # Test configuration files
```

## Writing New Tests

### Unit Test Template
```python
import pytest

@pytest.mark.unit
def test_my_feature():
    """Test description."""
    # Arrange
    input_data = "test"
    
    # Act
    result = my_function(input_data)
    
    # Assert
    assert result == expected_output
```

### Integration Test Template
```python
import pytest

@pytest.mark.integration
async def test_component_integration():
    """Test multiple components working together."""
    # Setup
    component_a = ComponentA()
    component_b = ComponentB()
    
    # Execute
    result = await component_a.process(component_b)
    
    # Verify
    assert result.status == "success"
```

### E2E Test Template
```python
import pytest

@pytest.mark.e2e
async def test_end_to_end_workflow():
    """Test complete workflow with real services."""
    # Requires external services
    if not os.getenv("E2E_MILVUS"):
        pytest.skip("E2E_MILVUS not set")
    
    # Test real workflow
    db = create_vector_database("milvus", "test_collection")
    # ... test operations ...
```

## Performance Testing

### Measure Test Duration
```bash
pytest --durations=10 tests/
```

### Profile Tests
```bash
pytest --profile tests/
```

## Summary

**Quick Commands**:
- `./test.sh` - Run standard tests (default)
- `./test.sh unit` - Fast unit tests
- `./test.sh integration` - Integration tests
- `./tools/lint.sh && ./test.sh` - Pre-commit check

**CI Integration**: ✅ Automatic on PR/push
**New Tests**: ✅ Converter tests in `tests/test_converters.py`
**Security**: ✅ File path restrictions tested and enforced