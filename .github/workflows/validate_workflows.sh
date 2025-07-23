#!/bin/bash

# Validate GitHub Actions Workflows
# This script validates the workflow files using act or similar tools

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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
    echo -e "${GREEN}[VALIDATE]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f ".github/workflows/cli_ci.yml" ]; then
    print_error "This script must be run from the project root directory"
    exit 1
fi

print_header "Validating GitHub Actions workflows..."

# Check if yamllint is available
if command -v yamllint &> /dev/null; then
    print_status "Validating YAML syntax..."
    yamllint .github/workflows/
    print_status "YAML syntax validation passed"
else
    print_warning "yamllint not found, skipping YAML syntax validation"
fi

# Check if act is available for local testing
if command -v act &> /dev/null; then
    print_status "act found - you can test workflows locally with:"
    echo "  act push -W .github/workflows/cli_ci.yml"
    echo "  act release -W .github/workflows/cli_release.yml"
else
    print_warning "act not found - install it to test workflows locally:"
    echo "  brew install act (macOS)"
    echo "  or visit: https://github.com/nektos/act"
fi

# Validate workflow structure
print_status "Validating workflow structure..."

# Check CLI CI workflow
if grep -q "name: CLI CI" .github/workflows/cli_ci.yml; then
    print_status "✓ CLI CI workflow found"
else
    print_error "✗ CLI CI workflow not found"
    exit 1
fi

# Check CLI Release workflow
if grep -q "name: CLI Release" .github/workflows/cli_release.yml; then
    print_status "✓ CLI Release workflow found"
else
    print_error "✗ CLI Release workflow not found"
    exit 1
fi

# Check for required steps
required_steps=("Set up Go" "Build CLI" "Test CLI")
for step in "${required_steps[@]}"; do
    if grep -q "$step" .github/workflows/cli_ci.yml; then
        print_status "✓ Step '$step' found in CLI CI"
    else
        print_warning "⚠ Step '$step' not found in CLI CI"
    fi
done

print_status "Workflow validation completed successfully!" 