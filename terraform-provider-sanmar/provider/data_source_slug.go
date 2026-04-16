package provider

import (
	"context"
	"fmt"

	"github.com/hashicorp/terraform-plugin-framework-validators/stringvalidator"
	"github.com/hashicorp/terraform-plugin-framework/datasource"
	"github.com/hashicorp/terraform-plugin-framework/datasource/schema"
	"github.com/hashicorp/terraform-plugin-framework/schema/validator"
	"github.com/hashicorp/terraform-plugin-framework/types"
)

var _ datasource.DataSource = (*SlugDataSource)(nil)

var lookupSlugFunc = func(ctx context.Context, client *APIClient, resourceType string) (*SlugResponse, error) {
	return client.LookupSlug(ctx, resourceType)
}

// NewSlugDataSource returns the slug lookup data source.
func NewSlugDataSource() datasource.DataSource {
	return &SlugDataSource{}
}

// SlugDataSource exposes slug lookup over Terraform.
type SlugDataSource struct {
	client *APIClient
}

type slugDataSourceModel struct {
	ID           types.String `tfsdk:"id"`
	ResourceType types.String `tfsdk:"resource_type"`
	Slug         types.String `tfsdk:"slug"`
	FullName     types.String `tfsdk:"full_name"`
	Source       types.String `tfsdk:"source"`
	UpdatedAt    types.String `tfsdk:"updated_at"`
}

func (d *SlugDataSource) Metadata(_ context.Context, req datasource.MetadataRequest, resp *datasource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_slug"
}

func (d *SlugDataSource) Schema(_ context.Context, _ datasource.SchemaRequest, resp *datasource.SchemaResponse) {
	resp.Schema = schema.Schema{
		MarkdownDescription: "Lookup slug metadata for a resource type using the SanMar naming service.",
		Attributes: map[string]schema.Attribute{
			"id": schema.StringAttribute{
				Computed:            true,
				MarkdownDescription: "Identifier used in state, formatted as slug:<resource_type>.",
			},
			"resource_type": schema.StringAttribute{
				Required:            true,
				MarkdownDescription: "Canonical resource type to look up.",
				Validators: []validator.String{
					stringvalidator.LengthAtLeast(1),
				},
			},
			"slug": schema.StringAttribute{
				Computed:            true,
				MarkdownDescription: "Short slug resolved by the service.",
			},
			"full_name": schema.StringAttribute{
				Computed:            true,
				MarkdownDescription: "Friendly name for the resource type when available.",
			},
			"source": schema.StringAttribute{
				Computed:            true,
				MarkdownDescription: "Source identifier for the slug mapping.",
			},
			"updated_at": schema.StringAttribute{
				Computed:            true,
				MarkdownDescription: "Timestamp of the most recent sync entry.",
			},
		},
	}
}

func (d *SlugDataSource) Configure(_ context.Context, req datasource.ConfigureRequest, resp *datasource.ConfigureResponse) {
	if req.ProviderData == nil {
		return
	}

	client, ok := req.ProviderData.(*APIClient)
	if !ok {
		resp.Diagnostics.AddError("Unexpected provider data", fmt.Sprintf("expected *APIClient got %T", req.ProviderData))
		return
	}
	d.client = client
}

func readSlug(ctx context.Context, client *APIClient, resourceType string) (*SlugResponse, error) {
	slug, err := lookupSlugFunc(ctx, client, resourceType)
	if err != nil {
		return nil, err
	}
	if slug == nil {
		return nil, fmt.Errorf("no slug mapping exists for resource type %q", resourceType)
	}
	return slug, nil
}

func (d *SlugDataSource) Read(ctx context.Context, req datasource.ReadRequest, resp *datasource.ReadResponse) {
	if d.client == nil {
		resp.Diagnostics.AddError("Unconfigured provider", "The provider has not been configured; call provider block first.")
		return
	}

	var data slugDataSourceModel
	resp.Diagnostics.Append(req.Config.Get(ctx, &data)...)
	if resp.Diagnostics.HasError() {
		return
	}

	slug, err := readSlug(ctx, d.client, data.ResourceType.ValueString())
	if err != nil {
		resp.Diagnostics.AddError("Failed to lookup slug", err.Error())
		return
	}

	data.ID = types.StringValue("slug:" + data.ResourceType.ValueString())
	data.Slug = types.StringValue(slug.Slug)
	data.FullName = types.StringValue(slug.FullName)
	data.Source = types.StringValue(slug.Source)
	data.UpdatedAt = types.StringValue(slug.UpdatedAt)

	resp.Diagnostics.Append(resp.State.Set(ctx, &data)...)
}
