# IncidentMind

IncidentMind is an incident-response prototype for investigating alerts, organizing evidence, comparing remediation options with historical context, and recording post-incident learning. It combines a FastAPI backend, a React dashboard, PostgreSQL application state, local runbook retrieval, and an optional Hindsight Cloud memory adapter.

> **Status:** This is a prototype/demo, not an autonomous production remediation system. Agent reasoning currently uses deterministic Python logic; a Groq client is not implemented. Remediation tools simulate outcomes and do not execute production commands. Demo Mode and the A/B comparison include deterministic frontend fixtures.

## 1. Project overview

IncidentMind provides an incident workflow, a dashboard, bounded remediation simulation, webhook intake, and optional organizational-memory operations. The backend API is the main application surface. The frontend also contains a client-side scripted demo for presentations.

## 2. Problem statement

Responders must correlate monitoring signals, logs, deployments, dependencies, runbooks, and previous incident outcomes under time pressure. Lessons about ineffective fixes and successful recovery often remain in postmortems or individual experience. IncidentMind explores making that organizational context available during future investigations while keeping current evidence and human decisions visible.

## 3. Why incident response needs persistent memory

Current telemetry describes what is happening now. Runbooks describe operational guidance. Neither necessarily captures what this organization learned: which fixes worked, which failed, why an engineer rejected a proposal, and what the postmortem recommended. Persistent memory can make those records retrievable during later incidents. It is supporting evidence, not a replacement for current telemetry or operator judgment.

## 4. Architecture

    Alertmanager / Azure webhook / backend simulator / incident API
                              |
                              v
                    FastAPI intake and API
                              |
              +---------------+----------------+
              v                                v
        PostgreSQL                       Agent workflow
    application state              investigation / blast radius /
    alerts / incidents              memory / diagnosis / remediation
                                               |
                                  +------------+------------+
                                  v                         v
                            Local runbooks             Hindsight Cloud
                     external operational docs      organizational memory

Data boundaries:

- **PostgreSQL = application state.** It stores incident, alert, event, investigation, diagnosis, remediation, approval, feedback, and postmortem records. It is not the organizational-memory service.
- **RAG = external operational knowledge.** The current implementation reads Markdown runbooks from the repository and ranks sections using lexical term overlap. It is not a vector or embedding-based search system.
- **Hindsight = organizational memory.** When configured and reachable, the Hindsight SDK provides persistent memory operations for incident records, remediation outcomes, feedback, and lessons.
- **Groq = intended LLM/reasoning provider.** Groq settings exist, but the backend does not currently call Groq. Agent reasoning is deterministic Python code; LLM generation and function calling are not implemented.

The application calls SQLAlchemy create_all at startup. Alembic migrations exist but startup does not apply them. For migration-managed databases, apply revisions explicitly before starting the app.

## 5. Agent responsibilities

Agents are Python modules with structured inputs/outputs, not separate services or autonomous LLM agents.

| Agent | Responsibility |
|---|---|
| Investigation | Collects incident context, metrics/log evidence, deployment information, and candidate causes through registered tools. |
| Blast radius | Estimates affected services from service and dependency context. |
| Incident memory | Retrieves similar incidents, successful/failed fixes, and lessons; can request a Hindsight reflection. Local historical JSON is also a fallback. |
| Diagnosis | Ranks candidate causes against current evidence, memory evidence, and runbook results. |
| Remediation | Produces bounded candidate actions and rationale. |
| Incident Time Machine | Compares candidate action identifiers with local historical actions and, when needed, Hindsight remediation memories. |
| Orchestrator | Runs the in-process workflow, contains subsystem failures, pauses for approval, and records simulation/postmortem results. |

Workflow checkpoints are not durably persisted; orchestration is not a distributed job system.

## 6. Hindsight integration

