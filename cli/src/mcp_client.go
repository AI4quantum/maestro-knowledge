package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/joho/godotenv"
	"github.com/mark3labs/mcp-go/client"
	"github.com/mark3labs/mcp-go/mcp"
)

// MCPClient represents a client for interacting with the MCP server
type MCPClient struct {
	client  *client.Client
	baseURL string
	ctx     context.Context
	cancel  context.CancelFunc
}

// MCPResponse represents the response from the MCP server
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

// normalizeURL ensures the URL has a protocol prefix and MCP endpoint
func normalizeURL(url string) string {
	// If it already has a protocol, just ensure it has the /mcp endpoint
	if strings.HasPrefix(url, "http://") || strings.HasPrefix(url, "https://") {
		if !strings.HasSuffix(url, "/mcp") {
			return strings.TrimSuffix(url, "/") + "/mcp"
		}
		return url
	}

	// If it's just a hostname:port, add http:// prefix and /mcp endpoint
	if strings.Contains(url, ":") {
		return "http://" + strings.TrimSuffix(url, "/") + "/mcp"
	}

	// If it's just a hostname, add http:// prefix, default port, and /mcp endpoint
	return "http://" + url + ":8030/mcp"
}

// getMCPServerURI gets the MCP server URI from environment variable or command line flag
func getMCPServerURI(cmdServerURI string) (string, error) {
	// Load .env file if it exists
	if _, err := os.Stat(".env"); err == nil {
		if err := godotenv.Load(); err != nil {
			return "", fmt.Errorf("failed to load .env file: %w", err)
		}
	}

	var serverURI string
	if cmdServerURI != "" {
		serverURI = cmdServerURI
	} else if envURI := os.Getenv("MAESTRO_KNOWLEDGE_MCP_SERVER_URI"); envURI != "" {
		serverURI = envURI
	} else {
		serverURI = "localhost:8030" // Default
	}

	return normalizeURL(serverURI), nil
}

// NewMCPClient creates a new MCP client
func NewMCPClient(serverURI string) (*MCPClient, error) {
	// Create context with timeout - use shorter timeout for tests
	timeout := 30 * time.Second
	if os.Getenv("MAESTRO_K_TEST_MODE") == "true" {
		timeout = 5 * time.Second // Shorter timeout for tests
	}
	ctx, cancel := context.WithTimeout(context.Background(), timeout)

	// Create MCP client using HTTP transport
	// The mark3labs/mcp-go library supports HTTP transport for connecting to existing servers
	mcpClient, err := client.NewStreamableHttpClient(serverURI)
	if err != nil {
		// Cancel context on error to prevent context leak
		cancel()

		// Provide user-friendly error messages for common connection issues
		errStr := err.Error()
		if strings.Contains(errStr, "connection refused") ||
			strings.Contains(errStr, "no such host") ||
			strings.Contains(errStr, "timeout") ||
			strings.Contains(errStr, "context deadline exceeded") ||
			strings.Contains(errStr, "network is unreachable") {
			return nil, fmt.Errorf("MCP server could not be reached at %s. Please ensure the server is running and accessible", serverURI)
		}
		return nil, fmt.Errorf("failed to create MCP client: %w", err)
	}

	return &MCPClient{
		client:  mcpClient,
		baseURL: serverURI,
		ctx:     ctx,
		cancel:  cancel,
	}, nil
}

