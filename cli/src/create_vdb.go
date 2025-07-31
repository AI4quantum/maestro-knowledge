package main

import (
	"github.com/spf13/cobra"
)

var createVdbCmd = &cobra.Command{
	Use:   "vector-database YAML_FILE",
	Short: "Create a vector database from YAML file",
	Long: `Create a vector database from YAML file.
	
Usage:
  maestro-k create vector-database YAML_FILE [options]

Examples:
  maestro-k create vector-database config.yaml
  maestro-k create vector-database config.yaml --uri=localhost:8000 --mode=local`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		// Suppress usage for all errors except usage errors
		cmd.SilenceUsage = true

		yamlFile := args[0]
		return createVectorDatabase(yamlFile)
	},
}

var createVdbShortCmd = &cobra.Command{
	Use:   "vector-db YAML_FILE",
	Short: "Create a vector database from YAML file (alias for vector-database)",
	Long: `Create a vector database from YAML file.
	
Usage:
  maestro-k create vector-db YAML_FILE [options]

Examples:
  maestro-k create vector-db config.yaml
  maestro-k create vector-db config.yaml --uri=localhost:8000 --mode=local`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		// Suppress usage for all errors except usage errors
		cmd.SilenceUsage = true

		yamlFile := args[0]
		return createVectorDatabase(yamlFile)
	},
}

var createVdbVdbCmd = &cobra.Command{
	Use:   "vdb YAML_FILE",
	Short: "Create a vector database from YAML file (alias for vector-database)",
	Long: `Create a vector database from YAML file.
	
Usage:
  maestro-k create vdb YAML_FILE [options]

Examples:
  maestro-k create vdb config.yaml
  maestro-k create vdb config.yaml --uri=localhost:8000 --mode=local`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		// Suppress usage for all errors except usage errors
		cmd.SilenceUsage = true

		yamlFile := args[0]
		return createVectorDatabase(yamlFile)
	},
}

func init() {
	// Add flags for overriding spec fields to all vector database creation commands
	commands := []*cobra.Command{createVdbCmd, createVdbShortCmd, createVdbVdbCmd}
	for _, cmd := range commands {
		cmd.Flags().StringVar(&overrideType, "type", "", "Override the database type (milvus, weaviate)")
		cmd.Flags().StringVar(&overrideURI, "uri", "", "Override the connection URI")
		cmd.Flags().StringVar(&overrideCollectionName, "collection-name", "", "Override the collection name")
		cmd.Flags().StringVar(&overrideEmbedding, "embedding", "", "Override the embedding model")
		cmd.Flags().StringVar(&overrideMode, "mode", "", "Override the deployment mode (local, remote)")
		cmd.Flags().IntVar(&overrideDimension, "dimension", 0, "Override the vector dimension for the collection")
	}
}