The optional memory adapter uses the hindsight-client SDK and the configured memory bank. Set HINDSIGHT_API_KEY and the endpoint/bank settings to enable remote calls. A configured URL alone does not prove availability; check the Hindsight diagnostic endpoint at /api/v1/health/hindsight.

### 7. Hindsight retain, recall, reflect

- **retain:** Store incident/root-cause context, remediation outcomes, engineer feedback, and postmortem lessons. Postmortem storage marks retention complete only after requested retain operations report success. Failures leave the postmortem available and are logged.
- **recall:** During memory assessment, request similar incidents and successful/failed remediation records for the service and incident symptoms. Time Machine can request historical remediation evidence too.
- **reflect:** During incident-memory assessment, request a synthesis of patterns across memories. A reflective summary is included as evidence when Hindsight supplies supporting memory references.

Memory operations are best-effort and must not erase PostgreSQL state. If recall yields no records, the memory agent may use local historical JSON. Therefore empty/unavailable Hindsight and local fixture evidence must not be presented as the same provenance. Frontend demo memories are fixtures, not proof of live Hindsight retrieval.

## 8. PostgreSQL role

PostgreSQL stores relational application records and is the intended durable state store. The development URL uses PostgreSQL via asyncpg. The backend can start in degraded mode when the database is unavailable, but database-backed operations require a reachable database.

## 9. RAG role

The runbook loader reads Markdown files from data/runbooks, splits documents into sections, and scores lexical query-term overlap. It provides external operational guidance to investigation/diagnosis; it does not store incident outcomes. The RAG_DATA_DIR setting exists but the current loader uses the repository data/runbooks path instead.

## 10. Groq role

Groq is configured as the intended language-model provider. GROQ_API_KEY, GROQ_MODEL, GROQ_TEMPERATURE, and GROQ_MAX_RETRIES are settings only: there is no Groq client invocation or model-generated function calling in the current backend. Do not interpret dashboard labels or health settings as evidence of active LLM reasoning.

## 11. Incident Simulator

The backend exposes GET /api/v1/simulate/scenarios and POST /api/v1/simulate. It creates seeded scenario data and persists it through the simulator/intake path. It does not automatically launch the complete orchestrator workflow.

The frontend Demo Mode is separate: it is a deterministic, client-side payment incident presentation with scripted steps, fixture metrics/memories, an approval gate, and simulated recovery. It does not need Azure or PagerDuty, but it does not demonstrate live monitoring or live Hindsight recall. If configured, the UI can separately request best-effort retention of its outcome. Demo values are illustrative, not live measurements.

## 12. Prometheus integration

The Alertmanager adapter at POST /api/v1/webhooks/alertmanager normalizes notifications into incident/alert records. Sample Prometheus and Alertmanager configuration is in monitoring; details are in [docs/prometheus-alertmanager.md](docs/prometheus-alertmanager.md).

The repository does not expose the application metrics or bundle the PostgreSQL exporter required by its sample alert rules. The rules can load, but will not fire until real scrape targets are instrumented and configured. Webhook intake exists; an end-to-end monitoring pipeline does not.

## 13. Azure Monitor integration

POST /api/v1/webhooks/azure-monitor accepts supported Azure Monitor webhook payloads, including Common Alert Schema/classic forms, and normalizes them into incident intake records. A shared secret can protect this endpoint. AZURE_AUTO_ORCHESTRATE defaults to false.

This is webhook ingestion, not an Azure SDK/control-plane integration: the app does not query Azure resources, metrics, or deployments directly. See [docs/azure-monitor.md](docs/azure-monitor.md). External Azure delivery has not been verified as part of this documentation.

## 14. Human approval model

The orchestrator blocks before remediation unless approval is explicit; approval for an action that does not match the current plan is rejected. The tool layer requires dry_run=true and does not execute arbitrary shell or SQL commands. A successful simulator prediction is labeled simulation_passed, not production telemetry verification. The incident approval API records a decision; it does not itself run a production remediation.

Operator-token checks protect selected approval/execution-record endpoints outside development/test. They do not authenticate the entire API.