// callMCPServer makes a call to the MCP server using the mark3labs/mcp-go library
func (c *MCPClient) callMCPServer(method string, params interface{}) (*MCPResponse, error) {

	// Initialize the client if not already initialized
	if !c.client.IsInitialized() {
		initRequest := mcp.InitializeRequest{
			Request: mcp.Request{
				Method: "initialize",
			},
			Params: mcp.InitializeParams{
				ProtocolVersion: "2024-11-05",
				Capabilities:    mcp.ClientCapabilities{},
			},
		}

		_, err := c.client.Initialize(c.ctx, initRequest)
		if err != nil {
			// Provide user-friendly error messages for common connection issues
			errStr := err.Error()
			if strings.Contains(errStr, "connection refused") ||
				strings.Contains(errStr, "no such host") ||
				strings.Contains(errStr, "timeout") ||
				strings.Contains(errStr, "context deadline exceeded") ||
				strings.Contains(errStr, "network is unreachable") {
				return nil, fmt.Errorf("MCP server could not be reached at %s. Please ensure the server is running and accessible", c.baseURL)
			}
			return nil, fmt.Errorf("failed to initialize MCP client: %w", err)
		}
	}

	// Create the tool call request
	request := mcp.CallToolRequest{
		Request: mcp.Request{
			Method: method,
		},
		Params: mcp.CallToolParams{
			Name:      method,
			Arguments: params,
		},
	}

	// Call the tool
	response, err := c.client.CallTool(c.ctx, request)
	if err != nil {
		// Provide user-friendly error messages for common connection issues
		errStr := err.Error()
		if strings.Contains(errStr, "connection refused") ||
			strings.Contains(errStr, "no such host") ||
			strings.Contains(errStr, "timeout") ||
			strings.Contains(errStr, "context deadline exceeded") ||
			strings.Contains(errStr, "network is unreachable") {
			return nil, fmt.Errorf("MCP server could not be reached at %s. Please ensure the server is running and accessible", c.baseURL)
		}
		return nil, fmt.Errorf("failed to call MCP tool %s: %w", method, err)
	}

	// Convert the response to our format
	result := &MCPResponse{
		JSONRPC: "2.0",
		ID:      1,
	}

	// Check if the response indicates an error
	if response != nil && len(response.Content) > 0 {
		// Try to get text content
		if textContent, ok := mcp.AsTextContent(response.Content[0]); ok {
			// Check if the content contains an error message
			contentText := textContent.Text
			if strings.Contains(contentText, "ValueError:") ||
				strings.Contains(contentText, "Error:") ||
				strings.Contains(contentText, "Exception:") ||
				strings.Contains(contentText, "Error calling tool") {
				// This is an error response
				result.Error = &MCPError{
					Code:    -1,
					Message: contentText,
				}
				return result, nil
			}

			// Try to parse as JSON first
			var jsonResult interface{}
			if err := json.Unmarshal([]byte(contentText), &jsonResult); err == nil {
				result.Result = jsonResult
			} else {
				// If not JSON, use as string
				result.Result = contentText
			}
		}
	}

	return result, nil
}

// ListDatabases calls the list_databases tool on the MCP server
func (c *MCPClient) ListDatabases() ([]DatabaseInfo, error) {
	response, err := c.callMCPServer("list_databases", nil)
	if err != nil {
		return nil, err
	}

	// The response structure depends on how the MCP server returns the result
	// We need to parse the result field which contains the JSON string
	if resultStr, ok := response.Result.(string); ok {
		// Check if it's a message indicating no databases
		if resultStr == "No vector databases are currently active" {
			return []DatabaseInfo{}, nil
		}

		// The result might be a formatted string like "Available vector databases:\n{JSON}"
		// Try to extract JSON from the string
		jsonStart := strings.Index(resultStr, "[")
		if jsonStart == -1 {
			jsonStart = strings.Index(resultStr, "{")
		}

		if jsonStart != -1 {
			jsonStr := resultStr[jsonStart:]
			var databases []DatabaseInfo
			if err := json.Unmarshal([]byte(jsonStr), &databases); err == nil {
				return databases, nil
			}
		}

		// If we can't extract JSON, try to parse the whole string as JSON
		var databases []DatabaseInfo
		if err := json.Unmarshal([]byte(resultStr), &databases); err != nil {
			return nil, fmt.Errorf("failed to parse database list: %w", err)
		}
		return databases, nil
	}

	return nil, fmt.Errorf("unexpected response format from MCP server")
}

// CreateVectorDatabase calls the create_vector_database_tool on the MCP server
func (c *MCPClient) CreateVectorDatabase(dbName, dbType, collectionName string) error {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name":         dbName,
			"db_type":         dbType,
			"collection_name": collectionName,
		},
	}

	response, err := c.callMCPServer("create_vector_database_tool", params)
	if err != nil {
		return err
	}

	// Check for error in response
	if response.Error != nil {
		return fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a success message
	if response.Result == nil {
		return fmt.Errorf("no response from MCP server")
	}

	return nil
}

// SetupDatabase calls the setup_database tool on the MCP server
func (c *MCPClient) SetupDatabase(dbName, embedding string) error {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name":   dbName,
			"embedding": embedding,
		},
	}

	response, err := c.callMCPServer("setup_database", params)
	if err != nil {
		return err
	}

	// Check for error in response
	if response.Error != nil {
		return fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a success message
	if response.Result == nil {
		return fmt.Errorf("no response from MCP server")
	}

	return nil
}

