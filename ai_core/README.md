# Mastery AI Core

`ai_core` is the orchestration service for tutoring, quiz intelligence, and graph-backed lesson guidance.
It exposes HTTP endpoints consumed by the backend.

## Responsibilities

- Tutor response generation (chat, hint, explain-mistake)
- Tutor session bootstrap and guided tutor modes
- Tutor checkpoint generation/evaluation
- Quiz generation and quiz insights
- Safety checks (basic moderation and prompt-injection hygiene)
- Retrieval orchestration hooks (with backend/internal retrieval integration)
- Graph- and lesson-aware context aggregation from backend internal adapters

## Service Endpoints

- `GET /` -> service status
- `GET /health` -> configuration health checks
- `POST /tutor/session/bootstrap`
- `POST /tutor/chat`
- `POST /tutor/chat/stream`
- `POST /tutor/recap`
- `POST /tutor/drill`
- `POST /tutor/prereq-bridge`
- `POST /tutor/study-plan`
- `POST /tutor/assessment/start`
- `POST /tutor/assessment/submit`
- `POST /tutor/hint`
- `POST /tutor/explain-mistake`
- `POST /quiz/generate`
- `GET /quiz/{quiz_id}/attempt/{attempt_id}/insights`

## Environment

Create `ai_core/.env` from `ai_core/.env.example`.

Minimum local configuration:

```env
PORT=10001
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174

LLM_PROVIDER=groq
LLM_MODEL=openai/gpt-oss-20b
GROQ_API_KEY=<your-groq-key>

POSTGRES_DSN=postgresql://postgres:postgres@127.0.0.1:55432/mastery_ai
QDRANT_URL=http://127.0.0.1:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=MasteryAI

NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=olayiwola

REDIS_URL=redis://127.0.0.1:6379/0

INTERNAL_SERVICE_KEY=replace_with_shared_secret
BACKEND_INTERNAL_POSTGRES_URL=http://127.0.0.1:8001/api/v1/internal/postgres
BACKEND_INTERNAL_GRAPH_CONTEXT_URL=http://127.0.0.1:8001/api/v1/internal/graph/context
BACKEND_INTERNAL_RAG_URL=http://127.0.0.1:8001/api/v1/internal/rag/retrieve
```

Notes:

- `POSTGRES_DSN` is preferred.
- If `POSTGRES_DSN` is missing, service can fall back to `DATABASE_URL`.
- `INTERNAL_SERVICE_KEY` must match the backend value exactly.
- `BACKEND_INTERNAL_POSTGRES_URL`, `BACKEND_INTERNAL_GRAPH_CONTEXT_URL`, and `BACKEND_INTERNAL_RAG_URL`
  should point to the backend internal adapters.
- Tutor and quiz orchestration now prefer structured lesson context from backend/Postgres first,
  then use graph context and RAG as supporting evidence.

## Installation

From repository root:

```bash
python -m venv .venv
```

Activate environment, then:

```bash
python -m pip install --upgrade pip
python -m pip install -r ai_core/requirements.txt
```

## Local Docker Infra

From repository root:

```powershell
docker compose up -d postgres redis neo4j qdrant
```

That matches the verified local ai-core layout:

- Postgres: `127.0.0.1:55432`
- Redis: `127.0.0.1:6379`
- Neo4j: `127.0.0.1:7687`
- Qdrant: `http://127.0.0.1:6333`
- Backend internal adapters: `http://127.0.0.1:8001/api/v1/internal/*`

## Run

From repository root:

```bash
python -m uvicorn ai_core.main:app --reload --port 10001
```

Health check:

- `http://127.0.0.1:10001/health`

The ai-core health payload now includes:

- `checks.*` configuration readiness
- `runtime.telemetry`

`runtime.telemetry.events` exposes rolling timing snapshots for ai-core graph-first work such as:

- `quiz.generate`
- `tutor.mode`
- `tutor.assessment.start`
- `tutor.assessment.submit`

## Backend Integration

Backend should point to ai-core with:

```env
AI_CORE_BASE_URL=http://127.0.0.1:10001
```

AI-core must point back to backend internal adapters with the shared internal service key:

```env
INTERNAL_SERVICE_KEY=replace_with_shared_secret
BACKEND_INTERNAL_POSTGRES_URL=http://127.0.0.1:8001/api/v1/internal/postgres
BACKEND_INTERNAL_GRAPH_CONTEXT_URL=http://127.0.0.1:8001/api/v1/internal/graph/context
BACKEND_INTERNAL_RAG_URL=http://127.0.0.1:8001/api/v1/internal/rag/retrieve
```

## Production Guidance

- Use strict CORS allowlist.
- Keep API keys in deployment secret manager.
- Keep the same `INTERNAL_SERVICE_KEY` on backend and ai-core.
- Pin model names explicitly per environment.
- Monitor `/health` plus backend `/api/v1/system/health` for cross-service issues.
