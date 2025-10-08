# 🧪 Local Development & Postman Testing

These instructions walk you through running the Azure Naming Function locally and exercising the HTTP endpoints from tools like Postman or curl before deploying to Azure.

---

## 1. Prerequisites

| Requirement | Notes |
| ----------- | ----- |
| Python 3.10+ | Matches the Functions worker runtime. |
| Node.js 18+ / npm | Required to install the Azure Functions Core Tools via npm on Linux/WSL. |
| [Azure Functions Core Tools](https://learn.microsoft.com/azure/azure-functions/functions-run-local) | Provides the `func` CLI for local runs. Install with `npm install -g azure-functions-core-tools@4 --unsafe-perm true` on Linux/WSL. |
| [Azurite](https://learn.microsoft.com/azure/storage/common/storage-use-azurite) | Emulates Azure Table Storage locally. Install via npm (`npm install -g azurite`) or Docker. |
| Optional: [Postman](https://www.postman.com/downloads/) | Used for manual API testing. |

### Install Azure Functions Core Tools (WSL/Linux)

The Azure Functions Core Tools provide the `func` CLI that starts your local Functions host. The fastest option on WSL/Ubuntu is to install via npm (requires Node.js, already used for Azurite):

```bash
npm install -g azure-functions-core-tools@4 --unsafe-perm true
```

After installation, confirm the CLI is available:

```bash
func --version
```

If the command is still not found, open a new terminal so your updated `PATH` is picked up or ensure your npm global bin directory is exported (usually `~/.npm-global/bin` on WSL).

> 💡 If you prefer Docker, you can run `docker run -p 10000:10000 -p 10001:10001 -p 10002:10002 mcr.microsoft.com/azure-storage/azurite` to launch Azurite quickly.

---

## 2. Configure Environment

1. Clone the repository and switch into the project folder.
2. Create a Python virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

  This pulls in the Azure Functions runtime libraries, the Azure Table SDK, JWT tooling, and the local test dependencies defined in `requirements.txt`.

3. Verify the Azure Functions Core Tools are available (install if needed):

  ```bash
  func --version
  ```

  If the command isn’t found, run the npm install command from the prerequisites table, then re-open your shell so `func` is on the PATH.

4. Start Azurite in a separate terminal:

   ```bash
   azurite --silent --location .azurite --debug .azurite/debug.log
   ```

5. Enable the local auth bypass so you can call the APIs without a real Entra ID token. Update **`local.settings.json`** (or set environment variables) with:

   ```json
   {
     "Values": {
       "ALLOW_LOCAL_AUTH_BYPASS": "true",
       "LOCAL_BYPASS_USER_ID": "local-dev-user",
       "LOCAL_BYPASS_ROLES": "user,manager"
     }
   }
   ```

   You can also export these directly:

   ```bash
   export ALLOW_LOCAL_AUTH_BYPASS=true
   export LOCAL_BYPASS_USER_ID=local-dev-user
   export LOCAL_BYPASS_ROLES=user,manager
   ```

   > ⚠️ Keep the bypass disabled in shared or hosted environments. It is intended only for isolated local testing.

---

## 3. Run the Functions Host Locally

With Azurite running and the virtual environment activated, start the Functions runtime:

```bash
func start
```

You should see the HTTP triggers listening on `http://localhost:7071/api/...`.

---

## 4. Test with Postman (or curl)

1. **Create a new Postman environment** with a `base_url` variable set to `http://localhost:7071`.
2. Import the [Postman collection](./postman-local-collection.json) included in this repository or create your own requests using the examples below.
3. Because the local auth bypass is enabled, you do **not** need to add an `Authorization` header. If you want to mimic production behavior, disable the bypass and supply a valid bearer token.

### Example Requests

**Claim a name**

```
POST {{base_url}}/api/claim
Content-Type: application/json

{
  "resource_type": "storage_account",
  "environment": "dev",
  "region": "wus2",
  "project": "finance",
  "purpose": "costreports",
  "system": "erp",
  "index": "01"
}
```

**Release a name**

```
POST {{base_url}}/api/release
Content-Type: application/json

{
  "name": "sanmar-st-finance-costreports-dev-wus2-01"
}
```

**Audit a name**

```
GET {{base_url}}/api/audit?name=sanmar-st-finance-costreports-dev-wus2-01
```

All endpoints return JSON responses and standard HTTP status codes identical to production.

---

## 5. Running Automated Tests

While the Functions host is running, you can still execute the Python unit tests in another terminal:

```bash
pytest
```

---

## 6. Cleaning Up

* Stop the Functions host with `Ctrl+C`.
* Stop Azurite (or the Docker container) when you are done.
* Deactivate the Python virtual environment with `deactivate`.

---

### Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `403 Forbidden` responses while bypass is enabled | Ensure `LOCAL_BYPASS_ROLES` includes the role required by the endpoint (e.g., `manager` for bulk audit). |
| Functions host cannot connect to storage | Confirm Azurite is running and `AzureWebJobsStorage` is set to `UseDevelopmentStorage=true`. |
| Still prompted for bearer token | Check that `ALLOW_LOCAL_AUTH_BYPASS` is `true` in the environment where the host is running. |

Happy testing! 🚀
