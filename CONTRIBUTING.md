# 🤝 Contributing to Azure Naming Function

Thank you for considering contributing to this project! This guide outlines the process and standards for contributions.

---

## 🧱 Project Structure

This project is built using Azure Functions (Python) with:

* Azure Table Storage for state
* GitHub slug specs for name logic
* Entra ID for authentication/authorization

You’ll find:

* Function endpoints in their own folders under `app/routes/`
* Domain logic in `core/` and integration adapters in `adapters/`
* Docs in `docs/`

---

## 🚀 Getting Started

1. Fork the repository
2. Clone your fork
3. Set up a Python 3.10+ virtual environment
4. Run `pip install -r requirements.txt`
5. Use `func start` to launch the Azure Functions locally

---

## ✅ Contribution Guidelines

* Follow the file headers format used in existing modules.
* Add docstrings and inline comments for complex logic.
* Keep functions SOLID and DRY — extract shared logic to `core/` or `adapters/` as appropriate.
* Ensure RBAC is enforced using the `auth.check_access()` helper.
* Add/update docs as needed in `docs/`.

---

## 🧪 Testing

While formal unit tests are in progress, manual testing is expected for all changes. If you add utility functions, please include corresponding test files in a future `tests/` folder.

---

## 🔁 Submitting Changes

1. Commit to a feature branch in your fork
2. Ensure your code builds and deploys locally
3. Submit a pull request with a description of changes

Please be sure to:

* Use descriptive commit messages
* Reference any related issues

---

## 📬 Communication

For significant changes or questions, open an issue to start a discussion before writing code.

---

Thanks again for helping improve this project! 🚀
