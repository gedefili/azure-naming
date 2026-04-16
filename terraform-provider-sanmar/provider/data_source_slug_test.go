package provider

import (
	"context"
	"strings"
	"testing"
)

func TestReadSlugReturnsErrorForMissingMapping(t *testing.T) {
	original := lookupSlugFunc
	lookupSlugFunc = func(context.Context, *APIClient, string) (*SlugResponse, error) {
		return nil, nil
	}
	defer func() {
		lookupSlugFunc = original
	}()

	_, err := readSlug(context.Background(), &APIClient{}, "app_service")
	if err == nil {
		t.Fatal("expected readSlug to fail when no mapping exists")
	}
	if !strings.Contains(err.Error(), "app_service") {
		t.Fatalf("expected error to mention resource type, got %q", err.Error())
	}
}

func TestReadSlugReturnsLookupResult(t *testing.T) {
	original := lookupSlugFunc
	lookupSlugFunc = func(context.Context, *APIClient, string) (*SlugResponse, error) {
		return &SlugResponse{Slug: "app", FullName: "app_service"}, nil
	}
	defer func() {
		lookupSlugFunc = original
	}()

	slug, err := readSlug(context.Background(), &APIClient{}, "app_service")
	if err != nil {
		t.Fatalf("expected readSlug to succeed, got %v", err)
	}
	if slug.Slug != "app" {
		t.Fatalf("expected slug 'app', got %q", slug.Slug)
	}
}
