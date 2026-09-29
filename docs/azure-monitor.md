# Azure Monitor Webhook Integration

IncidentMind provides a native adapter for Microsoft Azure Monitor alert webhooks at:

```text
POST /api/v1/webhooks/azure-monitor
```

The adapter normalizes incoming Azure Monitor alerts into the shared internal `Incident` and `Alert` schemas, feeding directly into the intake pipeline and **Incident Orchestrator**—the exact same pipeline used by Alertmanager, Prometheus, and the incident simulator.

---

## Architecture Flow

```text
┌───────────────────────┐
│     Azure Monitor     │
│  (Metric / Log Alert) │
└──────────┬────────────┘
           │ HTTP POST (Common Alert Schema)
           ▼
┌───────────────────────────────────────────────┐
│     FastAPI Endpoint                          │
│     POST /api/v1/webhooks/azure-monitor       │
│     ├── Authentication & Secret Validation    │
│     └── Pydantic Schema Validation            │
└──────────┬────────────────────────────────────┘
           │ Normalized IncidentCreate & Alert
           ▼
┌───────────────────────────────────────────────┐
│     Incident Intake Service                   │
│     ├── Relational DB storage (Incident/Alert)│
│     ├── Idempotent deduplication              │
│     └── Runtime tool registration             │
└──────────┬────────────────────────────────────┘
           │ Pipeline Handoff (PIPELINE_INITIALIZED)
           ▼
┌───────────────────────────────────────────────┐
│     Incident Orchestrator                     │
│     ├── Investigation Agent                   │
│     ├── Blast Radius Agent                    │
│     ├── Incident Memory Agent (Hindsight)     │
│     ├── Diagnosis Agent                       │
│     ├── Remediation Agent (What-If Analysis)  │
│     └── Human Approval Gate                   │
└───────────────────────────────────────────────┘
```

---

## Configuration & Environment Variables

Azure Monitor integration is entirely decoupled and **does not introduce a hard dependency on Azure SDKs or proprietary cloud services**. If Azure configuration is omitted, all other application features (manual simulations, Prometheus/Alertmanager intake, Hindsight organizational memory, REST API) continue to operate normally.

Configure optional settings in `.env`:

```bash
# Optional: Shared secret for Azure Action Group authentication
AZURE_WEBHOOK_SECRET=your-secure-webhook-token-here

# Optional: Fallback service name if not present in customProperties/resource IDs
AZURE_DEFAULT_SERVICE=azure-service

# Optional: Automatically execute full agent orchestration synchronously upon alert receipt
AZURE_AUTO_ORCHESTRATE=false
```

---

## Connecting a Real Azure Monitor Action Group

To route production alerts from Microsoft Azure to IncidentMind:

### 1. Create or Open an Action Group in Azure Portal
1. In the Azure Portal, search for and open **Monitor**, then select **Alerts** > **Action groups**.
2. Click **Create** (or edit an existing Action Group).
3. Under the **Basics** tab, select your Subscription, Resource Group, and specify an Action Group Name (e.g., `ag-incidentmind-webhook`).

### 2. Add Webhook Action
1. Go to the **Actions** tab.
2. Under **Action type**, select **Webhook**.
3. In the Webhook configuration pane:
   - **URI**: Enter your public IncidentMind endpoint:
     ```text
     https://incidentmind.yourdomain.com/api/v1/webhooks/azure-monitor?code=YOUR_AZURE_WEBHOOK_SECRET
     ```
     *(If exposing via a dev proxy like ngrok during development: `https://<id>.ngrok-free.app/api/v1/webhooks/azure-monitor?code=YOUR_SECRET`)*
   - **Enable the common alert schema**: Toggle to **Yes** *(Highly Recommended)*.
4. Click **OK**, then click **Review + create**.

### 3. Attach Action Group to Alert Rules
1. In Azure Monitor, create or select any **Metric alert rule** (e.g. CPU > 90%, HTTP 5xx > 5%), **Log search alert rule** (Log Analytics / Kusto query), or **Activity Log alert**.
2. Under the **Actions** section of the alert rule, select the Action Group configured above.
3. Save the alert rule.

