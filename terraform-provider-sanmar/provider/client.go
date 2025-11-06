package provider

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/Azure/azure-sdk-for-go/sdk/azcore/policy"
	"github.com/Azure/azure-sdk-for-go/sdk/azidentity"
)

// RetryConfig configures retry behaviour for API calls.
type RetryConfig struct {
	MaxAttempts int
	MinBackoff  time.Duration
	MaxBackoff  time.Duration
}

// APIClient coordinates calls to the Azure naming service.
type APIClient struct {
	endpoint string
	scope    string
	cred     *azidentity.DefaultAzureCredential
	retry    RetryConfig
	http     *http.Client
}

// NewAPIClient constructs a client with the supplied configuration.
func NewAPIClient(ctx context.Context, endpoint, scope string, retry RetryConfig) (*APIClient, error) {
	cred, err := azidentity.NewDefaultAzureCredential(nil)
	if err != nil {
		return nil, fmt.Errorf("failed to initialize DefaultAzureCredential: %w", err)
	}

	ep := strings.TrimSuffix(endpoint, "/")
	if ep == "" {
		ep = "http://localhost:7071"
	}

	if retry.MaxAttempts <= 0 {
		retry.MaxAttempts = 1
	}
	if retry.MinBackoff <= 0 {
		retry.MinBackoff = 500 * time.Millisecond
	}
	if retry.MaxBackoff < retry.MinBackoff {
		retry.MaxBackoff = retry.MinBackoff
	}

	return &APIClient{
		endpoint: ep,
		scope:    scope,
		cred:     cred,
		retry:    retry,
		http: &http.Client{
			Timeout: 30 * time.Second,
		},
	}, nil
}

func (c *APIClient) buildRequest(ctx context.Context, method, path string, body any) (*http.Request, error) {
	var reader io.Reader
	if body != nil {
		buf, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal request body: %w", err)
		}
		reader = bytes.NewReader(buf)
	}

	target := c.endpoint + path
	req, err := http.NewRequestWithContext(ctx, method, target, reader)
	if err != nil {
		return nil, fmt.Errorf("failed to build request: %w", err)
	}

	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	if c.scope != "" {
		token, err := c.cred.GetToken(ctx, policy.TokenRequestOptions{Scopes: []string{c.scope}})
		if err != nil {
			return nil, fmt.Errorf("failed to acquire access token: %w", err)
		}
		req.Header.Set("Authorization", "Bearer "+token.Token)
	}

	return req, nil
}

func (c *APIClient) doRequest(ctx context.Context, req *http.Request) (*http.Response, error) {
	attempts := 0
	backoff := c.retry.MinBackoff
	for {
		attempts++
		resp, err := c.http.Do(req)
		if err == nil && resp.StatusCode < 500 {
			return resp, nil
		}

		if err == nil {
			if resp.StatusCode == http.StatusTooManyRequests || (resp.StatusCode >= 500 && resp.StatusCode <= 599) {
				// read body for logging and close before retrying
				io.Copy(io.Discard, resp.Body)
				resp.Body.Close()
			} else {
				return resp, nil
			}
		}

		if attempts >= c.retry.MaxAttempts {
			if err != nil {
				return nil, err
			}
			return resp, nil
		}

		select {
		case <-time.After(backoff):
		case <-ctx.Done():
			if err != nil {
				return nil, err
			}
			return nil, ctx.Err()
		}

		backoff *= 2
		if backoff > c.retry.MaxBackoff {
			backoff = c.retry.MaxBackoff
		}
	}
}

func decodeError(resp *http.Response) error {
	if resp == nil {
		return errors.New("no response received")
	}
	defer resp.Body.Close()
	content, _ := io.ReadAll(resp.Body)
	if len(content) == 0 {
		return fmt.Errorf("unexpected status %d", resp.StatusCode)
	}
	return fmt.Errorf("unexpected status %d: %s", resp.StatusCode, strings.TrimSpace(string(content)))
}

// ClaimNameRequest describes the payload for claim endpoint.
type ClaimNameRequest struct {
	ResourceType string            `json:"resource_type"`
	Region       string            `json:"region"`
	Environment  string            `json:"environment"`
	Project      *string           `json:"project,omitempty"`
	Purpose      *string           `json:"purpose,omitempty"`
	Subsystem    *string           `json:"subsystem,omitempty"`
	System       *string           `json:"system,omitempty"`
	Index        *string           `json:"index,omitempty"`
	SessionID    *string           `json:"sessionId,omitempty"`
	Metadata     map[string]string `json:"metadata,omitempty"`
}

