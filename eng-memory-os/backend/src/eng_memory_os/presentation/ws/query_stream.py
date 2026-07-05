"""
WebSocket handler for real-time query streaming.

Supports streaming the multi-agent pipeline's execution progress
to the frontend in real-time via WebSocket.
"""

from __future__ import annotations

import asyncio
import json
import time

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from eng_memory_os.domain.agent.entities import Query
from eng_memory_os.presentation.dependencies import get_agent_runner

logger = structlog.get_logger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str) -> None:
        await websocket.accept()
        self._connections[client_id] = websocket
        logger.info("ws_connected", client_id=client_id, total=len(self._connections))

    def disconnect(self, client_id: str) -> None:
        self._connections.pop(client_id, None)
        logger.info("ws_disconnected", client_id=client_id, total=len(self._connections))

    async def send_json(self, client_id: str, data: dict) -> None:
        ws = self._connections.get(client_id)
        if ws:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(client_id)

    async def broadcast(self, data: dict) -> None:
        disconnected: list[str] = []
        for client_id, ws in self._connections.items():
            try:
                await ws.send_json(data)
            except Exception:
                disconnected.append(client_id)
        for cid in disconnected:
            self.disconnect(cid)

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


@router.websocket("/ws/query")
async def websocket_query(websocket: WebSocket):
    """WebSocket endpoint for streaming query execution.

    Protocol:
    1. Client sends: {"type": "query", "text": "...", "user_id": "..."}
    2. Server streams progress updates:
       {"type": "progress", "node": "gateway", "status": "started"}
       {"type": "progress", "node": "planner", "status": "completed", "data": {...}}
       ...
    3. Server sends final response:
       {"type": "response", "data": {...}}
    4. Or error:
       {"type": "error", "detail": "..."}
    """
    import uuid
    client_id = str(uuid.uuid4())[:8]

    await manager.connect(websocket, client_id)

    try:
        while True:
            # Receive query from client
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_json(client_id, {
                    "type": "error",
                    "detail": "Invalid JSON message",
                })
                continue

            msg_type = message.get("type")

            if msg_type == "query":
                await _handle_query(client_id, message)
            elif msg_type == "ping":
                await manager.send_json(client_id, {"type": "pong"})
            else:
                await manager.send_json(client_id, {
                    "type": "error",
                    "detail": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.exception("ws_error", client_id=client_id, error=str(e))
        manager.disconnect(client_id)


async def _handle_query(client_id: str, message: dict) -> None:
    """Process a query message and stream progress updates."""
    query_text = message.get("text", "")
    user_id = message.get("user_id", "ws-user")
    mode = message.get("mode", "agent")

    if not query_text:
        await manager.send_json(client_id, {
            "type": "error",
            "detail": "Query text is required",
        })
        return

    start_time = time.perf_counter()

    # Send initial acknowledgment
    initial_node = "retriever" if mode == "rag" else "gateway"
    initial_msg = "Searching vector store, knowledge graph, and lexical index..." if mode == "rag" else "Classifying query intent..."
    await manager.send_json(client_id, {
        "type": "progress",
        "node": initial_node,
        "status": "started",
        "message": initial_msg,
    })

    try:
        runner = get_agent_runner()
        query = Query.create(raw_text=query_text, user_id=user_id)

        # Stream progress for each node
        if mode == "rag":
            nodes = ["retriever", "reasoner"]
        else:
            nodes = ["gateway", "planner", "retriever", "reasoner", "critic", "generator"]

        for i, node in enumerate(nodes):
            await manager.send_json(client_id, {
                "type": "progress",
                "node": node,
                "status": "processing",
                "step": i + 1,
                "total_steps": len(nodes),
                "message": _get_node_message(node),
            })
            # Small delay to allow frontend to render progress
            await asyncio.sleep(0.1)

        # Execute the query based on mode
        if mode == "rag" and hasattr(runner, "run_rag"):
            response = await runner.run_rag(query)
        else:
            response = await runner.run(query)

        total_time = (time.perf_counter() - start_time) * 1000

        # Persist query log in the database
        try:
            from eng_memory_os.presentation.dependencies import get_db_session
            from eng_memory_os.infrastructure.db.postgres_query_log_repository import PostgresQueryLogRepository
            async with get_db_session() as session:
                repo = PostgresQueryLogRepository(session)
                await repo.save(
                    user_id_str=user_id,
                    raw_query=query_text,
                    classified_intent=mode,
                    response_text=response.response_text,
                    confidence=float(response.confidence),
                    is_degraded=response.is_degraded,
                    total_time_ms=total_time,
                    retry_count=response.retry_count,
                )
        except Exception as e:
            logger.warning("ws_query_log_persist_failed", error=str(e))

        # Send final response
        await manager.send_json(client_id, {
            "type": "response",
            "data": {
                "response_id": str(response.id),
                "response_text": response.response_text,
                "confidence": float(response.confidence),
                "is_degraded": response.is_degraded,
                "citations": [
                    {
                        "evidence_id": c.evidence_id,
                        "memory_id": c.memory_id,
                        "source_uri": c.source_uri,
                        "relevance_score": c.relevance_score,
                    }
                    for c in response.citations
                ],
                "total_time_ms": round(total_time, 1),
                "retry_count": response.retry_count,
                "nodes_visited": response.nodes_visited,
            },
        })

    except Exception as e:
        logger.exception("ws_query_failed", client_id=client_id)
        await manager.send_json(client_id, {
            "type": "error",
            "detail": str(e),
        })


def _get_node_message(node: str) -> str:
    """Return a human-readable progress message for each node."""
    messages = {
        "gateway": "Classifying query intent...",
        "planner": "Decomposing query into sub-tasks...",
        "retriever": "Searching vector store, knowledge graph, and lexical index...",
        "reasoner": "Synthesizing evidence with citations...",
        "critic": "Verifying reasoning against evidence...",
        "generator": "Formatting final response...",
    }
    return messages.get(node, "Processing...")
