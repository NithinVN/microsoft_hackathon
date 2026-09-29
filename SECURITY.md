# Security Review and Threat Model

## Application Scope

IncidentMind is an incident intake and investigation application. It stores incident descriptions, alert payloads, operational findings, engineer feedback, and remediation records in PostgreSQL; it can send incident context to Hindsight Cloud for organizational-memory recall and retention. Agents are ordinary application code that reads these records and calls a fixed local tool registry. The checked-in backend does not spawn shell processes or execute LLM-generated SQL or commands. Remediation execution is simulation-only.

## Assets and Trust Boundaries

- Incident, alert, telemetry, log, diagnosis, feedback, and postmortem data may contain sensitive operational or customer information.
- Groq, Hindsight, database, and webhook credentials must remain server-side and out of source control, browser bundles, responses, and logs.
- Browser clients and all webhook payloads are untrusted inputs. Alert labels, annotations, Azure custom properties, runbook text, memory results, and engineer-provided fields must be treated as data, not instructions.
- The application crosses boundaries at browser-to-API requests, monitoring-webhook intake, agent-to-tool calls, PostgreSQL queries, and outbound Hindsight requests.

## Implemented Mitigations

- SQL access uses SQLAlchemy expressions and bound parameters; there is no arbitrary-SQL tool or shell-execution API in the backend.
- Registered tools validate inputs with Pydantic, reject unrecognized arguments, constrain service/action identifiers, and bound numeric limits. Tool failures return generic messages and validation responses omit submitted values.
- Remediation simulation rejects `dry_run=false`. The orchestrator now stops at `HUMAN_APPROVAL` unless an explicit approval value is provided; an alert-triggered orchestration run cannot approve itself or mark an action recovered.
- Azure Monitor and Alertmanager webhooks use constant-time shared-secret comparison when configured. They accept open requests only in `development` and `test`; staging/production fail closed with HTTP 503 when the relevant secret is absent. Secrets can be supplied in headers (Azure also retains the `code` query parameter for compatibility).
- Remediation approval and execution-record routes require `OPERATOR_API_TOKEN` as a bearer token outside development/test and fail closed when it is unconfigured. Comparisons are constant-time.
- Credentialed CORS is restricted to configured origins, methods, and headers; wildcard origins are rejected.
- Hindsight queries, provider exception messages, and webhook exception details are not written to application logs or returned as raw provider errors.
- Compose requires an explicit PostgreSQL password. Non-development settings reject the checked-in development password and database URL, and reject debug mode.

## Required Deployment Controls and Known Gaps

**The general REST API has no built-in user authentication or role-based authorization.** Incident reads and writes remain unauthenticated. Approval and execution-record routes have a shared bearer-token gate outside development/test, but the token is not a per-user identity or role system. The `engineer`/`approved_by` fields remain caller-supplied labels, not proof of identity. CORS does not prevent non-browser clients from calling the API.

Do not expose the backend directly to an untrusted network. Before a production deployment, put every non-webhook API route behind an identity-aware gateway (for example, OIDC/SSO), enforce reader/operator/approver roles there, restrict backend network access to that gateway, and ensure the gateway forwards authenticated identity rather than trusting caller-supplied engineer names. Keep webhook routes separately authenticated with unique secrets, rate limits, and source/network restrictions. Do not place a shared API secret in the static frontend bundle.

Additional deployment requirements:

- Set `APP_ENV` to `staging` or `production`, set `DEBUG=False`, use a unique high-entropy PostgreSQL password, and configure `DATABASE_URL` consistently. Keep credentials in a secret manager; percent-encode reserved characters in database URLs.
- Configure separate high-entropy `AZURE_WEBHOOK_SECRET` and `ALERTMANAGER_WEBHOOK_SECRET` values. Prefer headers; if Azure requires a query credential, redact query strings from reverse-proxy and access logs.
- Configure a unique high-entropy `OPERATOR_API_TOKEN` for approval/execution endpoints; do not reuse webhook or database credentials. Treat it as a shared emergency gate only, not a substitute for per-user authorization.
- Terminate TLS at a trusted ingress, restrict outbound access to required database/Hindsight services, and limit request body size/rate at the ingress. The backend does not currently have a global request-size or rate limit.
- Keep `/docs`, `/redoc`, and OpenAPI discovery inaccessible to public unauthenticated clients in production.
- Review retention and redaction for incident payloads before sending them to Hindsight; restrict access to incident and memory data according to operational sensitivity.

## Prompt Injection and Agent Authority

Alert data, logs, runbooks, feedback, and recalled memory can contain adversarial instructions. The current agents do not invoke a general-purpose LLM or convert text into executable commands; the tool registry is an allowlist of bounded application functions. Hindsight is an external memory/synthesis service and its returned text is untrusted evidence. Any future LLM integration must keep retrieved/user text in a data-only context, validate structured outputs against strict schemas, authorize tools independently of the model, and retain the simulation-only restriction. Never pass model-generated command strings to a shell, SQL executor, cloud SDK, or infrastructure API.

## Verification

Run the backend suite from the repository root with `backend/.venv/Scripts/python -m pytest -v` after installing `backend/requirements.txt`. Security regression tests cover fail-closed webhooks, explicit approval, and strict tool argument validation.