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
  python3 -m venv .venv  # Windows (PowerShell): py -m venv .venv
  source .venv/bin/activate  # Windows: .venv\Scripts\activate
  python3 -m pip install -r requirements.txt
  ```

  This pulls in the Azure Functions runtime libraries, the Azure Table SDK, JWT tooling, and the local test dependencies defined in `requirements.txt`.

3. Verify the Azure Functions Core Tools are available (install if needed):

  ```bash
  func --version
  ```

  If the command isn’t found, run the npm install command from the prerequisites table, then re-open your shell so `func` is on the PATH.

4. The Functions project now uses the Python v2 programming model with a single entry point in `function_app.py`. No per-function folders are required—the decorated functions in that file define every trigger.

5. Start Azurite in a separate terminal:

   ```bash
   azurite --silent --location .azurite --debug .azurite/debug.log
   ```

6. Configure authentication options:

   - For local-only testing, you can enable the bypass so you can call the APIs without a real Entra ID token. Update **`local.settings.json`** (or set environment variables) with:

   ```json
   {
     "Values": {
       "ALLOW_LOCAL_AUTH_BYPASS": "true",
       "LOCAL_BYPASS_USER_ID": "local-dev-user",
       "LOCAL_BYPASS_ROLES": "contributor,admin"
     }
   }
   ```

   You can also export these directly:

   ```bash
   export ALLOW_LOCAL_AUTH_BYPASS=true
   export LOCAL_BYPASS_USER_ID=local-dev-user
  export LOCAL_BYPASS_ROLES=contributor,admin
   ```

   - To integrate with Entra ID groups, set the optional environment variables that map each role to a group ID:

     | Variable | Description |
     | --- | --- |
     | `AZURE_ROLE_GROUP_READER` | GUID for the **Sanmar Naming Reader** group/app role. |
     | `AZURE_ROLE_GROUP_CONTRIBUTOR` | GUID for the **Sanmar Naming Contributor** group/app role. |
     | `AZURE_ROLE_GROUP_ADMIN` | GUID for the **Sanmar Naming Admin** group/app role. |

   - To override the pluggable providers used by the application, set one or both of the following:

     | Variable | Description |
     | --- | --- |
     | `NAMING_RULE_PROVIDER` | Dotted path to a callable or object that returns a provider with `get_rule(resource_type) -> NamingRule`. |
     | `SLUG_PROVIDER` | Dotted path to a callable or object (or sequence) that yields providers implementing `get_slug(resource_type) -> str`. |

   > ⚠️ Keep the bypass disabled in shared or hosted environments. It is intended only for isolated local testing.

---

## 3. Run the Functions Host Locally

With Azurite running and the virtual environment activated, start the Functions runtime:

```bash
func start
```

You should see the HTTP triggers listening on `http://localhost:7071/api/...`. Each route is defined in `function_app.py`; the `generate` endpoint is an alias of `claim` for backward compatibility.

### VS Code one-click startup + debugging

If you use VS Code, the repository includes a helper script (`tools/start_local_stack.py`) plus debug configuration that automates the local stack:

1. Select **Attach to Local Azure Functions** from the Run & Debug panel and press **F5**.  
2. The pre-launch task will:
  - ensure `.venv` is active for the session,
  - start Azurite (CLI or Docker fallback),
  - launch `func start` with `debugpy` listening on port `5678`, and
  - print the Swagger UI URL (`http://localhost:7071/api/docs`) once the host is ready.
3. VS Code attaches to the waiting debug session once the Functions worker is ready.

You can also invoke the helper manually:

```bash
python tools/start_local_stack.py
```

Stop debugging (or press `Ctrl+C` in the terminal) to tear everything down.

#### What the bootstrap script starts and where it writes

| Component | How it runs | Ports | Files & directories | Notes |
| --- | --- | --- | --- | --- |
| Azurite (storage emulator) | `azurite` CLI if available, otherwise `docker run mcr.microsoft.com/azure-storage/azurite` | `10000` (Blob), `10001` (Queue), `10002` (Table) | `./.azurite/` for persistent data and `./.azurite/debug.log` for CLI debug output | Removed when the Azurite process stops; Docker mode runs ephemeral containers with `--rm`. |
| Azure Functions host | `func start --verbose` | `7071` HTTP listener | none | Spawns the Python worker and gRPC channels under the hood. |
| Python worker + debugger | `debugpy` adapter spawned by Core Tools | `5678` | none | Allows VS Code to attach. Terminates automatically when the worker exits. |
| Swagger URL hint | Printed to terminal | n/a | none | Copy/paste `http://localhost:7071/api/docs` into your browser when ready. |

