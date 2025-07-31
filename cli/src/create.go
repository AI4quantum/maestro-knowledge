package main

import (
	"fmt"
	"os"
	"regexp"
	"strings"

	"github.com/spf13/cobra"
	"gopkg.in/yaml.v3"
)

// VectorDatabaseConfig represents the structure of a vector database configuration
type VectorDatabaseConfig struct {
	APIVersion string             `yaml:"apiVersion"`
	Kind       string             `yaml:"kind"`
	Metadata   Metadata           `yaml:"metadata"`
	Spec       VectorDatabaseSpec `yaml:"spec"`
}

type Metadata struct {
	Name   string            `yaml:"name"`
	Labels map[string]string `yaml:"labels,omitempty"`
}

type VectorDatabaseSpec struct {
	Type           string `yaml:"type"`
	URI            string `yaml:"uri"`
	CollectionName string `yaml:"collection_name"`
	Embedding      string `yaml:"embedding"`
	Mode           string `yaml:"mode"`
	Dimension      int    `yaml:"dimension,omitempty"`
}

// replaceEnvVars replaces {{ENV_VAR_NAME}} placeholders with environment variable values
func replaceEnvVars(content string) (string, error) {
	// Regex to match {{ENV_VAR_NAME}} pattern
	re := regexp.MustCompile(`\{\{([A-Z_][A-Z0-9_]*)\}\}`)

	var missingVars []string

	result := re.ReplaceAllStringFunc(content, func(match string) string {
		// Extract the environment variable name from {{ENV_VAR_NAME}}
		envVarName := strings.Trim(match, "{}")

		// Get the environment variable value
		envValue := os.Getenv(envVarName)

		if envValue == "" {
			// If environment variable is not set, collect it for error reporting
			missingVars = append(missingVars, envVarName)
			if verbose && !silent {
				fmt.Printf("Warning: Environment variable %s is not set\n", envVarName)
			}
			return "" // Replace with empty string to avoid YAML parsing issues
		}

		if verbose && !silent {
			fmt.Printf("Replacing {{%s}} with environment variable value\n", envVarName)
		}

		return envValue
	})

	// If there are missing environment variables, return an error
	if len(missingVars) > 0 {
		return result, fmt.Errorf("missing required environment variables: %s", strings.Join(missingVars, ", "))
	}

	return result, nil
}

var createCmd = &cobra.Command{
	Use:   "create",
	Short: "Create vector database resources",
	Long: `Create vector database resources from YAML files, create collections, or create documents.
	
Usage:
  maestro-k create vector-database YAML_FILE [options]
  maestro-k create vector-db YAML_FILE [options]
  maestro-k create vdb YAML_FILE [options]
  maestro-k create collection VDB_NAME COLLECTION_NAME [options]
  maestro-k create vdb-col VDB_NAME COLLECTION_NAME [options]
  maestro-k create col VDB_NAME COLLECTION_NAME [options]
  maestro-k create document VDB_NAME COLLECTION_NAME DOC_NAME --file-name=FILE_NAME [options]
  maestro-k create vdb-doc VDB_NAME COLLECTION_NAME DOC_NAME --file-name=FILE_NAME [options]
  maestro-k create doc VDB_NAME COLLECTION_NAME DOC_NAME --file-name=FILE_NAME [options]

Examples:
  maestro-k create vector-db config.yaml
  maestro-k create vdb config.yaml --uri=localhost:8000 --mode=local
  maestro-k create collection my-database my-collection
  maestro-k create col my-database my-collection --embedding=text-embedding-3-small
  maestro-k create document my-database my-collection my-doc --file-name=document.txt
  maestro-k create doc my-database my-collection my-doc --file-name=document.txt --embed=text-embedding-3-small`,
}

// Flags for overriding spec fields
var (
	overrideType           string
	overrideURI            string
	overrideCollectionName string
	overrideEmbedding      string
	overrideMode           string
	overrideDimension      int
)

func createVectorDatabase(yamlFile string) error {
	if verbose && !silent {
		fmt.Printf("Creating vector database from: %s\n", yamlFile)
	}

	// Check if YAML file exists
	if _, err := os.Stat(yamlFile); os.IsNotExist(err) {
		return fmt.Errorf("YAML file not found: %s", yamlFile)
	}

	// Read and parse YAML file
	config, err := loadVectorDatabaseConfig(yamlFile)
	if err != nil {
		return fmt.Errorf("failed to load configuration: %w", err)
	}

	// Apply overrides (this will show override messages if verbose is enabled and not silent)
	applyOverrides(config)

	if dryRun {
		if !silent {
			fmt.Println("[DRY RUN] Would create vector database")
		}
		return nil
	}

	// Validate the configuration
	if err := validateVectorDatabaseConfig(config); err != nil {
		return fmt.Errorf("configuration validation failed: %w", err)
	}

	// Perform the creation
	if err := performVectorDatabaseCreation(config); err != nil {
		return fmt.Errorf("creation failed: %w", err)
	}

	if !silent {
		fmt.Printf("✅ Vector database '%s' created successfully\n", config.Metadata.Name)
	}

	return nil
}

func loadVectorDatabaseConfig(yamlFile string) (*VectorDatabaseConfig, error) {
	data, err := os.ReadFile(yamlFile)
	if err != nil {
		return nil, fmt.Errorf("failed to read YAML file: %w", err)
	}

	// Replace environment variable placeholders in the YAML content
	yamlContent := string(data)
	yamlContent, err = replaceEnvVars(yamlContent)
	if err != nil {
		return nil, fmt.Errorf("failed to process environment variables: %w", err)
	}

	var config VectorDatabaseConfig
	if err := yaml.Unmarshal([]byte(yamlContent), &config); err != nil {
		return nil, fmt.Errorf("failed to parse YAML: %w", err)
	}

	return &config, nil
}

