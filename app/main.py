from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

try:
    from .chat_service import PromptChatService
    from .config import get_settings
    from .schemas import ChatRequest, ChatResponse, HistoryItem, HistoryResponse
except Exception:  # pragma: no cover - allow running as a script inside the app/ folder
    from chat_service import PromptChatService
    from config import get_settings
    from schemas import ChatRequest, ChatResponse, HistoryItem, HistoryResponse


settings = get_settings()
app = FastAPI(title=settings.app_title)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

service = PromptChatService(settings)

base_dir = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(base_dir / "templates"))
app.mount("/static", StaticFiles(directory=str(base_dir / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": settings.app_title,
            "default_model": settings.default_model,
            "default_system_prompt": "You are a helpful assistant for prompt testing.",
        },
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    # Allow both OpenRouter and Groq API key configurations
    if not settings.openrouter_api_key and not settings.groq_api_key:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY or GROQ_API_KEY is required")

    model = payload.model or settings.default_model
    system_prompt = payload.system_prompt or "You are a helpful assistant for prompt testing."

    try:
        reply = await run_in_threadpool(
            service.chat,
            session_id=payload.session_id,
            message=payload.message,
            model=model,
            system_prompt=system_prompt,
            file_data=payload.file_data,
            file_name=payload.file_name,
            file_mime_type=payload.file_mime_type,
        )
    except Exception as exc:
        import traceback, pathlib

        tb = traceback.format_exc()
        logpath = pathlib.Path(__file__).resolve().parent.parent / "error.log"
        with open(logpath, "a", encoding="utf-8") as f:
            f.write("--- /api/chat exception ---\n")
            f.write(tb)
            f.write("\n")

        error_msg = str(exc)
        lowered = error_msg.lower()

        if "insufficient_quota" in lowered or "insufficient credits" in lowered or "payment" in lowered:
            detail = "Insufficient credits/quota for this model"
        elif "rate limit" in lowered or "rate_limit" in lowered:
            detail = "Rate limit exceeded. Please retry shortly"
        elif "model_not_found" in lowered or "no endpoints found" in lowered or "not found" in lowered:
            detail = f"Model '{model}' is unavailable on this provider"
        elif "authentication" in lowered or "unauthorized" in lowered or "invalid api key" in lowered:
            detail = "Authentication failed. Check your API key/provider"
        elif "timeout" in lowered:
            detail = "Request timed out. Please try again"
        elif error_msg.strip():
            detail = error_msg.strip()
        else:
            detail = f"Chat error, see {logpath}"

        raise HTTPException(status_code=500, detail=detail)

    return ChatResponse(session_id=payload.session_id, model=model, reply=reply)


@app.get("/api/history/{session_id}", response_model=HistoryResponse)
async def get_history(session_id: str) -> HistoryResponse:
    messages = await run_in_threadpool(service.get_history, session_id)
    return HistoryResponse(
        session_id=session_id,
        messages=[HistoryItem(**message) for message in messages],
    )


@app.delete("/api/history/{session_id}")
async def clear_history(session_id: str) -> dict[str, str]:
    await run_in_threadpool(service.clear_history, session_id)
    return {"status": "cleared", "session_id": session_id}


if __name__ == "__main__":
    # Allow running via `python main.py` from inside the app/ directory.
    import uvicorn
    # Use module string so uvicorn manages the process lifecycle reliably.
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
