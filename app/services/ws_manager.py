"""In-memory WebSocket connection manager.

Tracks connected visitors (one socket per chatbot:session) and agents (grouped
by org). Broadcasts messages between a visitor and the agents of its org.

SCALING NOTE: this state is per-process. On a single-server VPS with one
uvicorn worker that is correct and sufficient. To run multiple workers/servers,
replace the in-process dicts with a Redis pub/sub layer (publish on send,
subscribe per process) — the call sites below are the only integration points.
"""
import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


def visitor_key(chatbot_id: str, session_id: str) -> str:
    return f"{chatbot_id}:{session_id}"


class ConnectionManager:
    def __init__(self) -> None:
        # chatbot_id:session_id -> visitor socket
        self.visitors: dict[str, WebSocket] = {}
        # org_id -> set of agent sockets
        self.agents: dict[str, set[WebSocket]] = {}
        # agent socket -> { agent_id, agent_name, org_id }
        self.agent_info: dict[WebSocket, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    # ── Visitors ──
    async def connect_visitor(self, ws: WebSocket, key: str) -> None:
        await ws.accept()
        self.visitors[key] = ws

    def disconnect_visitor(self, key: str) -> None:
        self.visitors.pop(key, None)

    def visitor_online(self, key: str) -> bool:
        return key in self.visitors

    async def send_to_visitor(self, key: str, payload: dict) -> None:
        ws = self.visitors.get(key)
        if ws is None:
            return
        try:
            await ws.send_json(payload)
        except Exception:
            logger.debug("Failed to send to visitor %s", key)

    # ── Agents ──
    async def connect_agent(
        self, ws: WebSocket, org_id: str, agent_id: str, agent_name: str
    ) -> None:
        await ws.accept()
        self.agents.setdefault(org_id, set()).add(ws)
        self.agent_info[ws] = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "org_id": org_id,
        }

    def disconnect_agent(self, ws: WebSocket) -> None:
        info = self.agent_info.pop(ws, None)
        if info:
            peers = self.agents.get(info["org_id"])
            if peers:
                peers.discard(ws)
                if not peers:
                    self.agents.pop(info["org_id"], None)

    async def broadcast_to_org_agents(self, org_id: str, payload: dict) -> None:
        for ws in list(self.agents.get(org_id, set())):
            try:
                await ws.send_json(payload)
            except Exception:
                logger.debug("Failed to send to an agent in org %s", org_id)

    def agent_name(self, ws: WebSocket) -> str:
        return self.agent_info.get(ws, {}).get("agent_name", "Agent")

    def agent_id(self, ws: WebSocket) -> str:
        return self.agent_info.get(ws, {}).get("agent_id", "")


# Singleton used across the app (one process).
manager = ConnectionManager()