The script traps `SIGINT`/`SIGTERM` and calls `terminate_all()` on every process it launches, ensuring those ports close cleanly when you stop the session. If the Terminal is force-closed, you can manually clear any leftover processes with:

```bash
pkill -f "mcr.microsoft.com/azure-storage/azurite"
pkill -f "azure-functions-core-tools"
pkill -f "debugpy/adapter"
```

To verify the stack is completely shut down, check that ports `5678`, `7071`, and `10000-10002` no longer appear in the listener list:

```bash
ss -ltnp | egrep ':(5678|7071|1000[0-2])'
```

An empty result (exit code `1`) confirms the environment is idle.

---

## 4. Request an Azure access token

When the bypass is disabled you must present a bearer token that includes one of the custom roles:

* **Sanmar Naming Reader** — read-only access (view docs, audit your own records).
* **Sanmar Naming Contributor** — create/release names and query audits.
* **Sanmar Naming Admin** — elevated operations such as bulk audits and slug synchronization.

Assign yourself to the appropriate app role in Entra ID, then request a token. If you're using the Azure CLI, the following command requests a token for the registered application (replace the placeholders with your actual values):

```bash
az account get-access-token \
  --resource api://<AZURE_CLIENT_ID> \
  --query accessToken -o tsv
```

You can then export it for curl/Postman:

```bash
export ACCESS_TOKEN="$(az account get-access-token --resource api://<AZURE_CLIENT_ID> --query accessToken -o tsv)"
```

Include this token in the `Authorization` header as `Bearer $ACCESS_TOKEN` when calling the API.

### Token helper script

To streamline local testing, a helper utility is available:

```bash
python tools/get_access_token.py --show-claims
```

By default it looks for `AZURE_CLIENT_ID` and requests `api://<client-id>` access. The raw token is printed for copy/paste, along with key claims when `--show-claims` is supplied. Additional options:

* `--client-id <id>` — override the application ID.
* `--resource <resource>` — request a specific resource instead of the default.
* `--scope <scope>` — request an OAuth scope (e.g., `api://<client-id>/.default`).

The script wraps `az account get-access-token`, so make sure you are logged in with `az login` first.

## 5. Explore the API with Swagger UI

When the Functions host is running you can browse fully generated OpenAPI documentation at:

* Swagger UI: <http://localhost:7071/api/docs>
* Raw spec: <http://localhost:7071/api/openapi.json>

The Swagger page lists every HTTP trigger with schemas, sample payloads, and status codes. Select an operation and choose **Try it out** to execute a request directly from the browser. Because the route is anonymous locally, you do not need a function key or bearer token while the bypass variables are enabled.

> ℹ️ In hosted environments you can restrict access to the documentation by removing or changing the anonymous auth level for the `/docs` and `/openapi.json` routes.

## 6. Test with Postman (or curl)

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

## 7. Running Automated Tests

While the Functions host is running, you can still execute the Python unit tests in another terminal:

```bash
pytest
```

---

## 8. Cleaning Up

* Stop the Functions host with `Ctrl+C`.
* Stop Azurite (or the Docker container) when you are done.
* Deactivate the Python virtual environment with `deactivate`.

---

### Troubleshooting

| Symptom | Fix |
| ------- | --- |
| `403 Forbidden` responses while bypass is enabled | Ensure `LOCAL_BYPASS_ROLES` includes the role required by the endpoint (e.g., `admin` for cross-user bulk audit). |
| Functions host cannot connect to storage | Confirm Azurite is running and `AzureWebJobsStorage` is set to `UseDevelopmentStorage=true`. |
| Still prompted for bearer token | Check that `ALLOW_LOCAL_AUTH_BYPASS` is `true` in the environment where the host is running. |

Happy testing! 🚀
