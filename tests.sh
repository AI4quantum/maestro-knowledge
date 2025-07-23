#!/bin/bash

# Combined test script for both Python and CLI components

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# Check if CLI testing is requested
RUN_CLI_TESTS=${1:-false}

if [ "$RUN_CLI_TESTS" = "cli" ] || [ "$RUN_CLI_TESTS" = "all" ]; then
    print_header "Running CLI Workflow Tests..."
    
    # Check if we're in the right directory
    if [ ! -f "cli/go.mod" ]; then
        print_error "CLI tests require cli/go.mod to exist"
        exit 1
    fi

    # Step 1: Set up Go
    print_status "Step 1: Setting up Go..."
    if command -v go &> /dev/null; then
        GO_VERSION=$(go version | awk '{print $3}' | sed 's/go//')
        print_status "✓ Go $GO_VERSION detected"
    else
        print_error "Go is not installed"
        exit 1
    fi

    # Step 2: Build CLI
    print_status "Step 2: Building CLI..."
    cd cli
    if ./build.sh; then
        print_status "✓ CLI build successful"
    else
        print_error "CLI build failed"
        exit 1
    fi
    cd ..

    # Step 3: Test CLI
    print_status "Step 3: Testing CLI..."
    cd cli
    if ./tests.sh; then
        print_status "✓ CLI tests passed"
    else
        print_error "CLI tests failed"
        exit 1
    fi
    cd ..

    # Step 4: Test CLI functionality
    print_status "Step 4: Testing CLI functionality..."
    if ./maestro-k --version &> /dev/null; then
        print_status "✓ CLI version command works"
    else
        print_error "CLI version command failed"
        exit 1
    fi

    if ./maestro-k --help &> /dev/null; then
        print_status "✓ CLI help command works"
    else
        print_error "CLI help command failed"
        exit 1
    fi

    if ./maestro-k validate --help &> /dev/null; then
        print_status "✓ CLI validate help command works"
    else
        print_error "CLI validate help command failed"
        exit 1
    fi

    # Step 5: Test YAML validation
    print_status "Step 5: Testing YAML validation..."

    # Test with valid YAML
    if ./maestro-k validate --verbose tests/yamls/local_milvus.yaml &> /dev/null; then
        print_status "✓ Valid YAML validation works"
    else
        print_error "Valid YAML validation failed"
        exit 1
    fi

    # Test with schema validation (if schema exists)
    if [ -f "schemas/vector-database-schema.json" ]; then
        if ./maestro-k validate --verbose schemas/vector-database-schema.json tests/yamls/local_milvus.yaml &> /dev/null; then
            print_status "✓ Schema validation works"
        else
            print_error "Schema validation failed"
            exit 1
        fi
    else
        print_warning "schemas/vector-database-schema.json not found, skipping schema validation test"
    fi

    # Test with invalid YAML (should fail)
    if ./maestro-k validate --verbose tests/yamls/invalid-test.yaml &> /dev/null; then
        print_warning "⚠ Invalid YAML validation should have failed"
    else
        print_status "✓ Invalid YAML correctly rejected"
    fi

    # Step 6: Show CLI info
    print_status "Step 6: Showing CLI info..."
    echo "CLI binary information:"
    ls -lh maestro-k
    file maestro-k
    echo "CLI version:"
    ./maestro-k --version

    print_header "CLI Workflow Tests Completed Successfully! 🎉"
fi

# Run Python tests (default behavior)
if [ "$RUN_CLI_TESTS" != "cli" ]; then
    print_header "Running Python Tests..."
    
    # Add some test .env variables
    export OPENAI_API_KEY=fake-openai-key
    export WEAVIATE_API_KEY=fake-weaviate-key
    export WEAVIATE_URL=fake-weaviate-url.com

    # Run all tests with the correct PYTHONPATH and robustly suppress Pydantic deprecation warnings
    PYTHONWARNINGS="ignore:PydanticDeprecatedSince20" PYTHONPATH=src uv run pytest -v
    
    print_header "Python Tests Completed Successfully! 🎉"
fi

print_status "All tests completed!" 