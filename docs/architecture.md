# IncidentMind Architecture & Foundation Specification

## Overview

**IncidentMind** is an AI-powered Incident Response Agent with organizational memory powered by **Hindsight Cloud**.

Unlike traditional diagnosis bots that treat each outage as an isolated incident, IncidentMind learns continuously from past incidents, failed and successful remediation attempts, engineer feedback, and postmortems to improve future incident response.

---

## Architectural Principles

1. **Organizational Memory vs. Storage**:
   - **Hindsight Cloud**: Serves as the organizational experience layer (`retain`, `recall`, `reflect`). It stores institutional memories, failed-fix lessons, and postmortem reflections.
   - **PostgreSQL**: Serves strictly as application relational store (incident records, telemetry events, user audit logs). It is **not** a replacement for Hindsight.
2. **External Knowledge vs. Experience**:
   - **RAG**: Used for external/reference knowledge (static runbooks, architecture docs, SOPs).
   - **Hindsight**: Used for organizational experience and past incident trajectory.
3. **No Arbitrary Execution**:
   - Strict remediation guardrails: No arbitrary shell commands or LLM-generated raw SQL execution.
   - Remediation strictly requires explicit **Human Approval**.
4. **Observable State**:
   - All agent steps, memory recalls, and what-if evaluations are surfaced cleanly in the UI.

---

## System Directory Layout

```
/frontend    - React 18, TypeScript, Vite SPA
/backend     - FastAPI, Pydantic, Uvicorn, structured logging
/data        - Local runbooks, simulated incidents, and mock telemetry
/scripts     - Operational and setup automation scripts
/docs        - Architecture, API specifications, and design documents
/tests       - Backend unit and integration test suite
```

---

## Primary Agent Ecosystem (Upcoming Phases)

1. **Incident Orchestrator**: Coordinates incident lifecycle, manages LangGraph state, and interfaces with the UI.
2. **Investigation Agent**: Collects evidence, traces metrics, and correlates system signals.
3. **Blast Radius Agent**: Analyzes service dependency graphs, identifying affected downstream services and user impact.
4. **Memory Agent**: Interfaces directly with Hindsight Cloud (`recall`, `retain`, `reflect`), retrieving relevant prior incidents and warning against failed fixes.
5. **Diagnosis Agent**: Synthesizes current evidence with Hindsight memories to determine root causes.
6. **Remediation Agent**: Proposes safe, vetted remediation actions, runs what-if analysis against past incident outcomes, and waits for human approval before execution.

---

## API Standards

- API Prefix: `/api/v1`
- Centralized configuration via `backend/app/core/config.py` using `pydantic-settings`
- Structured logging format with timestamp, level, module, and message
- Configurable LLM through environment variable `GROQ_MODEL` (default: `openai/gpt-oss-120b`)
