package main

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var (
	version   = "0.1.0"
	buildTime = "unknown"
	verbose   bool
	silent    bool
	dryRun    bool
)

func main() {
	var rootCmd = &cobra.Command{
		Use:   "maestro-k",
		Short: "Maestro Knowledge CLI tool",
		Long: `Maestro Knowledge CLI tool for validating YAML files and schemas.
		
A command-line interface for working with Maestro Knowledge configurations.`,
		Version: version + " (built " + buildTime + ")",
	}

	// Global flags
	rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "", false, "Show all output")
	rootCmd.PersistentFlags().BoolVarP(&silent, "silent", "", false, "Show no additional output on success, e.g., no OK or Success etc")
	rootCmd.PersistentFlags().BoolVarP(&dryRun, "dry-run", "", false, "Mocks agents and other parts of workflow execution")

	// Add commands
	rootCmd.AddCommand(validateCmd)

	if err := rootCmd.Execute(); err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		os.Exit(1)
	}
}
