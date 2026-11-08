"""Paquete de ruteadores FastAPI de MIRA CU-3."""

from backend.app.routers.session import router as session_router
from backend.app.routers.chat import router as chat_router
from backend.app.routers.actions import router as actions_router

__all__ = ["session_router", "chat_router", "actions_router"]
