package provider

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

type tokenProvider struct{}

func TestClaimLifecycle(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/claim", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Fatalf("expected POST, got %s", r.Method)
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(ClaimNameResponse{
			Name:         "wus2prdfoo",
			ResourceType: "storage_account",
			Region:       "wus2",
			Environment:  "prd",
			Slug:         "st",
			ClaimedBy:    "user@example.com",
		})
	})
	mux.HandleFunc("/api/release", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
	})
	mux.HandleFunc("/api/audit", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("name") == "gone" {
			http.NotFound(w, r)
			return
		}
		json.NewEncoder(w).Encode(AuditRecord{
			Name:        "wus2prdfoo",
			Resource:    "storage_account",
			InUse:       true,
			ClaimedBy:   "user@example.com",
			Region:      "wus2",
			Environment: "prd",
			Slug:        "st",
		})
	})
	mux.HandleFunc("/api/slug", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(SlugResponse{
			ResourceType: "storage_account",
			Slug:         "st",
			FullName:     "Storage Account",
			Source:       "table",
			UpdatedAt:    time.Now().UTC().Format(time.RFC3339),
		})
	})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	client, err := NewAPIClient(context.Background(), srv.URL, "", RetryConfig{MaxAttempts: 2, MinBackoff: time.Millisecond, MaxBackoff: 2 * time.Millisecond})
	if err != nil {
		t.Fatalf("NewAPIClient: %v", err)
	}

	claim, err := client.ClaimName(context.Background(), ClaimNameRequest{ResourceType: "storage_account", Region: "wus2", Environment: "prd"})
	if err != nil {
		t.Fatalf("ClaimName: %v", err)
	}
	if claim.Name != "wus2prdfoo" {
		t.Fatalf("unexpected claim name: %s", claim.Name)
	}

	audit, err := client.GetAudit(context.Background(), "wus2", "prd", "wus2prdfoo")
	if err != nil {
		t.Fatalf("GetAudit: %v", err)
	}
	if audit == nil || audit.ClaimedBy != "user@example.com" {
		t.Fatalf("unexpected audit: %#v", audit)
	}

	slug, err := client.LookupSlug(context.Background(), "storage_account")
	if err != nil {
		t.Fatalf("LookupSlug: %v", err)
	}
	if slug == nil || slug.Slug != "st" {
		t.Fatalf("unexpected slug: %#v", slug)
	}

	if err := client.ReleaseName(context.Background(), ReleaseRequest{Name: "wus2prdfoo", Region: "wus2", Environment: "prd", Reason: "test"}); err != nil {
		t.Fatalf("ReleaseName: %v", err)
	}
}

func TestGetAuditNotFound(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/audit", func(w http.ResponseWriter, r *http.Request) {
		http.NotFound(w, r)
	})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	client, err := NewAPIClient(context.Background(), srv.URL, "", RetryConfig{MaxAttempts: 1, MinBackoff: time.Millisecond, MaxBackoff: 2 * time.Millisecond})
	if err != nil {
		t.Fatalf("NewAPIClient: %v", err)
	}

	record, err := client.GetAudit(context.Background(), "wus2", "prd", "missing")
	if err != nil {
		t.Fatalf("GetAudit: %v", err)
	}
	if record != nil {
		t.Fatalf("expected nil record, got %#v", record)
	}
}

func TestRetryLogic(t *testing.T) {
	attempts := 0
	mux := http.NewServeMux()
	mux.HandleFunc("/api/claim", func(w http.ResponseWriter, r *http.Request) {
		attempts++
		if attempts < 2 {
			w.WriteHeader(http.StatusTooManyRequests)
			return
		}
		json.NewEncoder(w).Encode(ClaimNameResponse{Name: "ok"})
	})

	srv := httptest.NewServer(mux)
	defer srv.Close()

	client, err := NewAPIClient(context.Background(), srv.URL, "", RetryConfig{MaxAttempts: 3, MinBackoff: time.Millisecond, MaxBackoff: 2 * time.Millisecond})
	if err != nil {
		t.Fatalf("NewAPIClient: %v", err)
	}

	_, err = client.ClaimName(context.Background(), ClaimNameRequest{ResourceType: "vm", Region: "wus2", Environment: "prd"})
	if err != nil {
		t.Fatalf("ClaimName: %v", err)
	}
	if attempts != 2 {
		t.Fatalf("expected 2 attempts, got %d", attempts)
	}
}
