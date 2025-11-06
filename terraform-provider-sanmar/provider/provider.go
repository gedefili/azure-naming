package provider

import (
	"context"
	"fmt"
	"time"

	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/provider"
	"github.com/hashicorp/terraform-plugin-framework/provider/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/types"
	"github.com/hashicorp/terraform-plugin-log/tflog"
)

// Ensure Provider satisfies interfaces
var _ provider.Provider = (*SanmarProvider)(nil)

// New returns a new instance of the provider configured with the supplied version.
func New(version string) func() provider.Provider {
	return func() provider.Provider {
		return &SanmarProvider{version: version}
	}
}

// SanmarProvider implements the Terraform provider interface.
type SanmarProvider struct {
	version string
}

// sanmarProviderModel stores provider configuration.
type sanmarProviderModel struct {
	Endpoint         types.String `tfsdk:"endpoint"`
	Scope            types.String `tfsdk:"scope"`
	RetryMaxAttempts types.Int64  `tfsdk:"retry_max_attempts"`
	RetryMinBackoff  types.String `tfsdk:"retry_min_backoff"`
	RetryMaxBackoff  types.String `tfsdk:"retry_max_backoff"`
}

// Metadata sets the provider type name.
func (p *SanmarProvider) Metadata(_ context.Context, req provider.MetadataRequest, resp *provider.MetadataResponse) {
	resp.TypeName = req.TypeName
	resp.Version = p.version
}

// Schema defines provider configuration schema.
func (p *SanmarProvider) Schema(_ context.Context, _ provider.SchemaRequest, resp *provider.SchemaResponse) {
	resp.Schema = schema.Schema{
		Attributes: map[string]schema.Attribute{
			"endpoint": schema.StringAttribute{
				Optional:    true,
				Description: "Base URL for the Azure Naming service (for example, https://naming.azurewebsites.net).",
			},
			"scope": schema.StringAttribute{
				Optional:    true,
				Description: "AAD scope or resource identifier to request tokens for (for example, api://client-id/.default).",
			},
			"retry_max_attempts": schema.Int64Attribute{
				Optional:    true,
				Description: "Maximum number of attempts for transient HTTP errors (default 4).",
			},
			"retry_min_backoff": schema.StringAttribute{
				Optional:    true,
				Description: "Minimum backoff duration between retries (default 500ms).",
			},
			"retry_max_backoff": schema.StringAttribute{
				Optional:    true,
				Description: "Maximum backoff duration between retries (default 5s).",
			},
		},
		Blocks: map[string]schema.Block{},
	}
}

// Configure sets up provider state.
func (p *SanmarProvider) Configure(ctx context.Context, req provider.ConfigureRequest, resp *provider.ConfigureResponse) {
	var data sanmarProviderModel
	diag := req.Config.Get(ctx, &data)
	resp.Diagnostics.Append(diag...)
	if resp.Diagnostics.HasError() {
		return
	}

	endpoint := ""
	if !data.Endpoint.IsNull() && !data.Endpoint.IsUnknown() {
		endpoint = data.Endpoint.ValueString()
	}
	scope := ""
	if !data.Scope.IsNull() && !data.Scope.IsUnknown() {
		scope = data.Scope.ValueString()
	}

	retryConfig := RetryConfig{
		MaxAttempts: 4,
		MinBackoff:  500 * time.Millisecond,
		MaxBackoff:  5 * time.Second,
	}

	if !data.RetryMaxAttempts.IsNull() && !data.RetryMaxAttempts.IsUnknown() {
		retryConfig.MaxAttempts = int(data.RetryMaxAttempts.ValueInt64())
	}

	if !data.RetryMinBackoff.IsNull() && !data.RetryMinBackoff.IsUnknown() {
		duration, err := time.ParseDuration(data.RetryMinBackoff.ValueString())
		if err != nil {
			resp.Diagnostics.AddError("Invalid retry_min_backoff", fmt.Sprintf("failed to parse duration: %v", err))
			return
		}
		retryConfig.MinBackoff = duration
	}

	if !data.RetryMaxBackoff.IsNull() && !data.RetryMaxBackoff.IsUnknown() {
		duration, err := time.ParseDuration(data.RetryMaxBackoff.ValueString())
		if err != nil {
			resp.Diagnostics.AddError("Invalid retry_max_backoff", fmt.Sprintf("failed to parse duration: %v", err))
			return
		}
		retryConfig.MaxBackoff = duration
	}

	client, err := NewAPIClient(ctx, endpoint, scope, retryConfig)
	if err != nil {
		resp.Diagnostics.AddError("Failed to configure provider", err.Error())
		return
	}

	tflog.Debug(ctx, "configured SanMar naming provider", map[string]any{
		"endpoint": endpoint,
		"scope":    scope,
	})

	resp.DataSourceData = client
	resp.ResourceData = client
}

// DataSources returns configured data sources.
func (p *SanmarProvider) DataSources(_ context.Context) []func() datasource.DataSource {
	return []func() datasource.DataSource{
		NewSlugDataSource,
	}
}

// Resources returns provider resources.
func (p *SanmarProvider) Resources(_ context.Context) []func() resource.Resource {
	return []func() resource.Resource{
		NewClaimResource,
	}
}
