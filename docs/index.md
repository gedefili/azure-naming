# 📚 Azure Naming Function Documentation Hub

Use this page as the map to every guide, reference, and workflow in the repository. Each section includes the core document plus any supporting assets so you can jump straight to what you need.

---

## 🧭 Getting Started & API Usage

- **[usage.md](usage.md)** — Walks through every endpoint (claim, release, audit, slug sync) with expected payloads and responses.
- **[auth.md](auth.md)** — Explains Entra ID roles, token validation, and how callers gain access.
- **[../README.md](../README.md)** — The main README includes the architecture diagram and high-level system overview.

---

## � Local Development & Testing

- **[local-testing.md](local-testing.md)** — Covers Azurite setup, running Functions locally, and OpenAPI exploration.
- **[token_workflow.md](token_workflow.md)** — Step-by-step bearer token acquisition for both CLI and CI flows.
- **[postman.md](postman.md)** — Guidance for the provided Postman collection, environments, and Newman usage.
- **[postman-link.md](postman-link.md)** — Direct share link for quickly importing the Postman collection.
- **Assets**: `postman-local-collection.json`, `tests/postman_collection.json`, and `tests/postman_environment.json` support automated runs.

---

## ⚙️ Operations & Deployment

- **[deployment.md](deployment.md)** — Provisioning checklist, configuration, and release workflow notes.
- **[cost-estimate.md](cost-estimate.md)** — High-level 10-year cost projection for the Azure footprint.

---

## 🧠 Architecture & Internals

- **[schema.md](schema.md)** — Data model, naming rules, and provider pipeline documentation.
- **[module-structure.md](module-structure.md)** — Describes how the Python packages are organized and wired.
- **[architecture.mmd](architecture.mmd)** — Mermaid source for the high-level system diagram that appears in the README.

---

## 🔄 Automation & Team Processes

- **[token_workflow.md](token_workflow.md)** — Automation-safe bearer token acquisition for CI inputs.
- **[postman.md](postman.md)** — Manual and automated Postman runs that backstop CI.
- **[../RELEASE.md](../RELEASE.md)** — Release management checklist and tagging guidance.

---

Looking for something else? Search the repository or reach out in the project channel and we’ll add it here.
