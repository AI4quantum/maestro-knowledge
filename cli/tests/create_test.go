package main

import (
	"os"
	"os/exec"
	"testing"
)

// TestCreateVectorDatabase tests the create vector-database command
func TestCreateVectorDatabase(t *testing.T) {
	// Create a valid YAML file for testing
	validYAML := `---
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: test-milvus-basic
spec:
  type: milvus
  uri: localhost:19530
  collection_name: test_collection
  embedding: text-embedding-3-small
  mode: local
`

	tempFile := createTempFile(t, "valid-*.yaml", validYAML)
	defer os.Remove(tempFile)

	cmd := exec.Command("../maestro-k", "create", "vector-db", tempFile, "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("Create command failed with valid YAML: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !contains(outputStr, "[DRY RUN] Would create vector database") {
		t.Errorf("Should show dry run message for valid YAML, got: %s", outputStr)
	}
}

// TestCreateVectorDatabaseWithOverrides tests the create command with field overrides
func TestCreateVectorDatabaseWithOverrides(t *testing.T) {
	// Create a valid YAML file for testing
	validYAML := `---
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: test-milvus-overrides
spec:
  type: milvus
  uri: localhost:19530
  collection_name: test_collection
  embedding: text-embedding-3-small
  mode: local
`

	tempFile := createTempFile(t, "valid-*.yaml", validYAML)
	defer os.Remove(tempFile)

	cmd := exec.Command("../maestro-k", "create", "vector-db", tempFile, "--uri=localhost:8000", "--mode=remote", "--verbose", "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("Create command failed with overrides: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !contains(outputStr, "Overriding URI: localhost:19530 -> localhost:8000") {
		t.Errorf("Should show URI override, got: %s", outputStr)
	}
	if !contains(outputStr, "Overriding mode: local -> remote") {
		t.Errorf("Should show mode override, got: %s", outputStr)
	}
	if !contains(outputStr, "[DRY RUN] Would create vector database") {
		t.Errorf("Should show dry run message, got: %s", outputStr)
	}
}

// TestCreateVectorDatabaseWithInvalidResourceType tests invalid resource type
func TestCreateVectorDatabaseWithInvalidResourceType(t *testing.T) {
	cmd := exec.Command("../maestro-k", "create", "invalid-resource", "test.yaml")
	output, _ := cmd.CombinedOutput()

	// Should show help message for invalid resource type
	outputStr := string(output)
	if !contains(outputStr, "Available Commands:") {
		t.Errorf("Should show available commands for invalid resource type, got: %s", outputStr)
	}
}

// TestCreateVectorDatabaseWithNonExistentFile tests with non-existent file
func TestCreateVectorDatabaseWithNonExistentFile(t *testing.T) {
	cmd := exec.Command("../maestro-k", "create", "vector-db", "nonexistent.yaml")
	output, err := cmd.CombinedOutput()

	// Should fail with non-existent file
	if err == nil {
		t.Error("Create command should fail with non-existent file")
	}

	outputStr := string(output)
	if !contains(outputStr, "not found") {
		t.Errorf("Error message should mention 'not found', got: %s", outputStr)
	}
}

// TestCreateVectorDatabaseWithInvalidYAML tests with invalid YAML
func TestCreateVectorDatabaseWithInvalidYAML(t *testing.T) {
	// Create an invalid YAML file
	invalidYAML := `---
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: test-milvus-invalid
spec:
  type: milvus
  uri: "localhost:19530
  collection_name: test_collection
  embedding: text-embedding-3-small
  mode: local
`

	tempFile := createTempFile(t, "invalid-*.yaml", invalidYAML)
	defer os.Remove(tempFile)

	cmd := exec.Command("../maestro-k", "create", "vector-db", tempFile)
	output, err := cmd.CombinedOutput()

	// Should fail with invalid YAML
	if err == nil {
		t.Error("Create command should fail with invalid YAML")
	}

	outputStr := string(output)
	if !contains(outputStr, "failed to parse YAML") {
		t.Errorf("Error message should mention YAML parsing error, got: %s", outputStr)
	}
}

// TestCreateVectorDatabaseWithInvalidConfig tests with invalid configuration
func TestCreateVectorDatabaseWithInvalidConfig(t *testing.T) {
	// Create YAML with invalid configuration
	invalidYAML := `---
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: test-milvus
spec:
  type: invalid-type
  uri: localhost:19530
  collection_name: test_collection
  embedding: text-embedding-3-small
  mode: local
`

	tempFile := createTempFile(t, "invalid-*.yaml", invalidYAML)
	defer os.Remove(tempFile)

	cmd := exec.Command("../maestro-k", "create", "vector-db", tempFile)
	output, err := cmd.CombinedOutput()

	// Should fail with invalid configuration
	if err == nil {
		t.Error("Create command should fail with invalid configuration")
	}

	outputStr := string(output)
	if !contains(outputStr, "invalid spec.type") {
		t.Errorf("Error message should mention invalid spec.type, got: %s", outputStr)
	}
}

// TestCreateVectorDatabaseDryRun tests dry run functionality
func TestCreateVectorDatabaseDryRun(t *testing.T) {
	// Create a valid YAML file for testing
	validYAML := `---
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: test-milvus-dryrun
spec:
  type: milvus
  uri: localhost:19530
  collection_name: test_collection
  embedding: text-embedding-3-small
  mode: local
`

	tempFile := createTempFile(t, "valid-*.yaml", validYAML)
	defer os.Remove(tempFile)

	cmd := exec.Command("../maestro-k", "create", "vector-db", tempFile, "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("Create command failed with dry run: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !contains(outputStr, "[DRY RUN] Would create vector database") {
		t.Errorf("Should show dry run message, got: %s", outputStr)
	}
}

// TestCreateVectorDatabaseSilent tests silent mode
func TestCreateVectorDatabaseSilent(t *testing.T) {
	// Create a valid YAML file for testing
	validYAML := `---
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: test-milvus-silent
spec:
  type: milvus
  uri: localhost:19530
  collection_name: test_collection
  embedding: text-embedding-3-small
  mode: local
`

	tempFile := createTempFile(t, "valid-*.yaml", validYAML)
	defer os.Remove(tempFile)

	cmd := exec.Command("../maestro-k", "create", "vector-db", tempFile, "--silent", "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("Create command failed with silent mode: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if contains(outputStr, "[DRY RUN] Would create vector database") {
		t.Error("Silent mode should not show dry run message")
	}
	if outputStr != "" {
		t.Errorf("Silent mode should show no output, got: %s", outputStr)
	}
}

// TestCreateVectorDatabaseWithVdbShortcut tests the create command with vdb shortcut
func TestCreateVectorDatabaseWithVdbShortcut(t *testing.T) {
	// Create a valid YAML file for testing
	validYAML := `---
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: test-milvus-vdb
spec:
  type: milvus
  uri: localhost:19530
  collection_name: test_collection
  embedding: text-embedding-3-small
  mode: local
`

	tempFile := createTempFile(t, "valid-*.yaml", validYAML)
	defer os.Remove(tempFile)

	cmd := exec.Command("../maestro-k", "create", "vdb", tempFile, "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("Create command with vdb shortcut failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !contains(outputStr, "[DRY RUN] Would create vector database") {
		t.Errorf("Should show dry run message, got: %s", outputStr)
	}
}

// TestCreateVectorDatabaseWithDimension tests the create command with a dimension override
func TestCreateVectorDatabaseWithDimension(t *testing.T) {
	// Create a valid YAML file for testing
	validYAML := `---
apiVersion: maestro/v1alpha1
kind: VectorDatabase
metadata:
  name: test-milvus-dimension
spec:
  type: milvus
  uri: localhost:19530
  collection_name: test_collection
  embedding: text-embedding-3-small
  mode: local
`

	tempFile := createTempFile(t, "valid-*.yaml", validYAML)
	defer os.Remove(tempFile)

	cmd := exec.Command("../maestro-k", "create", "vector-db", tempFile, "--dimension=768", "--verbose", "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("Create command failed with dimension override: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !contains(outputStr, "Overriding dimension: 0 -> 768") {
		t.Errorf("Should show dimension override, got: %s", outputStr)
	}
	if !contains(outputStr, "[DRY RUN] Would create vector database") {
		t.Errorf("Should show dry run message, got: %s", outputStr)
	}
}
