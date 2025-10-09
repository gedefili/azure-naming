# 💰 Cost Projection: 100,000 Claimed Names Retained for 10 Years

> **Scenario**: Bulk create 100,000 Azure resource names via this Functions app in a single campaign, retain the claim + audit history for ten full years, and keep the supporting Azure resources online the entire time.

The numbers below use publicly listed Azure rates as of **October 2025**. Prices vary slightly by region; the calculations assume **East US 2**, locally redundant storage (LRS), and the Azure Functions **Consumption** plan. Currency is USD.

## 1. Key Assumptions

| Area | Assumption |
| --- | --- |
| Execution profile | Each name creation is one function invocation that runs for **1 second at 256 MB** (0.25 GB) of memory. |
| Workload size | `100,000` create operations in year 1, negligible additional creates afterwards. Releases/audits happen but do not materially change the 10‑year tally. |
| Data model | Each claim produces:<br>• 1 entity in `ClaimedNames` (~1 KB)<br>• 3 audit events over its lifetime (~1.5 KB each) |
| Storage footprint | 1 claim entity (1 KB) + 3 audits (3 × 1.5 KB) ≈ **5.5 KB per name**.<br>`100,000` names ⇒ **550 MB (0.537 GB)** persisted. |
| Storage tier | Azure Table Storage on Standard LRS (`$0.058 / GB-month`). |
| Transactions | 3 table transactions per create (name insert, audit insert, slug touch) ⇒ `300,000` total. |
| Free grants | Azure Functions’ free monthly grants (1 M executions, 400k GB-s) are ignored for conservative budgeting. |
| Other services | No premium networking, Key Vault, Application Insights ingestion, or backups included. |

## 2. One-Time Ingestion Cost (Year 1)

| Service | Calc | Cost |
| --- | --- | ---: |
| **Function executions** | `100,000 ÷ 1,000,000 × $0.20` | $0.02 |
| **Function compute (GB-s)** | `100,000 × 0.25 GB × 1 s × $0.000016` | $0.40 |
| **Table transactions** | `300,000 ÷ 10,000 × $0.00036` | $0.0108 |
| **Total (ingestion)** |  | **$0.43** |

> ⚠️ If the workload stays within one billing month, the consumption-plan free grants would zero-out the Function charges, but the table includes them for contingency budgeting.

## 3. Ongoing Storage Cost (10-Year Horizon)

| Component | Calc | Monthly | 10-Year Total |
| --- | --- | ---: | ---: |
| **Table data (0.537 GB)** | `0.537 × $0.058` | $0.031 | $3.74 |
| **Table transactions (audit lookups, etc.)** | Assume `100,000` read ops/mo ⇒ `100,000 ÷ 10,000 × $0.00036` | $0.0036 | $0.43 |
| **Azure Functions idle** | Consumption plan has no standing charge when idle. | $0.00 | $0.00 |
| **Total (run cost)** |  | **$0.035** | **$4.17** |

> Increase the storage line proportionally if you opt for zone- or geo-redundant storage (ZRS/GRS) or if the audit history is more verbose than assumed.

## 4. Ten-Year Total Cost of Ownership

| Category | 10-Year Cost |
| --- | ---: |
| One-time ingestion | $0.43 |
| Ongoing storage & transactions | $4.17 |
| **Grand Total** | **≈ $4.60** |

## 5. Sensitivity Checks

- **Heavier audit history**: Doubling audit events to six per name raises storage to ~0.8 GB ⇒ $5.57 over the decade.
- **Geo-redundant storage (GRS)**: Roughly 2× the LRS price; storage line becomes ~$7.48.
- **Including Application Insights**: Expect ~$2–$5/month depending on telemetry volume—add separately if you retain logs for compliance.

## 6. Not Included

The estimate deliberately omits costs for:

- Network egress (traffic stays within Azure)
- Azure Key Vault, Managed Identity, or Premium connectors
- Azure Monitor Log Analytics retention beyond default
- Engineering / operations labor

## 7. Recommendation

- Use the storage footprint formula (`names × data-per-name`) to plug in your own audit volume or retention policies.
- Revisit pricing annually; Azure Storage and Functions rates occasionally change, and newer SKUs (e.g., Premium Functions) may alter economics.
- If long-term archival/compliance is required, consider exporting closed records to Azure Archive Storage to reduce the 10-year storage line even further.

> 📎 **TL;DR**: Keeping 100k claimed names plus their audit trail online for a decade on the current Azure stack costs **well under $10** in platform fees, assuming consumption-plan Functions and LRS Table Storage.