## 15. Incident Time Machine

Time Machine compares candidate actions with historical outcomes. It searches local historical incident data first and requests Hindsight evidence when local matching finds no cases, so live Hindsight is not guaranteed for every comparison. Matches use normalized action identifiers. Outcomes are contextual evidence, not guarantees; confidence values are heuristic, not calibrated probabilities.

## 16. Learning loop

    incident and evidence -> diagnosis and candidate actions -> human decision
       -> simulated/recorded outcome -> postmortem and feedback
       -> Hindsight retain -> recall/reflection in a future investigation

Postmortem storage can retain incident context, root cause, recorded action outcomes, engineer feedback, and lessons when Hindsight is enabled. The retained flag reflects successful retain responses. Workflow checkpoints and retries are not a durable automatic learning pipeline.

## 17. Installation

Prerequisites: Python 3.11+, Node.js/npm for the frontend, PostgreSQL (or Docker for a local database), and optional Hindsight Cloud credentials.

From the repository root, copy the environment template:

    # PowerShell
    Copy-Item .env.example .env

    # macOS/Linux
    cp .env.example .env

Change the database credentials for your environment. Keep .env out of version control.

## 18. Environment variables

| Variable | Purpose | Current behavior/default |
|---|---|---|
| APP_NAME, APP_ENV, DEBUG | App identity/environment | IncidentMind, development, True |
| API_V1_PREFIX, HOST, PORT, LOG_LEVEL | API server settings | /api/v1, 0.0.0.0, 8000, INFO |
| ALLOWED_ORIGINS | Comma-separated CORS origins | Local frontend origins |
| DATABASE_URL | PostgreSQL async SQLAlchemy URL | Local incidentmind_db |
| POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB, POSTGRES_PORT | Compose database settings | Development values; Compose requires a password |
| HINDSIGHT_BASE_URL / HINDSIGHT_API_URL | Hindsight endpoint | https://api.hindsight.cloud |
| HINDSIGHT_API_KEY | Hindsight credentials | Empty; valid key required for remote calls |
| HINDSIGHT_BANK_ID, HINDSIGHT_WORKSPACE_ID | Hindsight identifiers | incidentmind-memory, incidentmind-org |
| HINDSIGHT_TIMEOUT_SECONDS, HINDSIGHT_MAX_RETRIES | Hindsight request policy | 10 seconds, 3 attempts |
| GROQ_API_KEY, GROQ_MODEL, GROQ_TEMPERATURE, GROQ_MAX_RETRIES | Reserved Groq configuration | Configured, but no Groq client is implemented |
| RAG_DATA_DIR | Intended runbook path | Not honored; loader reads data/runbooks |
| SIMULATOR_DETERMINISTIC | Simulator configuration | True |
| AZURE_WEBHOOK_SECRET | Azure webhook shared secret | Empty; required outside development/test |
| AZURE_DEFAULT_SERVICE | Azure fallback service name | azure-service |
| AZURE_AUTO_ORCHESTRATE | Opt-in Azure orchestration | False |
| ALERTMANAGER_WEBHOOK_SECRET | Alertmanager webhook shared secret | Empty; required outside development/test |
| OPERATOR_API_TOKEN | Bearer token for selected operator endpoints | Empty; configure outside development/test |
| WEBHOOK_ORCHESTRATION_TIMEOUT_SECONDS | Azure orchestration timeout | 15 seconds |

Settings load from environment variables and .env in the process working directory. Production validation requires DEBUG=False, a non-default PostgreSQL password, and a non-development database URL.

## 19. Running locally

Start PostgreSQL. For example, use the Compose database service:

    docker compose up -d postgres

Create and install the backend environment, then start the API from the repository root:

    # Windows PowerShell
    py -3.12 -m venv backend/.venv
    backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
    backend/.venv/Scripts/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

    # macOS/Linux equivalents
    python3 -m venv backend/.venv
    backend/.venv/bin/python -m pip install -r backend/requirements.txt
    backend/.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload

