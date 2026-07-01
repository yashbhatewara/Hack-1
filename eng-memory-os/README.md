# Engineering Memory OS

> The permanent, queryable, and reasoning brain of your software organization.

An AI-powered engineering knowledge platform that understands code changes, architectural decisions, incidents, and historical context. Built with **Domain-Driven Design**, **Clean Architecture**, and **Event-Driven Architecture**.

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI + Python 3.12 | REST API, WebSocket streaming |
| **Knowledge Graph** | Cognee 1.0 | Entity extraction, relationship mapping |
| **Agent System** | LangGraph | Multi-agent reasoning with verification loops |
| **Vector DB** | Qdrant | Semantic similarity search |
| **Relational DB** | PostgreSQL 16 | Metadata, users, audit logs |
| **Frontend** | Next.js 14 + React Flow | Chat, graph visualization, evidence viewer |
| **Observability** | OpenTelemetry | Distributed tracing, metrics |

## Quick Start

### Prerequisites
- Docker Desktop
- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Node.js 20+

### One-Command Launch
```bash
docker-compose up --build
```

This starts PostgreSQL, Qdrant, the Backend API, and the Frontend UI.

### Local Development

**Backend:**
```bash
cd backend
uv sync
uv run uvicorn eng_memory_os.cmd.api_server:create_app --factory --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

## Project Structure

```
eng-memory-os/
├── backend/                  # Python FastAPI backend
│   └── src/eng_memory_os/
│       ├── cmd/              # Entry points (API server, workers)
│       ├── domain/           # Pure Python domain layer (DDD)
│       │   ├── shared/       # Base events, types, errors
│       │   ├── memory/       # Memory bounded context
│       │   ├── knowledge/    # Knowledge graph bounded context
│       │   ├── agent/        # Agent reasoning bounded context
│       │   ├── gateway/      # LLM gateway bounded context
│       │   └── integration/  # External integration interfaces
│       ├── application/      # Use cases & event handlers
│       ├── infrastructure/   # Concrete adapters (DB, Cognee, LLM)
│       └── presentation/     # REST/WebSocket API layer
├── frontend/                 # Next.js 14 frontend
├── deploy/                   # Docker, K8s configs
├── docs/                     # Architecture & API docs
└── tests/                    # Unit, integration, E2E tests
```

## Bounded Contexts

1. **Memory Context** — Lifecycle management of incoming unstructured data
2. **Knowledge Context** — Entity extraction, relationship mapping, graph persistence (Cognee)
3. **Agent Context** — Multi-agent reasoning, retrieval, and critique workflows (LangGraph)
4. **Integration Context** — Adapters for GitHub, Jira, Slack, Notion
5. **Gateway Context** — LLM routing, provider fallback, token/cost management

## License

MIT
