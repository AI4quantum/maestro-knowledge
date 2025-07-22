# Contributing to Maestro Knowledge

Thank you for your interest in contributing to Maestro Knowledge! This document provides guidelines and instructions for contributing to this project.

## 📚 Documentation Structure

Before contributing, please familiarize yourself with our documentation:

- **[📖 Documentation Index](README.md)** - Overview of all documentation
- **[🔧 Vector Database Abstraction](VECTOR_DB_ABSTRACTION.md)** - Understanding the database layer
- **[📋 Project Overview](PRESENTATION.md)** - Complete project overview

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## How Can I Contribute?

### Reporting Bugs

This section guides you through submitting a bug report for Maestro Knowledge. Following these guidelines helps maintainers and the community understand your report, reproduce the behavior, and find related reports.

#### Before Submitting A Bug Report

* Check the documentation for a list of common questions and problems.
* Perform a cursory search to see if the problem has already been reported. If it has, add a comment to the existing issue instead of opening a new one.

#### How Do I Submit A (Good) Bug Report?

Bugs are tracked as GitHub issues. Create an issue and provide the following information by filling in the template.

Explain the problem and include additional details to help maintainers reproduce the problem:

* Use a clear and descriptive title for the issue to identify the problem.
* Describe the exact steps which reproduce the problem in as many details as possible.
* Provide specific examples to demonstrate the steps.
* Describe the behavior you observed after following the steps and point out what exactly is the problem with that behavior.
* Explain which behavior you expected to see instead and why.
* Include screenshots and animated GIFs which show you following the described steps and clearly demonstrate the problem.
* If the problem wasn't triggered by a specific action, describe what you were doing before the problem happened.
* Include details about your configuration and environment:
  * Which version of Maestro Knowledge are you using?
* What's the name and version of the OS you're using?
* Are you running Maestro Knowledge in a virtual machine?
  * What are your environment variables?
  * Which vector database are you using? (Weaviate, Milvus, etc.)

### Suggesting Enhancements

This section guides you through submitting an enhancement suggestion for Maestro Knowledge, including completely new features and minor improvements to existing functionality.

#### Before Submitting An Enhancement Suggestion

* Check the documentation for suggestions.
* Perform a cursory search to see if the enhancement has already been suggested. If it has, add a comment to the existing issue instead of opening a new one.

#### How Do I Submit A (Good) Enhancement Suggestion?

Enhancement suggestions are tracked as GitHub issues. Create an issue and provide the following information:

* Use a clear and descriptive title for the issue to identify the suggestion.
* Provide a step-by-step description of the suggested enhancement in as many details as possible.
* Provide specific examples to demonstrate the steps.
* Describe the current behavior and explain which behavior you expected to see instead and why.
* Include screenshots and animated GIFs which help you demonstrate the steps or point out the part of Maestro Knowledge which the suggestion is related to.
* Explain why this enhancement would be useful to most Maestro Knowledge users.

### Pull Requests

* Fill in the required template
* Do not include issue numbers in the PR title
* Include screenshots and animated GIFs in your pull request whenever possible.
* Follow our coding conventions
* Document new code based on the Documentation Style Guide
* End all files with a newline

## 🏗️ Development Setup

### Project Structure

