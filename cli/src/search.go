package main

import (
	"fmt"
	"strings"

	"github.com/spf13/cobra"
)



var searchCmd = &cobra.Command{
	Use:   "search",
	Short: "Search documents using natural language",
	Long: `Search documents in a vector database using natural language.

This command allows you to ask questions about documents stored in a vector database.
The query agent will search through the documents and return relevant documents.`,
	Example: `  maestro-k query "What is the main topic of the documents?" --vdb=my-vdb
  maestro-k query "Find information about API endpoints" --vdb=my-vdb --doc-limit 10`,
	Args: cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		query := args[0]
		vdbName, _ := cmd.Flags().GetString("vdb")
		collectionName, _ := cmd.Flags().GetString("collection")

		// Validate inputs
		if strings.TrimSpace(query) == "" {
			return fmt.Errorf("search cannot be empty")
		}

		// Use interactive selection if vdb name is not provided
		if vdbName == "" {
			var err error
			vdbName, err = PromptForVectorDatabase(vdbName)
			if err != nil {
				return fmt.Errorf("failed to select vector database: %w", err)
			}
		}

		// Use default collection if not specified
		if collectionName == "" {
			collectionName = "Test_collection_lowercase" // Default collection
		}

		return searchVectorDatabase(vdbName, query, collectionName)
	},
}

func searchVectorDatabase(dbName, query, collectionName string) error {
	// Initialize progress indicator
	var progress *ProgressIndicator
	if ShouldShowProgress() {
		progress = NewProgressIndicator("Processing search...")
		progress.Start()
	}

	if verbose {
		fmt.Println("Querying vector database...")
	}

	if dryRun {
		if progress != nil {
			progress.Stop("Dry run completed")
		}
		fmt.Println("[DRY RUN] Would search vector database")
		return nil
	}

	if progress != nil {
		progress.Update("Connecting to MCP server...")
	}

	// Get MCP server URI
	serverURI, err := getMCPServerURI(mcpServerURI)
	if err != nil {
		if progress != nil {
			progress.StopWithError("Failed to get MCP server URI")
		}
		return fmt.Errorf("failed to get MCP server URI: %w", err)
	}

	if verbose {
		fmt.Printf("Connecting to MCP server at: %s\n", serverURI)
	}

	// Create MCP client
	client, err := NewMCPClient(serverURI)
	if err != nil {
		if progress != nil {
			progress.StopWithError("Failed to create MCP client")
		}
		return fmt.Errorf("failed to create MCP client: %w", err)
	}
	defer client.Close()

	if progress != nil {
		progress.Update("Executing search...")
	}

	// Call the search method
	result, err := client.Search(dbName, query, docLimit, collectionName)
	if err != nil {
		if progress != nil {
			progress.StopWithError("Search failed")
		}
		return fmt.Errorf("failed to search vector database: %w", err)
	}

	if progress != nil {
		progress.Stop("Search completed successfully")
	}

	fmt.Println(result)
	return nil
}

func init() {
	// Add flags to search command
	searchCmd.Flags().String("vdb", "", "Vector database name")
	searchCmd.Flags().String("collection", "", "Collection name to search in")
	searchCmd.Flags().IntVarP(&docLimit, "doc-limit", "d", 5, "Maximum number of documents to consider")
}