// DatabaseExists checks if a database with the given name exists
func (c *MCPClient) DatabaseExists(dbName string) (bool, error) {
	databases, err := c.ListDatabases()
	if err != nil {
		return false, fmt.Errorf("failed to list databases: %w", err)
	}

	for _, db := range databases {
		if db.Name == dbName {
			return true, nil
		}
	}
	return false, nil
}

// DeleteVectorDatabase calls the cleanup tool on the MCP server
func (c *MCPClient) DeleteVectorDatabase(dbName string) error {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name": dbName,
		},
	}

	response, err := c.callMCPServer("cleanup", params)
	if err != nil {
		return err
	}

	// Check for error in response
	if response.Error != nil {
		return fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a success message
	if response.Result == nil {
		return fmt.Errorf("no response from MCP server")
	}

	return nil
}

// GetSupportedEmbeddings calls the get_supported_embeddings tool on the MCP server
func (c *MCPClient) GetSupportedEmbeddings(dbName string) (string, error) {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name": dbName,
		},
	}

	response, err := c.callMCPServer("get_supported_embeddings", params)
	if err != nil {
		return "", err
	}

	// Check for error in response
	if response.Error != nil {
		return "", fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a string with the embeddings list
	if response.Result == nil {
		return "", fmt.Errorf("no response from MCP server")
	}

	if resultStr, ok := response.Result.(string); ok {
		return resultStr, nil
	}

	return "", fmt.Errorf("unexpected response format from MCP server")
}

// ListCollections calls the list_collections tool on the MCP server
func (c *MCPClient) ListCollections(dbName string) (string, error) {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name": dbName,
		},
	}

	response, err := c.callMCPServer("list_collections", params)
	if err != nil {
		return "", err
	}

	// Check for error in response
	if response.Error != nil {
		return "", fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a string with the collections list
	if response.Result == nil {
		return "", fmt.Errorf("no response from MCP server")
	}

	if resultStr, ok := response.Result.(string); ok {
		return resultStr, nil
	}

	return "", fmt.Errorf("unexpected response format from MCP server")
}

// GetCollectionInfo calls the get_collection_info tool on the MCP server
func (c *MCPClient) GetCollectionInfo(dbName, collectionName string) (string, error) {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name": dbName,
		},
	}

	// Only add collection_name if it's provided
	if collectionName != "" {
		params["input"].(map[string]interface{})["collection_name"] = collectionName
	}

	response, err := c.callMCPServer("get_collection_info", params)
	if err != nil {
		return "", err
	}

	// Check for error in response
	if response.Error != nil {
		return "", fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a string with the collection info
	if response.Result == nil {
		return "", fmt.Errorf("no response from MCP server")
	}

	if resultStr, ok := response.Result.(string); ok {
		return resultStr, nil
	}

	return "", fmt.Errorf("unexpected response format from MCP server")
}

// ListDocumentsInCollection calls the list_documents_in_collection tool on the MCP server
func (c *MCPClient) ListDocumentsInCollection(dbName, collectionName string) (string, error) {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name":         dbName,
			"collection_name": collectionName,
		},
	}

	response, err := c.callMCPServer("list_documents_in_collection", params)
	if err != nil {
		return "", err
	}

	// Check for error in response
	if response.Error != nil {
		return "", fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a string with the documents list
	if response.Result == nil {
		return "", fmt.Errorf("no response from MCP server")
	}

	if resultStr, ok := response.Result.(string); ok {
		return resultStr, nil
	}

	return "", fmt.Errorf("unexpected response format from MCP server")
}

// CreateCollection calls the create_collection tool on the MCP server
func (c *MCPClient) CreateCollection(dbName, collectionName, embedding string) error {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name":         dbName,
			"collection_name": collectionName,
			"embedding":       embedding,
		},
	}

	response, err := c.callMCPServer("create_collection", params)
	if err != nil {
		return err
	}

	// Check for error in response
	if response.Error != nil {
		return fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a success message
	if response.Result == nil {
		return fmt.Errorf("no response from MCP server")
	}

	return nil
}

