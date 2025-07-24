package main

import (
	"fmt"

	"github.com/spf13/cobra"
)

var listCmd = &cobra.Command{
	Use:   "list (vector-database | vector-db)",
	Short: "List vector database resources",
	Long: `List vector database resources.

Usage:
  maestro-k list vector-database [options]
  maestro-k list vector-db [options]

Examples:
  maestro-k list vector-db
  maestro-k list vector-database --verbose
  maestro-k list vector-db --mcp-server-uri=http://localhost:8000`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		resourceType := args[0]

		// Validate resource type
		if resourceType != "vector-database" && resourceType != "vector-db" {
			return fmt.Errorf("unsupported resource type: %s. Use 'vector-database' or 'vector-db'", resourceType)
		}

		return listVectorDatabases()
	},
}

func listVectorDatabases() error {
	if verbose {
		fmt.Println("Listing vector databases...")
	}

	if dryRun {
		fmt.Println("[DRY RUN] Would list vector databases")
		return nil
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
	client := NewMCPClient(serverURI)

	// Call the MCP server to list databases
	databases, err := client.ListDatabases()
	if err != nil {
		return fmt.Errorf("failed to list vector databases: %w", err)
	}

	// Display results
	if len(databases) == 0 {
		if !silent {
			fmt.Println("No vector databases found")
		}
		return nil
	}

	if !silent {
		fmt.Printf("Found %d vector database(s):\n\n", len(databases))
	}

	for i, db := range databases {
		if !silent {
			fmt.Printf("%d. %s (%s)\n", i+1, db.Name, db.Type)
			fmt.Printf("   Collection: %s\n", db.Collection)
			fmt.Printf("   Documents: %d\n", db.DocumentCount)
			fmt.Println()
		}
	}

	if verbose {
		fmt.Println("Vector database listing completed successfully")
	}

	return nil
}
