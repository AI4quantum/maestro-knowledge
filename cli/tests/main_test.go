package main

import (
	"os"
	"os/exec"
	"testing"
)

// TestMain runs before all tests
func TestMain(m *testing.M) {
	// Check if CLI binary exists, if not build it
	if _, err := os.Stat("../../maestro-k"); os.IsNotExist(err) {
		buildCLI()
	}

	// Run tests
	code := m.Run()

	// Cleanup
	os.Exit(code)
}

// buildCLI builds the CLI binary for testing
func buildCLI() {
	cmd := exec.Command("go", "build", "-o", "../../maestro-k", "./src")
	cmd.Dir = ".."

	if err := cmd.Run(); err != nil {
		panic("Failed to build CLI: " + err.Error())
	}
}

// TestCLIVersion tests the --version flag
func TestCLIVersion(t *testing.T) {
	cmd := exec.Command("../../maestro-k", "--version")
	output, err := cmd.Output()

	if err != nil {
		t.Fatalf("Failed to run version command: %v", err)
	}

	versionOutput := string(output)
	if versionOutput == "" {
		t.Error("Version output should not be empty")
	}

	// Check if version contains expected format
	if len(versionOutput) < 3 {
		t.Errorf("Version output too short: %s", versionOutput)
	}
}

// TestCLIHelp tests the --help flag
func TestCLIHelp(t *testing.T) {
	cmd := exec.Command("../../maestro-k", "--help")
	output, err := cmd.Output()

	if err != nil {
		t.Fatalf("Failed to run help command: %v", err)
	}

	helpOutput := string(output)

	// Check for expected help content
	expectedContent := []string{
		"maestro-k",
		"Usage:",
		"validate",
		"--help",
		"--version",
	}

	for _, expected := range expectedContent {
		if !contains(helpOutput, expected) {
			t.Errorf("Help output should contain '%s'", expected)
		}
	}
}

// TestValidateHelp tests the validate command help
func TestValidateHelp(t *testing.T) {
	cmd := exec.Command("../../maestro-k", "validate", "--help")
	output, err := cmd.Output()

	if err != nil {
		t.Fatalf("Failed to run validate help command: %v", err)
	}

	helpOutput := string(output)

	// Check for expected validate help content
	expectedContent := []string{
		"validate",
		"YAML_FILE",
		"SCHEMA_FILE",
		"Validate YAML files against schemas",
	}

	for _, expected := range expectedContent {
		if !contains(helpOutput, expected) {
			t.Errorf("Validate help output should contain '%s'", expected)
		}
	}
}

// TestValidateNoArgs tests validate command with no arguments
func TestValidateNoArgs(t *testing.T) {
	cmd := exec.Command("../../maestro-k", "validate")
	err := cmd.Run()

	// Should fail with no arguments
	if err == nil {
		t.Error("Validate command should fail with no arguments")
	}
}

// TestValidateWithNonExistentFile tests validate with a non-existent file
func TestValidateWithNonExistentFile(t *testing.T) {
	cmd := exec.Command("../../maestro-k", "validate", "nonexistent.yaml")
	output, err := cmd.CombinedOutput()

	// Should fail with non-existent file
	if err == nil {
		t.Error("Validate command should fail with non-existent file")
	}

	outputStr := string(output)
	if !contains(outputStr, "not found") {
		t.Errorf("Error message should mention 'not found', got: %s", outputStr)
	}
}

// TestValidateWithVerboseFlag tests the verbose flag
func TestValidateWithVerboseFlag(t *testing.T) {
	// Create a temporary YAML file for testing
	tempFile := createTempYAMLFile(t)
	defer os.Remove(tempFile)

	cmd := exec.Command("../../maestro-k", "validate", "--verbose", tempFile)
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("Validate command failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !contains(outputStr, "Validating YAML file") {
		t.Errorf("Verbose output should show validation message, got: %s", outputStr)
	}
}

// TestValidateWithSilentFlag tests the silent flag
func TestValidateWithSilentFlag(t *testing.T) {
	// Create a temporary YAML file for testing
	tempFile := createTempYAMLFile(t)
	defer os.Remove(tempFile)

	cmd := exec.Command("../../maestro-k", "validate", "--silent", tempFile)
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("Validate command failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if contains(outputStr, "✅ Validation successful") {
		t.Error("Silent mode should not show success message")
	}
}

// TestValidateWithDryRunFlag tests the dry-run flag
func TestValidateWithDryRunFlag(t *testing.T) {
	// Create a temporary YAML file for testing
	tempFile := createTempYAMLFile(t)
	defer os.Remove(tempFile)

	cmd := exec.Command("../../maestro-k", "validate", "--dry-run", tempFile)
	output, err := cmd.CombinedOutput()

	if err != nil {
		t.Fatalf("Validate command failed: %v, output: %s", err, string(output))
	}

	outputStr := string(output)
	if !contains(outputStr, "[DRY RUN]") {
		t.Errorf("Dry run should show [DRY RUN] message, got: %s", outputStr)
	}
}

// Helper functions

// contains checks if a string contains a substring
func contains(s, substr string) bool {
	return len(s) >= len(substr) && (s == substr || len(substr) == 0 ||
		(len(s) > len(substr) && (s[:len(substr)] == substr ||
			s[len(s)-len(substr):] == substr ||
			containsSubstring(s, substr))))
}

// containsSubstring checks if a string contains a substring (simplified)
func containsSubstring(s, substr string) bool {
	for i := 0; i <= len(s)-len(substr); i++ {
		if s[i:i+len(substr)] == substr {
			return true
		}
	}
	return false
}

// createTempYAMLFile creates a temporary YAML file for testing
func createTempYAMLFile(t *testing.T) string {
	content := `---
name: test-config
version: 1.0
settings:
  debug: true
  timeout: 30
`

	tmpfile, err := os.CreateTemp("", "test-*.yaml")
	if err != nil {
		t.Fatalf("Failed to create temp file: %v", err)
	}

	if _, err := tmpfile.Write([]byte(content)); err != nil {
		t.Fatalf("Failed to write to temp file: %v", err)
	}

	if err := tmpfile.Close(); err != nil {
		t.Fatalf("Failed to close temp file: %v", err)
	}

	return tmpfile.Name()
}
