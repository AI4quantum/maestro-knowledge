package main

import (
	"fmt"
	"os"

	"github.com/joho/godotenv"
	"github.com/spf13/cobra"
)

var (
	version      = "0.1.0"
	buildTime    = "unknown"
	verbose      bool
	silent       bool
	dryRun       bool
	force        bool
	mcpServerURI string
)

// addContextualHelp adds contextual help to commands
func addContextualHelp() {
	// Add post-run hooks to show contextual help
	vdbListCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("vectordb", "list")
		}
	}

	vdbCreateCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("vectordb", "create")
		}
	}

	vdbDeleteCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("vectordb", "delete")
		}
	}

	collectionListCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("collection", "list")
		}
	}

	collectionCreateCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("collection", "create")
		}
	}

	collectionDeleteCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("collection", "delete")
		}
	}

	documentListCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("document", "list")
		}
	}

	documentCreateCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("document", "create")
		}
	}

	documentDeleteCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("document", "delete")
		}
	}

	queryCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("query", "")
		}
	}

	searchCmd.PostRun = func(cmd *cobra.Command, args []string) {
		if !silent {
			ShowContextualHelp("search", "")
		}
	}
}

func main() {
	// Load .env file if it exists
	if err := godotenv.Load(); err != nil {
		// .env file doesn't exist, which is fine
		// Only log error if it's not a "file not found" error
		if !os.IsNotExist(err) {
			fmt.Fprintf(os.Stderr, "Warning: Failed to load .env file: %v\n", err)
		}
	}

	var rootCmd = &cobra.Command{
		Use:   "maestro-k",
		Short: "Maestro Knowledge CLI tool",
		Long: `Maestro Knowledge CLI tool for managing vector databases and their resources.
		
A command-line interface for working with Maestro Knowledge configurations.`,
		Version:       version + " (built " + buildTime + ")",
		SilenceErrors: true, // Prevent Cobra from automatically printing errors
	}

	// Global flags
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "", false, "Show all output")
	rootCmd.PersistentFlags().BoolVarP(&silent, "silent", "", false, "Show no additional output on success, e.g., no OK or Success etc")
	rootCmd.PersistentFlags().BoolVarP(&dryRun, "dry-run", "", false, "Mocks agents and other parts of workflow execution")
	rootCmd.PersistentFlags().BoolVarP(&force, "force", "f", false, "Skip confirmation prompts for destructive operations")
	rootCmd.PersistentFlags().StringVar(&mcpServerURI, "mcp-server-uri", "", "MCP server URI (overrides MAESTRO_KNOWLEDGE_MCP_SERVER_URI environment variable)")

	// Add resource-based commands
	rootCmd.AddCommand(vdbCmd)
	rootCmd.AddCommand(collectionCmd)
	rootCmd.AddCommand(documentCmd)
	rootCmd.AddCommand(embeddingCmd)
	rootCmd.AddCommand(queryCmd)
	rootCmd.AddCommand(searchCmd)
	rootCmd.AddCommand(validateCmd)
	rootCmd.AddCommand(statusCmd)

	// Add completion command
	AddCompletionCommand(rootCmd)

	// Add sub-commands to resource commands
	vdbCmd.AddCommand(vdbListCmd)
	vdbCmd.AddCommand(vdbCreateCmd)
	vdbCmd.AddCommand(vdbDeleteCmd)

	collectionCmd.AddCommand(collectionListCmd)
	collectionCmd.AddCommand(collectionCreateCmd)
	collectionCmd.AddCommand(collectionDeleteCmd)

	documentCmd.AddCommand(documentListCmd)
	documentCmd.AddCommand(documentCreateCmd)
	documentCmd.AddCommand(documentDeleteCmd)

	embeddingCmd.AddCommand(embeddingListCmd)

	// Add contextual help to commands
	addContextualHelp()

	// Setup custom completions
	SetupCustomCompletions()

	if err := rootCmd.Execute(); err != nil {
		// Check for other common errors and provide suggestions
		suggestion := SuggestForError(err.Error())
		if suggestion != "" && verbose {
			fmt.Fprintf(os.Stderr, "💡 %s\n", suggestion)
		}
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}