In a second terminal:

    cd frontend
    npm install
    npm run dev

Dashboard: http://localhost:5173. API docs: http://localhost:8000/docs. Liveness: /api/v1/health/live. Database readiness: /api/v1/health/ready. Hindsight diagnostic: /api/v1/health/hindsight.

For a migration-managed database, run python -m alembic upgrade head from the repository root before application startup. The create_all startup hook does not apply Alembic revisions. The Docker deployment path has not been validated as a migration-managed deployment.

## 20. Running tests

After installing backend requirements, run from the repository root:

    # Windows
    backend/.venv/Scripts/python -m pytest -q

    # macOS/Linux
    backend/.venv/bin/python -m pytest -q

The backend suite uses SQLite fixtures and mocks for many external services. A passing suite does not establish live Hindsight, Azure, Groq, or Prometheus connectivity. The frontend package has build and lint scripts but no configured frontend test script.

## 21. Demo instructions

1. Start the backend and frontend as described above.
2. Open the dashboard and choose Demo Mode.
3. Follow the scripted incident timeline and approve or reject the simulated remediation at the approval gate.
4. View the Hindsight A/B comparison as a seeded illustrative comparison, not a live experiment.
5. If Hindsight credentials are configured, the demo outcome can be submitted for best-effort retention; check the response/status rather than assuming retention succeeded.

The backend simulator can also be exercised through the scenarios endpoint and POST simulate API. Its records are separate from the client-side Demo Mode and do not automatically run full orchestration.

## 22. Security considerations

- Store database credentials, Hindsight keys, and webhook/operator tokens in a protected environment or secret manager; never commit .env.
- Configure webhook secrets and OPERATOR_API_TOKEN outside development/test. Those environments intentionally relax authentication checks.
- General API authentication, tenant isolation, request-size limits, and rate limiting are not implemented for all routes. Use an authenticated gateway and network controls before exposure.
- Treat webhook payloads, runbooks, historical fixtures, and retrieved memories as untrusted. Verify evidence before approving an action.
- A simulated approval or predicted recovery is not a production action or service verification.
- Review redaction and retention requirements before sending logs or engineer feedback to an external memory service.

## 23. Limitations

- Groq configuration exists without an implemented LLM request/function-calling path.
- Demo/A-B content includes hard-coded fixtures and is not a live comparison.
- Hindsight is optional/best-effort; local historical JSON may be used when recall returns no records.
- RAG is lexical Markdown retrieval; RAG_DATA_DIR is currently unused.
- Time Machine searches local history first and consults Hindsight conditionally; its confidence is heuristic.
- Some tool lookups still rely on process-local registrations/static history, so restart and multi-worker behavior is not fully reliable.
- Prometheus sample rules lack required app/exporter metrics. Azure support is webhook ingestion, not direct Azure API integration. PagerDuty is not implemented.
- Backend simulation persists seeded intake but does not automatically run the complete orchestrator.
- Orchestration checkpoints/retries are not durable; webhook concurrency and timeout cancellation need further hardening.
- Frontend and external integration flows have not all been validated end to end.

## 24. Future improvements

1. Implement and test a real Groq client with schema-validated outputs and bounded tool calls, or remove unused Groq settings.
2. Make PostgreSQL the source of truth for all agent tools; add durable workflow checkpoints and safe retries.
3. Add webhook-level database idempotency and cancellation-safe background jobs.
4. Apply/test Alembic migrations as part of deployment and validate against PostgreSQL.
5. Make Hindsight provenance explicit for live recall, empty results, service errors, and local fallback; add live integration tests.
6. Instrument application/database metrics and validate Prometheus alert delivery end to end.
7. Add general API authentication, request limits, tenant boundaries, and memory redaction/retention controls.
8. Add frontend automated tests and full incident-to-approval-to-learning end-to-end coverage.
