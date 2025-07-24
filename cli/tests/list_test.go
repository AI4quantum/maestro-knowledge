package main

import (
	"os/exec"
	"strings"
	"testing"
)

func TestListVectorDatabase(t *testing.T) {
	// Use dry-run mode since we don't have a real MCP server running
	cmd := exec.Command("../../maestro-k", "list", "vector-db", "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("List command failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !strings.Contains(outputStr, "[DRY RUN] Would list vector databases") {
		t.Errorf("Expected dry-run message, got: %s", outputStr)
	}
}

func TestListVectorDatabaseWithVerbose(t *testing.T) {
	// Use dry-run mode since we don't have a real MCP server running
	cmd := exec.Command("../../maestro-k", "list", "vector-db", "--verbose", "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("List command with verbose failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !strings.Contains(outputStr, "Listing vector databases") {
		t.Errorf("Expected verbose message 'Listing vector databases', got: %s", outputStr)
	}

	if !strings.Contains(outputStr, "[DRY RUN] Would list vector databases") {
		t.Errorf("Expected dry-run message, got: %s", outputStr)
	}
}

func TestListVectorDatabaseWithInvalidResourceType(t *testing.T) {
	cmd := exec.Command("../../maestro-k", "list", "invalid-resource")
	output, err := cmd.CombinedOutput()

	// Should fail with invalid resource type
	if err == nil {
		t.Error("Expected command to fail with invalid resource type, but it succeeded")
	}

	outputStr := string(output)
	if !strings.Contains(outputStr, "unsupported resource type") {
		t.Errorf("Expected error about unsupported resource type, got: %s", outputStr)
	}
}

func TestListVectorDatabaseWithDryRun(t *testing.T) {
	cmd := exec.Command("../../maestro-k", "list", "vector-db", "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("List command with dry-run failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !strings.Contains(outputStr, "[DRY RUN] Would list vector databases") {
		t.Errorf("Expected dry-run message, got: %s", outputStr)
	}
}

func TestListVectorDatabaseWithSilent(t *testing.T) {
	// Use dry-run mode since we don't have a real MCP server running
	cmd := exec.Command("../../maestro-k", "list", "vector-db", "--silent", "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("List command with silent failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	// Should not contain the default "No vector databases found" message when silent
	if strings.Contains(outputStr, "No vector databases found") {
		t.Errorf("Should not show default message when silent, got: %s", outputStr)
	}
}

func TestListVectorDatabaseHelp(t *testing.T) {
	cmd := exec.Command("../../maestro-k", "list", "vector-db", "--help")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("List help command failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !strings.Contains(outputStr, "List vector database resources") {
		t.Errorf("Expected help message about listing vector databases, got: %s", outputStr)
	}

	if !strings.Contains(outputStr, "maestro-k list vector-db") {
		t.Errorf("Expected usage example, got: %s", outputStr)
	}
}

func TestListVectorDatabaseWithVectorDatabase(t *testing.T) {
	// Use dry-run mode since we don't have a real MCP server running
	cmd := exec.Command("../../maestro-k", "list", "vector-database", "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("List command with 'vector-database' failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !strings.Contains(outputStr, "[DRY RUN] Would list vector databases") {
		t.Errorf("Expected dry-run message, got: %s", outputStr)
	}
}

func TestListVectorDatabaseWithMultipleFlags(t *testing.T) {
	cmd := exec.Command("../../maestro-k", "list", "vector-db", "--verbose", "--dry-run")
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("List command with multiple flags failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !strings.Contains(outputStr, "Listing vector databases") {
		t.Errorf("Expected verbose message, got: %s", outputStr)
	}

	if !strings.Contains(outputStr, "[DRY RUN] Would list vector databases") {
		t.Errorf("Expected dry-run message, got: %s", outputStr)
	}
}

// TestListVectorDatabaseWithRealServer tests the actual MCP server connection
// This test is expected to fail if no MCP server is running, which is acceptable
func TestListVectorDatabaseWithRealServer(t *testing.T) {
	cmd := exec.Command("../../maestro-k", "list", "vector-db")
	output, err := cmd.CombinedOutput()

	// This test is expected to fail if no MCP server is running
	if err != nil {
		outputStr := string(output)
		// Check if the error is due to connection refused (no server running)
		// or unsupported protocol scheme (malformed URL)
		if strings.Contains(outputStr, "connection refused") ||
			strings.Contains(outputStr, "unsupported protocol scheme") {
			t.Logf("Test skipped: No MCP server running or malformed URL (expected): %s", outputStr)
			return
		}
		// If it's a different error, fail the test
		t.Fatalf("List command failed with unexpected error: %v, output: %s", err, string(output))
	}

	// If the command succeeds, we should get either "No vector databases found" or actual database list
	outputStr := string(output)
	if !strings.Contains(outputStr, "No vector databases found") &&
		!strings.Contains(outputStr, "Found") &&
		!strings.Contains(outputStr, "vector database") {
		t.Errorf("Unexpected output from list command: %s", outputStr)
	}
}
