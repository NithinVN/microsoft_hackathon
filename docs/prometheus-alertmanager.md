# Prometheus and Alertmanager

IncidentMind accepts Alertmanager webhook notifications at:

```text
POST /api/v1/webhooks/alertmanager
```

A firing notification is normalized to the existing `Incident` and `Alert` records and enters the same shared intake path used by manual incident simulations. A resolved notification with the same Alertmanager fingerprint marks the associated incident resolved. Repeated firing notifications are idempotent while the alert remains active.

## Local setup

Start the application and optional monitoring services from the repository root:

```powershell
docker compose --profile monitoring up --build -d
```

Open Prometheus at `http://localhost:9090` and Alertmanager at `http://localhost:9093`. The sample Alertmanager receiver posts to the Compose backend service at `http://backend:8000/api/v1/webhooks/alertmanager`.

To run Prometheus and Alertmanager in containers while running FastAPI directly on the host, update the receiver URL in `monitoring/alertmanager/alertmanager.yml` to:

```text
http://host.docker.internal:8000/api/v1/webhooks/alertmanager
```

Then start the local backend using the repository's normal Uvicorn command and start the monitoring profile. Do not expose the webhook publicly without network restrictions or an authentication layer; the sample receiver assumes a trusted local Docker network.

## Demo alert rules

`monitoring/prometheus/alert_rules.yml` defines:

- `HighApiErrorRate`: 5xx response ratio above 5% for five minutes.
- `HighApiLatency`: API p95 request duration above one second for five minutes.
- `DatabaseConnectionSaturation`: PostgreSQL active connections above 90% of `max_connections` for three minutes.

The rules expect application metrics `http_requests_total{service,status}` and `http_request_duration_seconds_bucket{service,...}`, plus postgres_exporter metrics `pg_stat_activity_count` and `pg_settings_max_connections`. Prometheus must be configured to scrape the actual instrumented application and database exporter. This repository does not currently expose those metrics or bundle exporters, so the rules load but will not fire until real metric targets are added. The sample Prometheus config includes commented target examples; it intentionally does not report invented metrics.

Alert labels should include `service` (or `application`, `app`, or `job`) and `severity`. Useful annotations include `summary`, `description`, and `runbook_url`. Alertmanager supplies `startsAt`, `endsAt`, `generatorURL`, and a stable fingerprint. Configure `send_resolved: true` so IncidentMind receives resolution notifications.

## Test the webhook

Use the checked-in Alertmanager samples to exercise creation and resolution through FastAPI:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/webhooks/alertmanager -ContentType 'application/json' -InFile tests/fixtures/alertmanager_firing.json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/api/v1/webhooks/alertmanager -ContentType 'application/json' -InFile tests/fixtures/alertmanager_resolved.json
```

The response reports per-alert outcomes (`created`, `resolved`, `already_firing`, `already_resolved`, or `unmatched_resolved`). Invalid payload structure is rejected with HTTP 422. An unmatched resolved notification is retained as an alert audit record but does not create an incident.
