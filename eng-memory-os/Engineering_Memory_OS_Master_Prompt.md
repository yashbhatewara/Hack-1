<!-- markdownlint-disable MD013 -->

# Engineering Memory OS — The Ultimate Architectural Master Prompt

> **SYSTEM DIRECTIVE [CRITICAL]**
> You are not generating a prototype, a tutorial, or boilerplate. You are operating as the entire Principal Engineering Team (Architect, Backend, AI, Frontend, DevOps, Security, QA) to build a production-grade, open-source **Engineering Knowledge Operating System**.
>
> This document is your absolute, unalterable Engineering Constitution. You MUST read, internalize, and strictly adhere to every section. Do NOT skip phases. Do NOT leave `// TODO` or `pass` placeholders. Do NOT mock data. Think deeply before writing, self-correct, and implement completely.

---

## SECTION 1: ENGINEERING CONSTITUTION & PHILOSOPHY

### 1.1 The Identity

You are building an AI-powered engineering memory platform that acts as the permanent, queryable, and reasoning brain of a software organization. It understands code changes, architectural decisions, incidents, and historical context.

### 1.2 Absolute Directives

1. **Zero Placeholders:** Every function must be fully implemented.
2. **Domain-Driven Design (DDD):** Organize code by business domain, never by technical concern.
3. **Clean Architecture:** Dependencies point strictly inward. Presentation -> Application -> Domain <- Infrastructure.
4. **Event-Driven Architecture (EDA):** Domains communicate via asynchronous events (Pub/Sub pattern).
5. **No Framework Coupling:** Business logic must remain entirely agnostic of external frameworks or LLM providers.
6. **Anti-Hallucination:** If the system does not have the evidence, it MUST explicitly state so.

### 1.3 Autonomous Planning Framework (Mandatory Preamble)

Before generating ANY code, internally process this execution loop:
`Decompose Product -> Define Bounded Contexts -> Design Data Model -> Map Event Flow -> Design Agent Graph -> Assess Security -> Plan Deployment -> Execute Code`

---

## SECTION 2: CORE ARCHITECTURE & BOUNDED CONTEXTS

Implement a strict modular monolith or microservices repository structure using the following Bounded Contexts:

1. **Memory Context:** Manages the lifecycle of incoming unstructured data.
2. **Knowledge Context (Cognee):** Manages entity extraction, relationship mapping, and Graph persistence.
3. **Agent Context (LangGraph):** Orchestrates the multi-agent reasoning, retrieval, and critique workflows.
4. **Integration Context:** Adapters for GitHub, Jira, Slack, Notion, etc.
5. **Gateway Context:** LLM routing, provider fallback, and token/cost management.

**File Structure Blueprint:**

```text
/eng-memory-os
├── /docs                 # Architecture, API, and Deployment docs
├── /frontend             # Next.js 14, Tailwind, React Flow (for graph viz)
├── /backend
│   ├── /cmd              # Entry points (API server, Worker processes)
│   ├── /internal
│   │   ├── /domain       # Enterprise logic, Entities, Value Objects, Interfaces
│   │   ├── /application  # Use cases, Application services, Event Handlers
│   │   ├── /infrastructure
│   │   │   ├── /cognee   # Cognee graph memory integration
│   │   │   ├── /langgraph# LangGraph agent definitions
│   │   │   ├── /llm      # LLM Gateway (OpenAI, Anthropic, Local Fallback)
│   │   │   └── /db       # Vector DB (Qdrant/Milvus) & Relational DB (Postgres)
│   │   └── /presentation # REST/GraphQL APIs, WebSocket controllers
├── /deploy               # Docker, K8s, Terraform, CI/CD
└── /tests                # E2E, Integration, Unit
```

---

## SECTION 3: THE MEMORY LIFECYCLE & COGNEE ARCHITECTURE

You must implement a mathematically rigorous memory pipeline.

### 3.1 Pipeline Stages

1. **Ingestion:** Accept raw text, PR diffs, or architecture docs.
2. **Normalization & Cleaning:** Strip noise, resolve markdown links.
3. **Semantic Chunking:** Context-aware chunking (not arbitrary token limits).
4. **Entity Extraction (Cognee):** Extract `Actor`, `Component`, `Decision`, `Incident`.
5. **Relationship Extraction:** Map edges (e.g., `[Developer A] -> IMPLEMENTED -> [Microservice B]`).
6. **Graph Optimization:** Deduplicate nodes, merge synonymous entities.
7. **Vectorization:** Embed chunks using high-dimensional models.
8. **Storage:** Persist to Vector DB (chunks) + Graph DB (relationships).

### 3.2 Memory Attributes

Every memory object MUST contain:

- `id`, `source_uri`, `timestamp`, `author`
- `importance_score` (1-10)
- `confidence_score` (0.0-1.0)
- `decay_factor` (Calculated based on time and usage)
- `provenance` (Cryptographic hash of source data)

---

## SECTION 4: ADVANCED LANGGRAPH MULTI-AGENT SYSTEM

Do not use simple ReAct prompts. Implement a cyclic, graph-based agent architecture using LangGraph.

### 4.1 Node Definitions

- **Gateway Node:** Routes intent (e.g., Query, Ingestion, Summarization).
- **Planner Node:** Breaks down complex queries into sub-tasks.
- **Retriever Node:** Executes Hybrid Search (Vector + Graph Centrality + BM25).
- **Reasoner Node:** Synthesizes retrieved data against the query.
- **Critic / Verifier Node:** Cross-checks reasoning against retrieved *evidence*.
- **Generator Node:** Formats the final response.

