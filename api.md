# REST & WebSocket API Specification

The Engineering Memory OS exposes a REST API for management/ingest and a WebSocket endpoint for real-time query progress streaming.

---

## 1. REST API Endpoints

### 1.1 Memory Context

#### Ingest Memory

- **URL:** `POST /api/v1/memories`
- **Request Body (JSON):**

  ```json
  {
    "raw_content": "## ADR-042: Switch from REST to gRPC for inter-service communication...",
    "source_uri": "https://github.com/org/repo/blob/main/docs/adr/042-grpc.md",
    "source_type": "adr",
    "author": "alice@company.com",
    "title": "ADR-042: REST to gRPC Migration",
    "tags": ["architecture", "grpc", "migration"]
  }
  ```

- **Response (201 Created):**

  ```json
  {
    "memory_id": "6fc8c86e-cc00-43aa-a4a7-7324aea14301",
    "status": "pending",
    "importance_score": 7.5
  }
  ```

#### Query Knowledge Base (REST)

- **URL:** `POST /api/v1/memories/query`
- **Request Body (JSON):**

  ```json
  {
    "query": "Why did we choose gRPC?"
  }
  ```

- **Response (200 OK):**

  ```json
  {
    "response_id": "a90b8f72-73a1-432d-90cf-1a73be9de8a2",
    "response_text": "We chose gRPC for inter-service communication to reduce latency and leverage bi-directional streaming [E-6fc8c86e].",
    "confidence": 0.95,
    "is_degraded": false,
    "citations": [
      {
        "evidence_id": "6fc8c86e-cc00-43aa-a4a7-7324aea14301",
        "memory_id": "6fc8c86e-cc00-43aa-a4a7-7324aea14301",
        "source_uri": "https://github.com/org/repo/blob/main/docs/adr/042-grpc.md",
        "relevance_score": 0.92,
        "snippet": "gRPC provides lower latency and bidirectional streaming..."
      }
    ],
    "total_time_ms": 321.4,
    "retry_count": 0
  }
  ```

#### List Memories

- **URL:** `GET /api/v1/memories`
- **Query Parameters:**
  - `status`: Optional filter (e.g. `active`, `stale`, `pending`, `failed`)
  - `author`: Optional filter by author email
  - `limit`: Default 50
  - `offset`: Default 0

#### Get Memory Details

- **URL:** `GET /api/v1/memories/{memory_id}`

#### Delete Memory

- **URL:** `DELETE /api/v1/memories/{memory_id}`

#### Memory Statistics Summary

- **URL:** `GET /api/v1/memories/stats/summary`

---

### 1.2 Knowledge Graph Context

#### Search Nodes

- **URL:** `GET /api/v1/knowledge/nodes`
- **Query Parameters:**
  - `name`: Term to search
  - `entity_type`: Filter by type (e.g. `actor`, `component`, `decision`, `incident`)
  - `fuzzy`: Boolean (fuzzy matching)

#### Get Node Details

- **URL:** `GET /api/v1/knowledge/nodes/{node_id}`

#### Get Neighbor Subgraph (React Flow Viz)

- **URL:** `GET /api/v1/knowledge/nodes/{node_id}/neighbors`
- **Query Parameters:**
  - `depth`: Traversals from node (default 1)

#### Optimize Knowledge Graph

- **URL:** `POST /api/v1/knowledge/optimize`

---

### 1.3 System & Gateway Context

#### Health Check

- **URL:** `GET /api/v1/system/health`

#### LLM Provider Health Statuses

- **URL:** `GET /api/v1/system/providers`

#### Aggregate Token Usage Audits

- **URL:** `GET /api/v1/system/tokens`

---

## 2. WebSocket Query Streaming

Real-time progressive query execution updates are streamed through `/ws/query`.

### 2.1 Connection Protocol

1. Client establishes connection to `ws://localhost:8000/ws/query`.
2. Client sends a subscription message:

   ```json
   {
     "type": "query",
     "text": "Why did we switch to Valkey?",
     "user_id": "user-123"
   }
   ```

3. Server streams execution updates:

   ```json
   {
     "type": "progress",
     "node": "gateway",
     "status": "processing",
     "step": 1,
     "total_steps": 6,
     "message": "Classifying query intent..."
   }
   ```

4. Server sends final cited output:

   ```json
   {
     "type": "response",
     "data": {
       "response_id": "uuid",
       "response_text": "...",
       "confidence": 0.9,
       "is_degraded": false,
       "citations": [],
       "total_time_ms": 1200.0,
       "retry_count": 0,
       "nodes_visited": ["gateway", "planner", "retriever", "reasoner", "critic", "generator"]
     }
   }
   ```
