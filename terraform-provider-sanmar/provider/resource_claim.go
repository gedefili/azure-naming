package provider

import (
	"context"
	"fmt"

	"github.com/hashicorp/terraform-plugin-framework-validators/stringvalidator"
	"github.com/hashicorp/terraform-plugin-framework/diag"
	"github.com/hashicorp/terraform-plugin-framework/path"
	"github.com/hashicorp/terraform-plugin-framework/resource"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/mapplanmodifier"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/planmodifier"
	"github.com/hashicorp/terraform-plugin-framework/resource/schema/stringplanmodifier"
	"github.com/hashicorp/terraform-plugin-framework/types"
	"github.com/hashicorp/terraform-plugin-log/tflog"
)

var _ resource.Resource = (*ClaimResource)(nil)
var _ resource.ResourceWithImportState = (*ClaimResource)(nil)

// ClaimResource implements the Terraform resource.
type ClaimResource struct {
	client *APIClient
}

// NewClaimResource instantiates the resource.
func NewClaimResource() resource.Resource {
	return &ClaimResource{}
}

type claimResourceModel struct {
	ID           types.String `tfsdk:"id"`
	Name         types.String `tfsdk:"name"`
	ResourceType types.String `tfsdk:"resource_type"`
	Region       types.String `tfsdk:"region"`
	Environment  types.String `tfsdk:"environment"`
	Project      types.String `tfsdk:"project"`
	Purpose      types.String `tfsdk:"purpose"`
	Subsystem    types.String `tfsdk:"subsystem"`
	System       types.String `tfsdk:"system"`
	Index        types.String `tfsdk:"index"`
	SessionID    types.String `tfsdk:"session_id"`
	Metadata     types.Map    `tfsdk:"metadata"`
	ClaimedBy    types.String `tfsdk:"claimed_by"`
	Slug         types.String `tfsdk:"slug"`
}

func buildClaimPayload(ctx context.Context, plan claimResourceModel) (ClaimNameRequest, diag.Diagnostics) {
	var diags diag.Diagnostics
	payload := ClaimNameRequest{
		ResourceType: plan.ResourceType.ValueString(),
		Region:       plan.Region.ValueString(),
		Environment:  plan.Environment.ValueString(),
	}

	if !plan.Project.IsNull() && !plan.Project.IsUnknown() {
		v := plan.Project.ValueString()
		payload.Project = &v
	}
	if !plan.Purpose.IsNull() && !plan.Purpose.IsUnknown() {
		v := plan.Purpose.ValueString()
		payload.Purpose = &v
	}
	if !plan.Subsystem.IsNull() && !plan.Subsystem.IsUnknown() {
		v := plan.Subsystem.ValueString()
		payload.Subsystem = &v
	}
	if !plan.System.IsNull() && !plan.System.IsUnknown() {
		v := plan.System.ValueString()
		payload.System = &v
	}
	if !plan.Index.IsNull() && !plan.Index.IsUnknown() {
		v := plan.Index.ValueString()
		payload.Index = &v
	}
	if !plan.SessionID.IsNull() && !plan.SessionID.IsUnknown() {
		v := plan.SessionID.ValueString()
		payload.SessionID = &v
	}
	if !plan.Metadata.IsNull() && !plan.Metadata.IsUnknown() {
		metadata := make(map[string]string)
		diags = append(diags, plan.Metadata.ElementsAs(ctx, &metadata, false)...)
		payload.Metadata = metadata
	}

	return payload, diags
}

func (r *ClaimResource) Metadata(_ context.Context, req resource.MetadataRequest, resp *resource.MetadataResponse) {
	resp.TypeName = req.ProviderTypeName + "_claim"
}