```
maestro-knowledge/
├── docs/                    # 📚 Documentation
│   ├── README.md           # Documentation index
│   ├── VECTOR_DB_ABSTRACTION.md
│   ├── CONTRIBUTING.md     # This file
│   └── PRESENTATION.md
├── examples/                # 📚 Example implementations
│   ├── README.md           # Examples documentation
│   ├── milvus_example.py   # Milvus usage example
│   └── weaviate_example.py # Weaviate usage example
├── src/                     # 🐍 Source code
│   ├── db/                  # Vector database implementations
│   │   ├── __init__.py      # Package exports
│   │   ├── vector_db_base.py # Abstract base class
│   │   ├── vector_db_weaviate.py # Weaviate implementation
│   │   ├── vector_db_milvus.py # Milvus implementation
│   │   └── vector_db_factory.py # Factory function
│   └── vector_db.py         # Vector database compatibility layer
├── tests/                   # 🧪 Test suite
│   ├── test_vector_db_base.py
│   ├── test_vector_db_weaviate.py
│   ├── test_vector_db_milvus.py
│   ├── test_vector_db_factory.py
│   ├── test_vector_db.py    # Compatibility layer tests
│   └── test_integration_examples.py # Integration tests for examples
├── .github/                 # GitHub configuration
│   └── workflows/           # GitHub Actions workflows
│       └── ci.yml           # Continuous Integration workflow
├── tests.sh                 # Test runner script
├── lint.sh                  # Linting and formatting script
├── pyproject.toml           # Project configuration
└── README.md                # Main project documentation
```
```

### Vector Database Development

When working with vector databases:

1. **Follow the abstraction pattern**: All vector database code should implement the `VectorDatabase` interface
2. **Create separate files**: New implementations should be in separate files (e.g., `src/db/vector_db_pinecone.py`)
3. **Add tests**: Include comprehensive tests in separate test files (e.g., `tests/test_vector_db_pinecone.py`)
4. **Update factory function**: Add new database types to `create_vector_database()` in `src/db/vector_db_factory.py`
5. **Documentation**: Update [VECTOR_DB_ABSTRACTION.md](VECTOR_DB_ABSTRACTION.md) with new implementations
6. **Update compatibility layer**: Add imports to `src/vector_db.py` for backward compatibility
7. **Implement all required methods**: Ensure all abstract methods are implemented (setup, write_documents, list_documents, count_documents, delete_documents, delete_collection, create_query_agent, cleanup)

### Adding New Vector Database Support

To add support for a new vector database:

1. **Create implementation file**: `src/db/vector_db_[name].py`
2. **Create test file**: `tests/test_vector_db_[name].py`
3. **Update factory**: Add new type to `create_vector_database()` in `src/db/vector_db_factory.py`
4. **Update compatibility layer**: Add import to `src/vector_db.py`
5. **Update documentation**: Add new database to `VECTOR_DB_ABSTRACTION.md`
6. **Add environment variables**: Document required environment variables
7. **Create example**: Add `examples/[name]_example.py` following the existing pattern

Example for adding Pinecone support:

```python
# src/db/vector_db_pinecone.py
from .vector_db_base import VectorDatabase

class PineconeVectorDatabase(VectorDatabase):
    def __init__(self, collection_name: str = "MaestroDocs"):
        super().__init__(collection_name)
        # Initialize Pinecone client
        
    @property
    def db_type(self) -> str:
        return "pinecone"
    
    def setup(self):
        # Initialize collection/schema
        pass
        
    def write_documents(self, documents):
        # Store documents with vectors
        pass
    
    def list_documents(self, limit=10, offset=0):
        # Retrieve documents
        pass
    
    def count_documents(self) -> int:
        # Get document count
        pass
    
    def delete_documents(self, document_ids):
        # Delete documents by ID
        pass
    
    def delete_collection(self, collection_name=None):
        # Delete entire collection
        pass
    
    def create_query_agent(self):
        # Create query agent
        pass
    
    def cleanup(self):
        # Clean up resources
        pass
```

### Working with Examples

The `examples/` directory contains practical examples for each supported vector database:

- **`milvus_example.py`**: Demonstrates Milvus usage with proper vector dimensions (1536)
- **`weaviate_example.py`**: Demonstrates Weaviate usage with metadata handling

When adding a new vector database implementation:

1. **Follow the existing pattern**: Use the same structure as existing examples
2. **Include environment validation**: Check for required environment variables
3. **Add comprehensive error handling**: Use try-catch blocks with helpful error messages
4. **Include cleanup**: Proper resource cleanup in finally blocks
5. **Update examples/README.md**: Document the new example with prerequisites and usage instructions
6. **Test the example**: Ensure it runs successfully with proper configuration
7. **Integration tests**: Examples are automatically validated via `test_integration_examples.py`

The integration tests validate:
- Example file structure and imports
- Execution without errors (with mocked dependencies)
- Environment variable handling
- Error handling patterns
- Cleanup procedures
- Output formatting standards

Example structure for a new database example:

```python
#!/usr/bin/env python3
"""
[Database Name] Vector Database Example

This example demonstrates how to use the maestro-knowledge library with [Database Name].
"""

