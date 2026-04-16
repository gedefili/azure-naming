# [OPERATOR ACTION REQUIRED] Azure DevOps Enforcement And GitHub Shutdown Plan

This plan is for a human operator with the required repository and project
administration rights. It is not an agent-owned task.

## Purpose

The repository source of truth has already been migrated to Azure DevOps:

- Azure DevOps pipeline definition: `333` (`azure-naming`)
- Azure DevOps variable group: `155` (`azure-naming-shared`)
- Azure Repos main branch now contains `azure-pipelines.yml`
- GitHub workflow files have been removed from the Azure Repos source-of-truth repository

Two control-plane actions still require operator permissions that were not
available to the agent session:

1. disable the retired GitHub Actions workflows in `gedefili/azure-naming`
2. enforce Azure DevOps build validation on `main` for pipeline `333`

The order matters. Enable Azure DevOps enforcement first, then shut down GitHub
automation.

## Why Operator Action Is Required

The agent completed the repository migration work but was blocked by external
permissions:

- GitHub workflow disable calls returned `HTTP 403` because the token did not
  have repository admin rights.
- Azure DevOps build policy creation failed with `TF401027` because the current
  identity did not have Azure Repos `EditPolicies` permission on the branch.

## Step 2: Enforce Azure DevOps On `main`

This step makes Azure DevOps the required gate before merges.

### Required access

- Azure DevOps project access to `Infrastructure Administration`
- Azure Repos permission: `EditPolicies` on repository `cloud-resource-naming`
- Ability to view and edit repository branch policies

### Target objects

- Repository: `cloud-resource-naming`
- Branch: `main`
- Pipeline: `333` (`azure-naming`)

### What to configure

Add a build validation policy on `main` that requires pipeline `333`.

Recommended settings:

- `blocking = true`
- `enabled = true`
- `manual-queue-only = false`
- `queue-on-source-update-only = true`
- `branch-match-type = exact`
- `valid-duration = 0`

### UI procedure

1. Open Azure DevOps.
2. Go to `Infrastructure Administration`.
3. Open `Project Settings`.
4. Open `Repositories`.
5. Select repository `cloud-resource-naming`.
6. Open `Policies`.
7. Under branch policies for `main`, add a `Build validation` policy.
8. Choose pipeline `azure-naming`.
9. Set the policy to blocking and save it.

### CLI procedure

If you have `EditPolicies`, this command should work:

```bash
az repos policy build create \
  --organization https://dev.azure.com/sanmarcloud \
  --project "Infrastructure Administration" \
  --repository-id e5584bd0-5e29-4170-b8fd-7c5ac4cedf64 \
  --branch main \
  --branch-match-type exact \
  --build-definition-id 333 \
  --display-name "azure-naming pipeline" \
  --blocking true \
  --enabled true \
  --manual-queue-only false \
  --queue-on-source-update-only true \
  --valid-duration 0
```

### Verification

Verify all of the following after policy creation:

1. Opening a new PR against `main` shows `azure-naming pipeline` as a required check.
2. A source update on the PR queues a new Azure DevOps run automatically.
3. The PR cannot be completed while the required build is failing or still running.
4. The build shown on the PR is Azure DevOps pipeline `333`, not a GitHub check.

### Expected current run state

At the time this plan was written:

- branch verification run: `265183`
- first post-merge `main` run: `265184`

Those runs prove the Azure DevOps pipeline definition is live. The current test
failures observed there match preexisting failures already reproducible on clean
`main`, so enforcement should be based on the intended Azure DevOps pipeline even
if additional application test repair is needed separately.

## Step 1: Disable Retired GitHub Workflows

This step prevents the legacy GitHub repository from triggering old CI, deploy,
release, or label automation.

### Required access

- GitHub repository admin access to `gedefili/azure-naming`
- Ability to manage repository Actions settings or disable individual workflows

### Workflows to disable

Disable these active workflow definitions in GitHub:

- `198342433` — `CI`
- `198343998` — `CodeQL`
- `198344081` — `Create Labels`
- `177064351` — `Deploy to Azure`
- `258130931` — `Publish Dev Container`
- `198564832` — `Integration tests`
- `198343529` — `Labeler`
- `198567125` — `Postman collection`
- `198342620` — `Release`
- `177064236` — `Unit Tests`
- `198343590` — `Dependabot Updates`

`Stale` was already in `disabled_inactivity` state when this plan was created.

### UI procedure

1. Open the GitHub repository `gedefili/azure-naming`.
2. Go to `Actions`.
3. Open each workflow listed above.
4. Use the workflow menu to disable it.
5. Repeat until the workflow list shows no active CI/CD workflows for this retired repo.

### API procedure

With a GitHub token that has repository admin rights, the disable call is:

```bash
gh api -X PUT repos/gedefili/azure-naming/actions/workflows/<workflow-id>/disable
```

Example:

```bash
gh api -X PUT repos/gedefili/azure-naming/actions/workflows/177064351/disable
```

### Repository-level hardening

If the GitHub repository is truly retired, also consider these operator-only
follow-up actions:

1. Remove or rotate any remaining GitHub repository secrets related to Azure deployment.
2. Disable GitHub Actions entirely at repository settings if no workflows should ever run there again.
3. Update branch protection and required checks in GitHub so they no longer reference retired workflows.
4. Add a short repository banner or README notice in GitHub indicating Azure DevOps is the active control plane.

### Verification

Verify all of the following after shutdown:

1. The GitHub `Actions` tab shows the listed workflows as disabled.
2. A push or tag in the retired GitHub mirror does not trigger `Deploy to Azure` or `Release`.
3. No GitHub deployment has occurred after the disable operation.
4. Operators understand that Azure DevOps, not GitHub, is now the only supported automation path.

## Recommended Execution Order

Execute the cutover in this order:

1. Confirm Azure DevOps pipeline `333` exists and can queue.
2. Add Azure DevOps build validation to `main`.
3. Verify a PR shows Azure DevOps as the required gate.
4. Disable the retired GitHub workflows.
5. Remove or rotate GitHub deployment secrets if the repo will remain accessible.

## Rollback Considerations

If Azure DevOps enforcement is misconfigured:

- do not re-enable GitHub deployment as a first response
- instead, correct the Azure DevOps pipeline definition, variable group, or policy wiring
- only restore a GitHub workflow temporarily if there is an explicit operator decision to use GitHub as an emergency fallback

## Success Criteria

The cutover is complete when all of the following are true:

1. PRs to `main` are gated by Azure DevOps pipeline `333`.
2. The GitHub repository no longer runs deploy, release, CI, or label workflows.
3. Azure DevOps is the only active path for deployment and release automation.
4. Operators can point to one control plane for approvals, logs, artifacts, and deployment history.