from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    openrouter_api_key: str
    openrouter_base_url: str
    default_model: str
    groq_api_key: str
    groq_api_base: str
    app_title: str
    app_url: str


def get_settings() -> Settings:
    return Settings(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
        openrouter_base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        default_model=os.getenv("DEFAULT_MODEL", os.getenv("MODEL", "meta-llama/llama-3.1-8b-instruct")),
        groq_api_key=os.getenv("GROQ_API_KEY", ""),
        groq_api_base=os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1"),
        app_title=os.getenv("APP_TITLE", "Prompt Testing Tool"),
        app_url=os.getenv("APP_URL", "http://localhost:5000"),
    )