import sys
import os
from src.db.vector_db_factory import create_vector_database

def main():
    # Check environment variables
    # Create database instance
    # Set up database
    # Write documents
    # List documents
    # Count documents
    # Delete documents (demonstrate CRUD operations)
    # Cleanup

if __name__ == "__main__":
    main()
```

## Style Guides

### Python Style Guide

* Use 4 spaces for indentation rather than tabs
* Keep lines to a maximum of 79 characters
* Use docstrings for all public modules, functions, classes, and methods
* Use spaces around operators and after commas
* Follow PEP 8 guidelines
* Include warning filters for clean output in test files

### JavaScript Style Guide

* Use 2 spaces for indentation rather than tabs
* Keep lines to a maximum of 100 characters
* Use semicolons
* Use single quotes for strings unless you are writing JSON
* Follow the Airbnb JavaScript Style Guide

### Documentation Style Guide

* Use [Markdown](https://daringfireball.net/projects/markdown)
* Reference methods and classes in markdown with the following syntax:
  * Reference classes with `ClassName`
  * Reference instance methods with `ClassName#methodName`
  * Reference class methods with `ClassName.methodName`
* Update documentation in the `docs/` directory
* Keep the main `README.md` focused on quick start and overview

## Additional Notes

### Issue and Pull Request Labels

This section lists the labels we use to help us track and manage issues and pull requests.

* `bug` - Issues that are bugs
* `documentation` - Issues for improving or updating our documentation
* `enhancement` - Issues for enhancing a feature
* `good first issue` - Good for newcomers
* `help wanted` - Extra attention is needed
* `invalid` - Issues that can't be reproduced or are invalid
* `question` - Further information is requested
* `wontfix` - Issues that won't be fixed
* `vector-db` - Issues related to vector database implementations

## Development Process

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Code Quality and Linting

Before submitting a pull request, please ensure that:

1. All tests pass (`./tests.sh`)
2. All linting checks pass (`./lint.sh`)
3. The code is properly formatted
4. Documentation is updated
5. New tests are added for new functionality
6. Warning filters are included for clean test output
7. Examples are tested and working (if adding new database support)

### Running Code Quality Checks

We use Ruff for linting and formatting. Run the comprehensive check:

```bash
./lint.sh
```

This script will:
- Check all source files for linting issues
- Check all test files for linting issues  
- Check all example files for linting issues
- Verify code formatting is correct

### Manual Code Quality Commands

If you need to run individual checks:

```bash
# Install development dependencies
uv pip install ruff bandit safety

# Run linting only
uv run ruff check src/ tests/ examples/

# Check formatting only
uv run ruff format --check src/ tests/ examples/

# Auto-fix formatting issues
uv run ruff format src/ tests/ examples/

# Run security checks
uv run bandit -r src/
uv run safety check
```

### Integration Tests

We have comprehensive integration tests that validate our examples:

```bash
# Run all tests including integration tests
./tests.sh

# The test suite now includes:
# - Unit tests for core functionality
# - Integration tests for examples
# - Mocked database tests
# - Environment validation tests
```

### Test Organization

The test suite follows the modular structure:

- **Base tests**: `test_vector_db_base.py` - Tests for abstract base class
- **Implementation tests**: `test_vector_db_[name].py` - Tests for specific implementations
- **Factory tests**: `test_vector_db_factory.py` - Tests for factory function
- **Compatibility tests**: `test_vector_db.py` - Tests for compatibility layer
- **Integration tests**: `test_integration_examples.py` - Tests that validate example files work correctly

Each test file should:
- Include appropriate warning filters
- Use mocking to avoid external dependencies
- Test both success and error cases
- Include proper cleanup in teardown methods

## License

By contributing to Maestro Knowledge, you agree that your contributions will be licensed under its MIT License. 