// ClaimNameResponse describes the response from claim endpoint.
type ClaimNameResponse struct {
	Name         string `json:"name"`
	ResourceType string `json:"resourceType"`
	Region       string `json:"region"`
	Environment  string `json:"environment"`
	Slug         string `json:"slug"`
	ClaimedBy    string `json:"claimedBy"`
	Project      string `json:"project"`
	Purpose      string `json:"purpose"`
	Subsystem    string `json:"subsystem"`
	System       string `json:"system"`
	Index        string `json:"index"`
}

// ClaimName performs the claim request and returns the response model.
func (c *APIClient) ClaimName(ctx context.Context, payload ClaimNameRequest) (*ClaimNameResponse, error) {
	req, err := c.buildRequest(ctx, http.MethodPost, "/api/claim", payload)
	if err != nil {
		return nil, err
	}

	resp, err := c.doRequest(ctx, req)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode != http.StatusOK {
		return nil, decodeError(resp)
	}

	defer resp.Body.Close()
	var claim ClaimNameResponse
	if err := json.NewDecoder(resp.Body).Decode(&claim); err != nil {
		return nil, fmt.Errorf("failed to decode claim response: %w", err)
	}
	return &claim, nil
}

// ReleaseRequest contains release payload.
type ReleaseRequest struct {
	Name        string `json:"name"`
	Region      string `json:"region"`
	Environment string `json:"environment"`
	Reason      string `json:"reason"`
}

// ReleaseName releases a previously claimed name.
func (c *APIClient) ReleaseName(ctx context.Context, payload ReleaseRequest) error {
	req, err := c.buildRequest(ctx, http.MethodPost, "/api/release", payload)
	if err != nil {
		return err
	}

	resp, err := c.doRequest(ctx, req)
	if err != nil {
		return err
	}

	if resp.StatusCode != http.StatusOK {
		return decodeError(resp)
	}
	resp.Body.Close()
	return nil
}

// AuditRecord represents the audit endpoint response.
type AuditRecord struct {
	Name        string `json:"name"`
	Resource    string `json:"resource_type"`
	InUse       bool   `json:"in_use"`
	ClaimedBy   string `json:"claimed_by"`
	Region      string `json:"region"`
	Environment string `json:"environment"`
	Slug        string `json:"slug"`
	Project     string `json:"project"`
	Purpose     string `json:"purpose"`
	Subsystem   string `json:"subsystem"`
	System      string `json:"system"`
	Index       string `json:"index"`
}

// GetAudit retrieves the audit record for a claimed name.
func (c *APIClient) GetAudit(ctx context.Context, region, environment, name string) (*AuditRecord, error) {
	q := url.Values{}
	q.Set("region", region)
	q.Set("environment", environment)
	q.Set("name", name)
	path := "/api/audit?" + q.Encode()

	req, err := c.buildRequest(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}

	resp, err := c.doRequest(ctx, req)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode == http.StatusNotFound {
		resp.Body.Close()
		return nil, nil
	}

	if resp.StatusCode != http.StatusOK {
		return nil, decodeError(resp)
	}

	defer resp.Body.Close()
	var record AuditRecord
	if err := json.NewDecoder(resp.Body).Decode(&record); err != nil {
		return nil, fmt.Errorf("failed to decode audit response: %w", err)
	}
	return &record, nil
}

// SlugResponse captures slug lookup response.
type SlugResponse struct {
	ResourceType string `json:"resourceType"`
	Slug         string `json:"slug"`
	FullName     string `json:"fullName"`
	Source       string `json:"source"`
	UpdatedAt    string `json:"updatedAt"`
}

// LookupSlug retrieves slug information for a resource type.
func (c *APIClient) LookupSlug(ctx context.Context, resourceType string) (*SlugResponse, error) {
	q := url.Values{}
	q.Set("resource_type", resourceType)
	path := "/api/slug?" + q.Encode()

	req, err := c.buildRequest(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}

	resp, err := c.doRequest(ctx, req)
	if err != nil {
		return nil, err
	}

	if resp.StatusCode == http.StatusNotFound {
		resp.Body.Close()
		return nil, nil
	}

	if resp.StatusCode != http.StatusOK {
		return nil, decodeError(resp)
	}

	defer resp.Body.Close()
	var slug SlugResponse
	if err := json.NewDecoder(resp.Body).Decode(&slug); err != nil {
		return nil, fmt.Errorf("failed to decode slug response: %w", err)
	}
	return &slug, nil
}
