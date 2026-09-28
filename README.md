# IncidentMind

> **AI-Powered Incident Response Agent with Organizational Memory**

IncidentMind is an advanced incident response platform that does not merely diagnose outages—it remembers previous incidents, successful and failed remediation attempts, engineer feedback, and postmortems. Powered by **Hindsight Cloud**, it utilizes accumulated institutional experience to continuously improve incident response.

---

## Key Differentiators

1. **Incident Time Machine**:
   Compares candidate remediation actions against historical incidents and surfaces what happened when those actions were previously attempted.
2. **Failed-Fix Memory**:
   Remembers failed remediation attempts and actively warns engineers not to repeat ineffective actions in similar operational contexts.
3. **Continuous Learning Loop**:
   Incident outcome $\rightarrow$ Postmortem $\rightarrow$ Engineer feedback $\rightarrow$ Hindsight Memory update $\rightarrow$ Smarter future response.
4. **Strict Human-in-the-Loop Safeguards**:
   All remediation actions require explicit human approval. No arbitrary shell commands or raw LLM-generated SQL queries are permitted.

---

## Core Product Loop

```text
Incident
  │
  ▼
Investigation
  │
  ▼
Blast Radius Analysis
  │
  ▼
Historical Memory Retrieval (Hindsight recall)
  │
  ▼
Diagnosis
  │
  ▼
What-If / Historical Remediation Analysis
  │
  ▼
Human Approval (Mandatory Gate)
  │
  ▼
Remediation Execution
  │
  ▼
Verification
  │
  ▼
Postmortem Generation
  │
  ▼
Hindsight Memory Retain (Organizational Learning)
```

---

## Tech Stack

- **Frontend**: React 18, TypeScript, Vite, Lucide Icons
- **Backend**: Python 3.12, FastAPI, Pydantic v2, Uvicorn
- **LLM**: Groq API (default configurable model: `openai/gpt-oss-120b`)
- **Organizational Memory Layer**: Hindsight Cloud (`retain`, `recall`, `reflect`)
- **Application Database**: PostgreSQL (relational state storage; *not* a replacement for Hindsight)
- **Deployment**: Docker & Docker Compose

---

## Repository Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/health.py  # Health and readiness endpoints
│   │   ├── api/v1/router.py            # API v1 router
│   │   ├── core/config.py              # Centralized Pydantic settings
│   │   ├── core/logging.py             # Structured logging setup
│   │   └── main.py                     # FastAPI app with CORS & lifespan
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/client.ts               # Typed API client
│   │   ├── components/HealthStatus.tsx # Subsystem connectivity status
│   │   ├── App.tsx                     # Main dashboard layout
│   │   └── main.tsx                    # React DOM entry
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── data/                               # Data directory for runbooks and scenarios
├── scripts/
│   └── start-dev.ps1                   # Development startup automation
├── docs/
│   └── architecture.md                 # Architecture documentation
├── tests/
│   ├── conftest.py                     # Test fixtures (TestClient)
│   └── test_health.py                  # API & CORS unit tests
├── docker-compose.yml                  # Multi-container orchestration
├── .env.example                        # Environment variable template
└── README.md
```

---

## Getting Started Locally

### 1. Prerequisites
- Python 3.12+
- Node.js 20+ (Node 24 supported)
- npm 10+
- Docker (optional for local containerized deployment)

### 2. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Update with your Groq and Hindsight API keys as needed.

### 3. Backend Setup
```bash
# In repository root
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/pip install -r backend/requirements.txt

# Run backend tests
backend/.venv/Scripts/python -m pytest -v

# Run backend server
backend/.venv/Scripts/uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Docs available at: `http://localhost:8000/docs`

### 4. Frontend Setup
```bash
cd frontend
npm install
npm run build
npm run dev
```
Frontend available at: `http://localhost:5173`

### 5. Docker Compose (Alternative)
```bash
docker compose up --build
```
