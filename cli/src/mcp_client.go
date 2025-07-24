package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"github.com/joho/godotenv"
)

// MCPClient represents a client for communicating with the MCP server
type MCPClient struct {
	baseURL    string
	httpClient *http.Client
}

// MCPRequest represents a request to the MCP server
type MCPRequest struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      int         `json:"id"`
	Method  string      `json:"method"`
	Params  interface{} `json:"params"`
}

// MCPResponse represents a response from the MCP server
type MCPResponse struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      int         `json:"id"`
	Result  interface{} `json:"result,omitempty"`
	Error   *MCPError   `json:"error,omitempty"`
}

// MCPError represents an error from the MCP server
type MCPError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

// DatabaseInfo represents information about a vector database
type DatabaseInfo struct {
	Name          string `json:"name"`
	Type          string `json:"type"`
	Collection    string `json:"collection"`
	DocumentCount int    `json:"document_count"`
}

// NewMCPClient creates a new MCP client
func NewMCPClient(baseURL string) *MCPClient {
	return &MCPClient{
		baseURL: baseURL,
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// getMCPServerURI gets the MCP server URI from environment variable or command line flag
func getMCPServerURI(cmdServerURI string) (string, error) {
	// Load .env file if it exists
	if err := loadEnvFile(); err != nil {
		// It's okay if .env file doesn't exist
	}

	// Priority: command line flag > environment variable > default
	if cmdServerURI != "" {
		return cmdServerURI, nil
	}

	if envURI := os.Getenv("MAESTRO_KNOWLEDGE_MCP_SERVER_URI"); envURI != "" {
		return envURI, nil
	}

	// Default to localhost:8000
	return "http://localhost:8000", nil
}

// loadEnvFile loads environment variables from .env file
func loadEnvFile() error {
	// Load .env file if it exists
	if err := godotenv.Load(); err != nil {
		// It's okay if .env file doesn't exist
		return nil
	}
	return nil
}

// callMCPServer makes a call to the MCP server
func (c *MCPClient) callMCPServer(method string, params interface{}) (*MCPResponse, error) {
	// For FastMCP, we need to call the tool directly via HTTP POST
	// The method should be the tool name
	url := fmt.Sprintf("%s/mcp/tools/%s", c.baseURL, method)

	jsonData, err := json.Marshal(params)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	resp, err := c.httpClient.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to make HTTP request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("HTTP error %d: %s", resp.StatusCode, string(body))
	}

	// Read the response body
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response body: %w", err)
	}

	// For FastMCP, the response is typically a string result
	return &MCPResponse{
		JSONRPC: "2.0",
		ID:      1,
		Result:  string(body),
	}, nil
}

// ListDatabases calls the list_databases tool on the MCP server
func (c *MCPClient) ListDatabases() ([]DatabaseInfo, error) {
	response, err := c.callMCPServer("list_databases", map[string]interface{}{})
	if err != nil {
		return nil, err
	}

	// The response structure depends on how the MCP server returns the result
	// We need to parse the result field which contains the JSON string
	if resultStr, ok := response.Result.(string); ok {
		// The result is a JSON string, so we need to parse it
		var databases []DatabaseInfo
		if err := json.Unmarshal([]byte(resultStr), &databases); err != nil {
			// If it's not a JSON array, it might be a message indicating no databases
			if resultStr == "No vector databases are currently active" {
				return []DatabaseInfo{}, nil
			}
			return nil, fmt.Errorf("failed to parse database list: %w", err)
		}
		return databases, nil
	}

	return nil, fmt.Errorf("unexpected response format from MCP server")
}
