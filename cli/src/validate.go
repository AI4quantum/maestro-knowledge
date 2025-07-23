package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
	"github.com/xeipuuv/gojsonschema"
	"gopkg.in/yaml.v3"
)

var validateCmd = &cobra.Command{
	Use:   "validate [YAML_FILE] [SCHEMA_FILE]",
	Short: "Validate YAML files against schemas",
	Long: `Validate YAML files against schemas.
	
Usage:
  maestro-k validate YAML_FILE [options]
  maestro-k validate SCHEMA_FILE YAML_FILE [options]

Examples:
  maestro-k validate config.yaml
  maestro-k validate schema.json config.yaml`,
	Args: cobra.RangeArgs(1, 2),
	RunE: func(cmd *cobra.Command, args []string) error {
		var yamlFile, schemaFile string

		if len(args) == 1 {
			// Single argument: validate YAML_FILE
			yamlFile = args[0]
			schemaFile = "" // Will use default schema
		} else {
			// Two arguments: validate SCHEMA_FILE YAML_FILE
			schemaFile = args[0]
			yamlFile = args[1]
		}

		return validateFiles(yamlFile, schemaFile)
	},
}

func validateFiles(yamlFile, schemaFile string) error {
	if verbose {
		fmt.Printf("Validating YAML file: %s\n", yamlFile)
		if schemaFile != "" {
			fmt.Printf("Using schema file: %s\n", schemaFile)
		} else {
			fmt.Println("Using default schema")
		}
	}

	// Check if YAML file exists
	if _, err := os.Stat(yamlFile); os.IsNotExist(err) {
		return fmt.Errorf("YAML file not found: %s", yamlFile)
	}

	// Check if schema file exists (if provided)
	if schemaFile != "" {
		if _, err := os.Stat(schemaFile); os.IsNotExist(err) {
			return fmt.Errorf("Schema file not found: %s", schemaFile)
		}
	}

	// TODO: Implement actual YAML validation logic
	// For now, just check file existence and basic structure

	if dryRun {
		fmt.Println("[DRY RUN] Would validate files")
		return nil
	}

	// Perform validation
	if err := performValidation(yamlFile, schemaFile); err != nil {
		return fmt.Errorf("validation failed: %w", err)
	}

	if !silent {
		fmt.Println("✅ Validation successful")
	}

	return nil
}

func performValidation(yamlFile, schemaFile string) error {
	if verbose {
		fmt.Printf("Performing validation of %s\n", filepath.Base(yamlFile))
	}

	// Step 1: Parse the YAML file
	yamlData, err := os.ReadFile(yamlFile)
	if err != nil {
		return fmt.Errorf("failed to read YAML file: %w", err)
	}

	// Parse YAML to check if it's valid YAML
	var yamlContent interface{}
	if err := yaml.Unmarshal(yamlData, &yamlContent); err != nil {
		return fmt.Errorf("invalid YAML format: %w", err)
	}

	// Step 2: If no schema file provided, just validate YAML syntax
	if schemaFile == "" {
		if verbose {
			fmt.Println("No schema provided, only validating YAML syntax")
		}
		return nil // YAML is valid if we got here
	}

	// Step 3: Load and validate against JSON schema
	// Convert to absolute path for schema file
	absSchemaPath, err := filepath.Abs(schemaFile)
	if err != nil {
		return fmt.Errorf("failed to get absolute path for schema: %w", err)
	}

	// Convert YAML to JSON for validation
	jsonData, err := yamlToJSON(yamlData)
	if err != nil {
		return fmt.Errorf("failed to convert YAML to JSON: %w", err)
	}

	schemaLoader := gojsonschema.NewReferenceLoader("file://" + absSchemaPath)
	documentLoader := gojsonschema.NewStringLoader(string(jsonData))

	// Validate the document against the schema
	result, err := gojsonschema.Validate(schemaLoader, documentLoader)
	if err != nil {
		return fmt.Errorf("schema validation error: %w", err)
	}

	// Step 4: Check validation results
	if !result.Valid() {
		if verbose {
			fmt.Println("Validation failed:")
		}

		var errors []string
		for _, err := range result.Errors() {
			errorMsg := fmt.Sprintf("- %s: %s", err.Field(), err.Description())
			errors = append(errors, errorMsg)
			if verbose {
				fmt.Println(errorMsg)
			}
		}

		return fmt.Errorf("validation failed with %d errors", len(result.Errors()))
	}

	if verbose {
		fmt.Println("Schema validation passed")
	}

	return nil
}

// yamlToJSON converts YAML data to JSON format
func yamlToJSON(yamlData []byte) ([]byte, error) {
	var yamlContent interface{}

	// Parse YAML
	if err := yaml.Unmarshal(yamlData, &yamlContent); err != nil {
		return nil, fmt.Errorf("failed to parse YAML: %w", err)
	}

	// Marshal to JSON
	jsonData, err := json.Marshal(yamlContent)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal to JSON: %w", err)
	}

	return jsonData, nil
}