func applyOverrides(config *VectorDatabaseConfig) {
	if overrideType != "" {
		if verbose && !silent {
			fmt.Printf("Overriding type: %s -> %s\n", config.Spec.Type, overrideType)
		}
		config.Spec.Type = overrideType
	}

	if overrideURI != "" {
		if verbose && !silent {
			fmt.Printf("Overriding URI: %s -> %s\n", config.Spec.URI, overrideURI)
		}
		config.Spec.URI = overrideURI
	}

	if overrideCollectionName != "" {
		if verbose && !silent {
			fmt.Printf("Overriding collection name: %s -> %s\n", config.Spec.CollectionName, overrideCollectionName)
		}
		config.Spec.CollectionName = overrideCollectionName
	}

	if overrideEmbedding != "" {
		if verbose && !silent {
			fmt.Printf("Overriding embedding: %s -> %s\n", config.Spec.Embedding, overrideEmbedding)
		}
		config.Spec.Embedding = overrideEmbedding
	}

	if overrideMode != "" {
		if verbose && !silent {
			fmt.Printf("Overriding mode: %s -> %s\n", config.Spec.Mode, overrideMode)
		}
		config.Spec.Mode = overrideMode
	}

	if overrideDimension != 0 {
		if verbose && !silent {
			fmt.Printf("Overriding dimension: %d -> %d\n", config.Spec.Dimension, overrideDimension)
		}
		config.Spec.Dimension = overrideDimension
	}
}

func validateVectorDatabaseConfig(config *VectorDatabaseConfig) error {
	// Basic validation
	if config.APIVersion != "maestro/v1alpha1" {
		return fmt.Errorf("invalid API version: %s", config.APIVersion)
	}

	if config.Kind != "VectorDatabase" {
		return fmt.Errorf("invalid kind: %s", config.Kind)
	}

	if config.Metadata.Name == "" {
		return fmt.Errorf("metadata.name is required")
	}

	// Validate spec fields
	if config.Spec.Type == "" {
		return fmt.Errorf("spec.type is required")
	}

	if config.Spec.Type != "milvus" && config.Spec.Type != "weaviate" {
		return fmt.Errorf("invalid spec.type: %s (must be 'milvus' or 'weaviate')", config.Spec.Type)
	}

	if config.Spec.URI == "" {
		return fmt.Errorf("spec.uri is required")
	}

	if config.Spec.CollectionName == "" {
		return fmt.Errorf("spec.collection_name is required")
	}

	if config.Spec.Embedding == "" {
		return fmt.Errorf("spec.embedding is required")
	}

	if config.Spec.Mode == "" {
		return fmt.Errorf("spec.mode is required")
	}

	if config.Spec.Mode != "local" && config.Spec.Mode != "remote" {
		return fmt.Errorf("invalid spec.mode: %s (must be 'local' or 'remote')", config.Spec.Mode)
	}

	if config.Spec.Dimension < 0 {
		return fmt.Errorf("invalid spec.dimension: %d (must be a non-negative integer)", config.Spec.Dimension)
	}

	return nil
}

func performVectorDatabaseCreation(config *VectorDatabaseConfig) error {
	if verbose {
		fmt.Printf("Creating vector database '%s' of type '%s'\n", config.Metadata.Name, config.Spec.Type)
		fmt.Printf("  URI: %s\n", config.Spec.URI)
		fmt.Printf("  Collection: %s\n", config.Spec.CollectionName)
		fmt.Printf("  Embedding: %s\n", config.Spec.Embedding)
		fmt.Printf("  Mode: %s\n", config.Spec.Mode)
		if config.Spec.Dimension > 0 {
			fmt.Printf("  Dimension: %d\n", config.Spec.Dimension)
		}
	}

	// Get MCP server URI
	serverURI, err := getMCPServerURI(mcpServerURI)
	if err != nil {
		return fmt.Errorf("failed to get MCP server URI: %w", err)
	}

	if verbose {
		fmt.Printf("Connecting to MCP server at: %s\n", serverURI)
	}

	// Create MCP client
	client, err := NewMCPClient(serverURI)
	if err != nil {
		return fmt.Errorf("failed to create MCP client: %w", err)
	}
	defer client.Close()

	// Check if database already exists
	exists, err := client.DatabaseExists(config.Metadata.Name)
	if err != nil {
		return fmt.Errorf("failed to check if database exists: %w", err)
	}
	if exists {
		return fmt.Errorf("vector database '%s' already exists", config.Metadata.Name)
	}

	// Call the MCP server to create the database with panic recovery
	var createErr error
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Convert panic to a user-friendly error
				createErr = fmt.Errorf("MCP server could not be reached at %s. Please ensure the server is running and accessible", serverURI)
			}
		}()
		createErr = client.CreateVectorDatabase(config.Metadata.Name, config.Spec.Type, config.Spec.CollectionName, config.Spec.Dimension)
	}()

	if createErr != nil {
		return fmt.Errorf("failed to create vector database: %w", createErr)
	}

	// Setup the database (create collections and configure embedding)
	if verbose {
		fmt.Printf("Setting up vector database with embedding: %s\n", config.Spec.Embedding)
	}

	var setupErr error
	func() {
		defer func() {
			if r := recover(); r != nil {
				// Convert panic to a user-friendly error
				setupErr = fmt.Errorf("MCP server could not be reached at %s. Please ensure the server is running and accessible", serverURI)
			}
		}()
		setupErr = client.SetupDatabase(config.Metadata.Name, config.Spec.Embedding)
	}()

	if setupErr != nil {
		return fmt.Errorf("failed to setup vector database: %w", setupErr)
	}

	if verbose {
		fmt.Println("Vector database creation completed successfully")
	}

	return nil
}