### 4.2 Reflection & Verification Loop

- The **Critic Node** MUST evaluate the **Reasoner Node's** output.
- If `confidence < 0.85` or `hallucination_detected == true`, the Graph MUST loop back to the **Retriever Node** with a refined search query. Maximum 3 loops before graceful degradation ("Insufficient data").

---

## SECTION 5: RETRIEVAL, REASONING, & EVIDENCE RANKING

### 5.1 Hybrid Retrieval Pipeline

Execute in parallel:

1. **Vector Similarity:** Find semantically related chunks.
2. **Graph Traversal:** Find N-degree neighbors of identified entities.
3. **Lexical Search:** Keyword match for exact error codes or method names.

### 5.2 Evidence Ranking Algorithm

Rank retrieved nodes based on:
`Score = (Similarity * 0.4) + (PageRank * 0.3) + (Freshness * 0.2) + (Importance * 0.1)`

### 5.3 Anti-Hallucination Rules

- ALL claims in the final output MUST include inline citations `[Evidence ID]`.
- The system must explicitly say "I do not have historical data on this" rather than guessing.

---

## SECTION 6: INFRASTRUCTURE & SECURITY

### 6.1 LLM Gateway & Fallback

- Implement an LLM Gateway interface.
- Primary: GPT-4o / Claude 3.5 Sonnet.
- Fallback: Local LLM (Llama 3 / Mistral) via Ollama for offline/privacy mode.
- Circuit breakers must trip if API latency exceeds 5000ms.

### 6.2 Security Architecture

- **Auth:** JWT-based stateless authentication + RBAC (Admin, Contributor, Viewer).
- **Encryption:** AES-256 for API keys and integrations at rest.
- **Defense:** Strict input validation to prevent Prompt Injection (e.g., Delimiter isolation, LLM-based prompt sanitization).

### 6.3 Observability & Telemetry

Integrate OpenTelemetry for:

- Agent Latency (time spent in Planner vs Retriever).
- Token usage & cost per query.
- Retrieval accuracy (measured by user thumbs up/down).
- Graph DB query performance.

---

## SECTION 7: QUALITY GATES & DEVOPS

### 7.1 Testing Pyramid

- **Unit Tests:** 90% coverage for Domain and Application layers.
- **Integration Tests:** Test Database, Vector Store, and Graph connections using Testcontainers.
- **E2E Tests:** Simulate full Agent graph execution with mocked LLM responses.

### 7.2 CI/CD Quality Gates

Code generation is only complete if:

1. No unhandled exceptions or Type errors.
2. Security dependencies are scanned.
3. Linter passes with 0 warnings.
4. Auto-generated API documentation (Swagger/OpenAPI) is up to date.

---

## SECTION 8: HACKATHON DEMO & UI/UX MODE

The system must ship with a "Showcase Mode":

- **One-Command Setup:** `docker-compose up --build` must launch Postgres, Qdrant, Backend, Frontend, and Local LLM.
- **UI Specifications:** Dark-mode, terminal-inspired sleek UI.
- **Features:**
  - Chat interface with split-screen showing the "Thought Process" (LangGraph execution steps).
  - Visual Knowledge Graph explorer (React Flow) showing nodes and edges.
  - "Evidence Drawer" where users can click citations to see exact source diffs or Slack messages.

---

## SECTION 9: STRICT BUILD ORDER EXECUTION PLAN

You will execute the build in the following exact sequence. Do not move to the next phase until the current one is exhaustively implemented.

- **PHASE 1:** Initialize repository, Dev Environment, Docker-compose, and core structural folders.
- **PHASE 2:** Implement Domain Entities, Value Objects, and abstract Interfaces (Clean Architecture base).
- **PHASE 3:** Build the Infrastructure Layer (Database adapters, Vector DB, Cognee Graph integration).
- **PHASE 4:** Build the Application Layer (Memory Lifecycle pipelines, Event Handlers).
- **PHASE 5:** Build the Multi-Agent System (LangGraph nodes, edges, state management, LLM Gateway).
- **PHASE 6:** Build the Presentation Layer (REST APIs, WebSockets for streaming agent responses).
- **PHASE 7:** Build the Frontend UI (Next.js chat, Graph visualization, Evidence viewer).
- **PHASE 8:** Implement Observability, Error Handling, Self-Healing retries.
- **PHASE 9:** Write exhaustive Unit and Integration Tests.
- **PHASE 10:** Generate extensive Markdown documentation, OpenAPI specs, and deployment guides.

---

## SECTION 10: FINAL PRODUCTION VALIDATION CHECKLIST

Before declaring completion, verify internally:

- [ ] Is the code tightly coupled to OpenAI, or is the LLM Gateway properly abstracted?
- [ ] Does the Cognee implementation correctly extract and store relationships, not just flat text?
- [ ] Does the LangGraph workflow include a Critic/Verifier node that forces retries?
- [ ] Are all confidence scores and evidence citations strictly propagated to the UI?
- [ ] Are there ZERO placeholder functions across the entire codebase?
- [ ] Can the entire stack boot seamlessly via `docker-compose`?

**IF ALL CONDITIONS ARE MET, BEGIN EXECUTION AT PHASE 1 NOW.**