> [!IMPORTANT]
> **Live Integration Status Notice**: The Azure Monitor integration adapter implemented here is fully tested against representative Common Alert Schema and classic payloads. However, the connection is **not live** until an operator configures an active Azure Monitor Action Group pointing to a publicly accessible HTTPS URL hosting this service.

---

## Payload Schema & Normalization Mapping

IncidentMind prioritizes the **Azure Monitor Common Alert Schema** (Microsoft's standard across all modern alert types) while also supporting classic metric/log alert schemas.

| Azure Monitor Common Alert Schema Field | IncidentMind Normalized Schema | Description / Normalization Logic |
| :--- | :--- | :--- |
| `data.essentials.originAlertId` or `alertId` | `Alert.alert_id` / `Incident.metadata.fingerprint` | SHA-256 fingerprint for deduplication & state tracking |
| `data.essentials.firedDateTime` | `Incident.detected_at` | UTC ISO-8601 alert onset timestamp |
| `data.essentials.resolvedDateTime` | `Incident.resolved_at` | Updated when `monitorCondition == "Resolved"` |
| `data.essentials.alertRule` | `Incident.title` | Title formatted as `[{service}] {alertRule}: {description}` |
| `data.essentials.description` | `Incident.description` | Detailed human-readable alert context |
| `data.essentials.severity` (`Sev0`–`Sev4`) | `Incident.severity` (`SEV-1`–`SEV-4`) | `Sev0` / `Sev1` $\rightarrow$ `SEV-1`<br>`Sev2` $\rightarrow$ `SEV-2`<br>`Sev3` $\rightarrow$ `SEV-3`<br>`Sev4` $\rightarrow$ `SEV-4` |
| `data.customProperties.service` / ARM resource name | `Incident.affected_service` | Extracted from `customProperties.service`, tags, or target ARM ID |
| `data.alertContext.condition` | `Incident.symptoms` & `telemetry` | Metric threshold values, operator, timeAggregation, and window |
| `data.essentials.monitorCondition` | `Alert.status` & `Incident.status` | `"Fired"` $\rightarrow$ `DETECTED`<br>`"Resolved"` $\rightarrow$ `RESOLVED` |

---

## Authentication & Security Options

When `AZURE_WEBHOOK_SECRET` is configured in `.env`, the endpoint validates each incoming request using constant-time digest comparison (`hmac.compare_digest`). The secret can be supplied via any of the following methods:

1. **Query Parameter (Standard for Azure Action Groups)**:
   ```text
   POST /api/v1/webhooks/azure-monitor?code=YOUR_SECRET
   ```
2. **Custom HTTP Header**:
   ```http
   X-Azure-Webhook-Secret: YOUR_SECRET
   ```
3. **Authorization Header**:
   ```http
   Authorization: Bearer YOUR_SECRET
   ```

If `AZURE_WEBHOOK_SECRET` is left empty in `.env`, the endpoint operates in open development mode without rejecting requests.

---

## Testing the Webhook Locally

You can test the endpoint using the sample payloads included in the repository:

### Test Firing Metric Alert
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/webhooks/azure-monitor" `
  -ContentType "application/json" `
  -InFile "tests/fixtures/azure_monitor_metric_firing.json"
```

### Test Resolved Alert
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/webhooks/azure-monitor" `
  -ContentType "application/json" `
  -InFile "tests/fixtures/azure_monitor_metric_resolved.json"
```

### Test with Secret Validation
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/webhooks/azure-monitor?code=your-secret" `
  -ContentType "application/json" `
  -InFile "tests/fixtures/azure_monitor_log_firing.json"
```

### Test with Agent Orchestration Enabled
```powershell
Invoke-RestMethod -Method Post -Uri "http://localhost:8000/api/v1/webhooks/azure-monitor?orchestrate=true" `
  -ContentType "application/json" `
  -InFile "tests/fixtures/azure_monitor_metric_firing.json"
```
