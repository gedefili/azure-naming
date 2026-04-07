# 🔧 Operations

Guides for deployment, security, compliance, cost management, and release procedures.

## Documents

- **[Deployment Checklist](deployment.md)** — Current standard for `environs-iac` provisioning and code publish
- **[Security & Compliance](SECURITY.md)** — Security model, encryption, compliance considerations
- **[Security Audit Report](security-audit-2025-10-16.md)** — Professional third-party security assessment
- **[Cost Estimation](cost-estimate.md)** — 10-year cost projection and optimization strategies
- **[Professional Standards Review](professional-standards-review-2025-10-16.md)** — Code quality and best practices assessment
- **[Release Process](RELEASE.md)** — Version management, tagging, and release workflow

## Key Topics

### Security

- Role-based access control (RBAC)
- Token validation and Entra ID integration
- Data encryption (at rest and in transit)
- Audit logging for compliance

See: [Security & Compliance](SECURITY.md) and [Security Audit Report](security-audit-2025-10-16.md)

### Deployment

- Azure resource provisioning from `environs-iac` and code publish from this repo
- Configuration management
- Environment setup and handoff between IaC and application deployment
- Database schema initialization

See: [Deployment Checklist](deployment.md)

### Cost Management

- 10-year cost projection
- Optimization recommendations
- Consumption patterns analysis
- Budget forecasting

See: [Cost Estimation](cost-estimate.md)

### Release Management

- Version tagging (`git tag`)
- Changelog updates
- Release workflow
- Artifact management

See: [Release Process](RELEASE.md)

## Production Readiness Checklist

Before deploying to production, verify:

- ✅ All security requirements met ([Security & Compliance](SECURITY.md))
- ✅ Cost estimates reviewed ([Cost Estimation](cost-estimate.md))
- ✅ Deployment steps understood ([Deployment Checklist](deployment.md))
- ✅ Release process documented ([Release Process](RELEASE.md))
- ✅ Code quality standards verified ([Professional Standards Review](professional-standards-review-2025-10-16.md))
- ✅ All tests passing locally
- ✅ Documentation updated

## See Also

- **Getting Started** → [App Registration](../02-getting-started/app-registration.md)
- **Development** → [Local Testing](../04-development/local-testing.md)
- **Contributing** → [Contributing Guidelines](../01-planning/CONTRIBUTING.md)

## Quick Links

- [Back to Main Index](../index.md)
- [Full Documentation](../index.md#-operations)
- [Main README](../../README.md) — High-level overview
