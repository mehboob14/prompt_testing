from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: str
    model: str | None = None
    system_prompt: str | None = None
    file_data: str | None = None
    file_name: str | None = None
    file_mime_type: str | None = None


class ChatResponse(BaseModel):
    session_id: str
    model: str
    reply: str


class HistoryItem(BaseModel):
    role: str
    content: str


class HistoryResponse(BaseModel):
    session_id: str
    messages: list[HistoryItem]