func (r *ClaimResource) Schema(_ context.Context, _ resource.SchemaRequest, resp *resource.SchemaResponse) {
	resp.Schema = schema.Schema{
		MarkdownDescription: "Claims a name via the SanMar Azure naming service and manages its lifecycle.",
		Attributes: map[string]schema.Attribute{
			"id": schema.StringAttribute{
				Computed: true,
				PlanModifiers: []planmodifier.String{
					stringplanmodifier.UseStateForUnknown(),
				},
				MarkdownDescription: "Identifier for Terraform state equal to the generated name.",
			},
			"name": schema.StringAttribute{
				Computed:            true,
				MarkdownDescription: "The generated resource name returned by the service.",
				PlanModifiers: []planmodifier.String{
					stringplanmodifier.UseStateForUnknown(),
				},
			},
			"resource_type": schema.StringAttribute{
				Required:            true,
				MarkdownDescription: "Azure resource type identifier used for slug resolution.",
				Validators: []schema.AttributeValidator{
					stringvalidator.LengthAtLeast(1),
				},
			},
			"region": schema.StringAttribute{
				Required:            true,
				MarkdownDescription: "Azure region short code (for example, wus2).",
				Validators: []schema.AttributeValidator{
					stringvalidator.LengthBetween(2, 8),
				},
			},
			"environment": schema.StringAttribute{
				Required:            true,
				MarkdownDescription: "Deployment environment such as dev, stg, or prd.",
				Validators: []schema.AttributeValidator{
					stringvalidator.LengthAtLeast(2),
				},
			},
			"project": schema.StringAttribute{
				Optional:            true,
				MarkdownDescription: "Optional project segment.",
			},
			"purpose": schema.StringAttribute{
				Optional:            true,
				MarkdownDescription: "Optional purpose segment.",
			},
			"subsystem": schema.StringAttribute{
				Optional: true,
			},
			"system": schema.StringAttribute{
				Optional: true,
			},
			"index": schema.StringAttribute{
				Optional: true,
			},
			"session_id": schema.StringAttribute{
				Optional:            true,
				MarkdownDescription: "Optional session identifier to pre-populate defaults.",
			},
			"metadata": schema.MapAttribute{
				Optional:    true,
				ElementType: types.StringType,
				PlanModifiers: []planmodifier.Map{
					mapplanmodifier.UseStateForUnknown(),
				},
				MarkdownDescription: "Additional metadata that will be forwarded to the claim request.",
			},
			"claimed_by": schema.StringAttribute{
				Computed:            true,
				MarkdownDescription: "Identifier of the caller stored by the service.",
			},
			"slug": schema.StringAttribute{
				Computed:            true,
				MarkdownDescription: "Slug resolved for the resource type.",
			},
		},
	}
}

func (r *ClaimResource) Configure(_ context.Context, req resource.ConfigureRequest, resp *resource.ConfigureResponse) {
	if req.ProviderData == nil {
		return
	}
	client, ok := req.ProviderData.(*APIClient)
	if !ok {
		resp.Diagnostics.AddError("Unexpected provider data", fmt.Sprintf("expected *APIClient got %T", req.ProviderData))
		return
	}
	r.client = client
}

func (r *ClaimResource) Create(ctx context.Context, req resource.CreateRequest, resp *resource.CreateResponse) {
	if r.client == nil {
		resp.Diagnostics.AddError("Unconfigured provider", "The provider has not been configured; call provider block first.")
		return
	}

	var plan claimResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &plan)...)
	if resp.Diagnostics.HasError() {
		return
	}

	payload, diags := buildClaimPayload(ctx, plan)
	resp.Diagnostics.Append(diags...)
	if resp.Diagnostics.HasError() {
		return
	}

	tflog.Info(ctx, "claiming name via SanMar provider", map[string]any{
		"resource_type": payload.ResourceType,
		"region":        payload.Region,
		"environment":   payload.Environment,
	})

	claim, err := r.client.ClaimName(ctx, payload)
	if err != nil {
		resp.Diagnostics.AddError("Failed to claim name", err.Error())
		return
	}

	plan.ID = types.StringValue(claim.Name)
	plan.Name = types.StringValue(claim.Name)
	plan.ClaimedBy = types.StringValue(claim.ClaimedBy)
	plan.Slug = types.StringValue(claim.Slug)

	resp.Diagnostics.Append(resp.State.Set(ctx, &plan)...)
}