// DeleteCollection calls the delete_collection tool on the MCP server
func (c *MCPClient) DeleteCollection(dbName, collectionName string) error {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name":         dbName,
			"collection_name": collectionName,
		},
	}

	response, err := c.callMCPServer("delete_collection", params)
	if err != nil {
		return err
	}

	// Check for error in response
	if response.Error != nil {
		return fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a success message
	if response.Result == nil {
		return fmt.Errorf("no response from MCP server")
	}

	return nil
}

// WriteDocument calls the write_document_to_collection tool on the MCP server
func (c *MCPClient) WriteDocument(dbName, collectionName, docName, fileName, embedding string) error {
	// Read the file content
	content, err := os.ReadFile(fileName)
	if err != nil {
		return fmt.Errorf("failed to read file '%s': %w", fileName, err)
	}

	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name":         dbName,
			"collection_name": collectionName,
			"doc_name":        docName,
			"text":            string(content),
			"url":             fileName,
			"metadata": map[string]interface{}{
				"filename": fileName,
				"doc_name": docName,
			},
			"embedding": embedding,
		},
	}

	response, err := c.callMCPServer("write_document_to_collection", params)
	if err != nil {
		return err
	}

	// Check for error in response
	if response.Error != nil {
		return fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a success message
	if response.Result == nil {
		return fmt.Errorf("no response from MCP server")
	}

	return nil
}

// DeleteDocumentFromCollection calls the delete_document_from_collection tool on the MCP server
func (c *MCPClient) DeleteDocumentFromCollection(dbName, collectionName, docName string) error {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name":         dbName,
			"collection_name": collectionName,
			"doc_name":        docName,
		},
	}

	response, err := c.callMCPServer("delete_document_from_collection", params)
	if err != nil {
		return err
	}

	// Check for error in response
	if response.Error != nil {
		return fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a success message
	if response.Result == nil {
		return fmt.Errorf("no response from MCP server")
	}

	return nil
}

// GetDocument calls the get_document tool on the MCP server
func (c *MCPClient) GetDocument(dbName, collectionName, docName string) (string, error) {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name":         dbName,
			"collection_name": collectionName,
			"doc_name":        docName,
		},
	}

	response, err := c.callMCPServer("get_document", params)
	if err != nil {
		return "", err
	}

	// Check for error in response
	if response.Error != nil {
		return "", fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a string with the document information
	if response.Result == nil {
		return "", fmt.Errorf("no response from MCP server")
	}

	// Convert the result to a string
	resultStr, ok := response.Result.(string)
	if !ok {
		return "", fmt.Errorf("unexpected response type from MCP server")
	}

	return resultStr, nil
}

// Query calls the query tool on the MCP server
func (c *MCPClient) Query(dbName, query string, limit int, collectionName string) (string, error) {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name":         dbName,
			"query":           query,
			"limit":           limit,
			"collection_name": collectionName,
		},
	}

	response, err := c.callMCPServer("query", params)
	if err != nil {
		return "", err
	}

	// Check for error in response
	if response.Error != nil {
		return "", fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a string with the query result
	if response.Result == nil {
		return "", fmt.Errorf("no response from MCP server")
	}

	// Convert the result to a string
	resultStr, ok := response.Result.(string)
	if !ok {
		return "", fmt.Errorf("unexpected response type from MCP server")
	}

	return resultStr, nil
}

// Search calls the search tool on the MCP server
func (c *MCPClient) Search(dbName, query string, limit int, collectionName string) (string, error) {
	params := map[string]interface{}{
		"input": map[string]interface{}{
			"db_name":         dbName,
			"query":           query,
			"limit":           limit,
			"collection_name": collectionName,
		},
	}

	response, err := c.callMCPServer("search", params)
	if err != nil {
		return "", err
	}

	// Check for error in response
	if response.Error != nil {
		return "", fmt.Errorf("MCP server error: %s", response.Error.Message)
	}

	// The response should be a string with the search result
	if response.Result == nil {
		return "", fmt.Errorf("no response from MCP server")
	}

	resultStr, ok := response.Result.(string)
	if !ok {
        prettyJSON, err := json.MarshalIndent(response.Result, "", "  ")
        if err != nil {
            return "", fmt.Errorf("unexpected response type from MCP server")
        }
		return string(prettyJSON), nil
	}

	return resultStr, nil
}

// Close closes the MCP client
func (c *MCPClient) Close() error {
	// Cancel the context to prevent context leaks
	if c.cancel != nil {
		c.cancel()
	}

	if c.client != nil {
		return c.client.Close()
	}
	return nil
}
