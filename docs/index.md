# 📚 Azure Naming Function Documentation

Welcome to the comprehensive documentation hub for the Azure Naming Function project. This index provides a complete roadmap to all guides, references, specifications, and operational procedures.

**Quick Links:**
- 🚀 [Getting Started](#-getting-started) — First-time setup, Terraform-managed registration, and token flow
- 📖 [API Reference](#-api-reference) — Endpoint specifications and data schemas
- 🛠️ [Development](#-development) — Local testing, architecture, and internals
- 🔧 [Operations](#-operations) — Deployment, security, monitoring
- 📋 [Planning & Processes](#-planning--processes) — Contributing, releases, changes
- 🔄 [Refactoring & Architecture](#-refactoring--architecture) — Code improvements and library specs

---

## 🚀 Getting Started

**Start here if you're new to the project or setting it up for the first time.**

| Document | Purpose |
|----------|---------|
| **[App Registration Guide](02-getting-started/app-registration.md)** | Current Entra standard: Terraform-managed API registration plus testing client setup |
| **[Authentication & Authorization](02-getting-started/auth.md)** | Understanding token validation and role-based access |
| **[Main README](../README.md)** | Project overview, architecture diagram, and high-level system design |

### What You'll Learn
- ✅ How the service registration is created in `environs-iac`
- ✅ How role-based access control (RBAC) works
- ✅ Token flow and security model
- ✅ System architecture and component interactions

---

## 📖 API Reference

**Detailed specifications for all endpoints, request/response formats, and data models.**

| Document | Purpose |
|----------|---------|
| **[Usage & Endpoints](03-api-reference/usage.md)** | Complete endpoint reference with payloads, responses, and examples |
| **[Data Schema](03-api-reference/schema.md)** | Azure Table Storage schema, naming rules, and provider pipeline |

### Endpoints Covered
- `POST /api/claim` — Generate and reserve a name
- `GET  /api/slug` — Resolve slug for resource type
- `POST /api/release` — Release/recycle a name
- `GET  /api/audit` — Query audit logs
- `GET  /api/audit_bulk` — Bulk audit queries
- `POST /api/slug_sync` — Refresh slug mappings
- `GET  /api/docs` — Interactive Swagger UI
- `GET  /api/openapi.json` — OpenAPI 3.0 specification

---

## 🛠️ Development

**Everything needed for local development, testing, and understanding the codebase architecture.**

| Document | Purpose |
|----------|---------|
| **[Local Testing Setup](04-development/local-testing.md)** | Azurite configuration, Functions runtime, and testing workflow |
| **[Module Structure](04-development/module-structure.md)** | Python package organization and component responsibilities |
| **[Architecture Deep Dive](04-development/architecture.mmd)** | Mermaid diagram showing system components and interactions |
| **[Token Workflow](04-development/token_workflow.md)** | Bearer token acquisition for CLI, CI/CD, and testing |
| **[Postman Testing](04-development/postman.md)** | API collection setup, environments, and automated testing |

### Assets
- [Postman Collection](04-development/postman-local-collection.json) — Importable API collection with pre-configured endpoints
- [Token Workflow Guide](04-development/token_workflow.md) — Automation-safe token acquisition

### What You'll Learn
- ✅ How to run the service locally with Azurite
- ✅ Project structure and module responsibilities
- ✅ How to obtain bearer tokens for testing
- ✅ How to test endpoints with Postman or curl
- ✅ System architecture and data flow

---

## 🔧 Operations

**Guides for deployment, security, monitoring, and production concerns.**

| Document | Purpose |
|----------|---------|
| **[Deployment Checklist](05-operations/deployment.md)** | `environs-iac` provisioning, code publish workflow, and go-live steps |
| **[Security & Compliance](05-operations/SECURITY.md)** | Security model, encryption, and compliance considerations |
| **[Security Audit Report](05-operations/security-audit-2025-10-16.md)** | Professional security assessment results |
| **[Cost Estimation](05-operations/cost-estimate.md)** | 10-year cost projection and optimization strategies |
| **[Professional Standards Review](05-operations/professional-standards-review-2025-10-16.md)** | Code quality and best practices assessment |
| **[Release Process](05-operations/RELEASE.md)** | Version tagging, changelog management, and release workflow |

### Key Topics
- ✅ Azure resource setup and configuration under the current two-repository standard
- ✅ Security model and role-based access control
- ✅ Encryption and compliance requirements
- ✅ Cost analysis and optimization
- ✅ Release management and versioning

---

## 📋 Planning & Processes

**Project governance, contribution guidelines, and change tracking.**

| Document | Purpose |
|----------|---------|
| **[Contributing Guidelines](01-planning/CONTRIBUTING.md)** | How to contribute code, report issues, and submit PRs |
| **[Changelog](01-planning/CHANGELOG.md)** | Complete history of all releases and changes (latest first) |
| **[Changelog (New)](01-planning/CHANGELOG.new.md)** | Unreleased changes and upcoming features |

### What You'll Find
- ✅ Contribution workflow and code standards
- ✅ Complete release history
- ✅ Upcoming features and breaking changes

---

## 🔄 Refactoring & Architecture

**Documentation from the code quality and architecture refactoring initiative.**

| Document | Purpose |
|----------|---------|
| **[Refactoring Complete Report](06-refactoring/REFACTORING_COMPLETE.md)** | Phase 1 & 2 completion summary, metrics, and validation results |
| **[Refactoring Plan](06-refactoring/REFACTORING_PLAN.md)** | 3-phase roadmap, duplication analysis, and implementation strategy |
| **[Refactoring Checklist](06-refactoring/REFACTORING_CHECKLIST.md)** | Step-by-step implementation guide and validation checklist |
| **[Library Specifications](06-refactoring/LIBRARY_SPECIFICATIONS.md)** | Complete API specifications for reusable library modules |

### Key Achievements
- ✅ 875 → 685 lines of code (-22% reduction)
- ✅ 40 lines of duplication eliminated (100%)
- ✅ 5/5 SOLID principles applied
- ✅ 20/20 unit tests (100% passing)
- ✅ Zero breaking changes to CLI interfaces

---

## 🗂️ Documentation Structure

The documentation is organized into logical categories:

```
docs/
├── 01-planning/              Project planning, contributing, releases
├── 02-getting-started/       Initial setup, registration, auth
├── 03-api-reference/         Endpoint specs and data schemas
├── 04-development/           Local testing, architecture, Postman
├── 05-operations/            Deployment, security, cost, release process
├── 06-refactoring/           Code quality initiative documentation
└── index.md                  This master index
```

---

## 🔎 Finding What You Need

**I want to...**

| Goal | Start Here |
|------|-----------|
| Get the service running locally | [Local Testing Setup](04-development/local-testing.md) |
| Understand how the API registration is created | [App Registration Guide](02-getting-started/app-registration.md) |
| Call the API endpoints | [Usage & Endpoints](03-api-reference/usage.md) → [Token Workflow](04-development/token_workflow.md) |
| Understand the system architecture | [Architecture Deep Dive](04-development/architecture.mmd) + [Module Structure](04-development/module-structure.md) |
| Deploy to production | [Deployment Checklist](05-operations/deployment.md) |
| Review security/compliance | [Security & Compliance](05-operations/SECURITY.md) + [Security Audit](05-operations/security-audit-2025-10-16.md) |
| Contribute to the project | [Contributing Guidelines](01-planning/CONTRIBUTING.md) |
| Release a new version | [Release Process](05-operations/RELEASE.md) |
| Understand the refactoring | [Refactoring Report](06-refactoring/REFACTORING_COMPLETE.md) |

---

## 📞 Need Help?

- **Local setup issues?** → See [Local Testing Setup](04-development/local-testing.md)
- **API questions?** → Check [Usage & Endpoints](03-api-reference/usage.md) and [Data Schema](03-api-reference/schema.md)
- **Contributing?** → Read [Contributing Guidelines](01-planning/CONTRIBUTING.md)
- **Security concerns?** → Review [Security & Compliance](05-operations/SECURITY.md)
- **Other issues?** → Search the documentation or reach out to the team

---

## 📈 Documentation Status

Core deployment and registration guidance was updated on April 7, 2026 to reflect the move of infrastructure provisioning to `environs-iac`.

| Section | Status | Last Updated |
|---------|--------|--------------|
| Getting Started | ✅ Current | April 7, 2026 |
| API Reference | ✅ Current | October 2025 |
| Development | ✅ Current | October 29, 2025 |
| Operations | ✅ Current | April 7, 2026 |
| Planning | ✅ Current | October 29, 2025 |
| Refactoring | ✅ Complete | October 29, 2025 |

---

## 🎯 Quick Reference

**Key Concepts:**
- **Slugs** — Standardized identifiers for Azure resources (e.g., `sa` for storage account)
- **Naming Rules** — JSON-based rules engine determining valid names
- **App Roles** — Three RBAC levels: Reader, Contributor, Admin
- **Audit Trail** — Complete history of all naming operations
- **Provider Chain** — Pluggable system for slug resolution

**Important URLs:**
- API Endpoints: `http://localhost:7071/api/` (local) or `https://<function-app>.azurewebsites.net/api/` (production)
- OpenAPI Docs: `/api/docs` (Swagger UI) or `/api/openapi.json` (specification)
- GitHub Repository: https://github.com/gedefili/azure-naming

---

*For a visual overview, see the architecture diagram in the [Main README](../README.md).*