func (r *ClaimResource) Read(ctx context.Context, req resource.ReadRequest, resp *resource.ReadResponse) {
	if r.client == nil {
		resp.Diagnostics.AddError("Unconfigured provider", "The provider has not been configured; call provider block first.")
		return
	}

	var state claimResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &state)...)
	if resp.Diagnostics.HasError() {
		return
	}

	record, err := r.client.GetAudit(ctx, state.Region.ValueString(), state.Environment.ValueString(), state.Name.ValueString())
	if err != nil {
		resp.Diagnostics.AddError("Failed to read claim", err.Error())
		return
	}

	if record == nil || !record.InUse {
		resp.State.RemoveResource(ctx)
		return
	}

	state.ClaimedBy = types.StringValue(record.ClaimedBy)
	state.Slug = types.StringValue(record.Slug)
	resp.Diagnostics.Append(resp.State.Set(ctx, &state)...)
}

func (r *ClaimResource) Update(ctx context.Context, req resource.UpdateRequest, resp *resource.UpdateResponse) {
	if r.client == nil {
		resp.Diagnostics.AddError("Unconfigured provider", "The provider has not been configured; call provider block first.")
		return
	}

	var plan claimResourceModel
	var state claimResourceModel
	resp.Diagnostics.Append(req.Plan.Get(ctx, &plan)...)
	resp.Diagnostics.Append(req.State.Get(ctx, &state)...)
	if resp.Diagnostics.HasError() {
		return
	}

	// If nothing relevant changed, keep existing state.
	if plan.ResourceType.Equal(state.ResourceType) &&
		plan.Region.Equal(state.Region) &&
		plan.Environment.Equal(state.Environment) &&
		plan.Project.Equal(state.Project) &&
		plan.Purpose.Equal(state.Purpose) &&
		plan.Subsystem.Equal(state.Subsystem) &&
		plan.System.Equal(state.System) &&
		plan.Index.Equal(state.Index) &&
		plan.SessionID.Equal(state.SessionID) &&
		plan.Metadata.Equal(state.Metadata) {
		resp.Diagnostics.Append(resp.State.Set(ctx, &state)...)
		return
	}

	// Release the existing claim.
	releasePayload := ReleaseRequest{
		Name:        state.Name.ValueString(),
		Region:      state.Region.ValueString(),
		Environment: state.Environment.ValueString(),
		Reason:      "terraform update",
	}

	if err := r.client.ReleaseName(ctx, releasePayload); err != nil {
		resp.Diagnostics.AddError("Failed to release existing name", err.Error())
		return
	}

	payload, diags := buildClaimPayload(ctx, plan)
	resp.Diagnostics.Append(diags...)
	if resp.Diagnostics.HasError() {
		return
	}

	claim, err := r.client.ClaimName(ctx, payload)
	if err != nil {
		resp.Diagnostics.AddError("Failed to claim replacement name", err.Error())
		return
	}

	plan.ID = types.StringValue(claim.Name)
	plan.Name = types.StringValue(claim.Name)
	plan.ClaimedBy = types.StringValue(claim.ClaimedBy)
	plan.Slug = types.StringValue(claim.Slug)

	resp.Diagnostics.Append(resp.State.Set(ctx, &plan)...)
}

func (r *ClaimResource) Delete(ctx context.Context, req resource.DeleteRequest, resp *resource.DeleteResponse) {
	if r.client == nil {
		resp.Diagnostics.AddError("Unconfigured provider", "The provider has not been configured; call provider block first.")
		return
	}

	var state claimResourceModel
	resp.Diagnostics.Append(req.State.Get(ctx, &state)...)
	if resp.Diagnostics.HasError() {
		return
	}

	if state.Name.IsNull() || state.Name.ValueString() == "" {
		resp.State.RemoveResource(ctx)
		return
	}

	payload := ReleaseRequest{
		Name:        state.Name.ValueString(),
		Region:      state.Region.ValueString(),
		Environment: state.Environment.ValueString(),
		Reason:      "terraform destroy",
	}

	if err := r.client.ReleaseName(ctx, payload); err != nil {
		resp.Diagnostics.AddError("Failed to release name", err.Error())
		return
	}
	resp.State.RemoveResource(ctx)
}

func (r *ClaimResource) ImportState(ctx context.Context, req resource.ImportStateRequest, resp *resource.ImportStateResponse) {
	resource.ImportStatePassthroughID(ctx, path.Root("id"), req, resp)
}
