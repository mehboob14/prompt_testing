from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_openai import ChatOpenAI

try:
    from .config import Settings
except Exception:  # pragma: no cover
    from config import Settings


class PromptChatService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._histories: dict[str, ChatMessageHistory] = {}

    def _get_history(self, session_id: str) -> BaseChatMessageHistory:
        if session_id not in self._histories:
            self._histories[session_id] = ChatMessageHistory()
        return self._histories[session_id]

    @lru_cache(maxsize=16)
    def _get_runnable(self, model_name: str) -> RunnableWithMessageHistory:
        if "llama-3.3" in model_name and self.settings.groq_api_key:
            llm = ChatOpenAI(
                model=model_name,
                openai_api_key=self.settings.groq_api_key,
                openai_api_base=self.settings.groq_api_base,
                temperature=0.2,
            )
        else:
            llm = ChatOpenAI(
                model=model_name,
                openai_api_key=self.settings.openrouter_api_key,
                openai_api_base=self.settings.openrouter_base_url,
                default_headers={
                    "HTTP-Referer": self.settings.app_url,
                    "X-Title": self.settings.app_title,
                },
                temperature=0.2,
            )

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "{system_prompt}"),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ]
        )

        chain = prompt | llm
        return RunnableWithMessageHistory(
            chain,
            self._get_history,
            input_messages_key="input",
            history_messages_key="history",
        )

    def chat(
        self,
        *,
        session_id: str,
        message: str,
        model: str,
        system_prompt: str,
        file_data: str | None = None,
        file_name: str | None = None,
        file_mime_type: str | None = None,
    ) -> str:
        input_message = message
        if file_data and file_name:
            input_message = f"{message}\n\n[Attached file: {file_name} ({file_mime_type})]"

        runnable = self._get_runnable(model)
        result = runnable.invoke(
            {"input": input_message, "system_prompt": system_prompt},
            config={"configurable": {"session_id": session_id}},
        )
        return self._extract_text(result)

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        history = self._get_history(session_id)
        return [self._to_payload(msg) for msg in history.messages]

    def clear_history(self, session_id: str) -> None:
        history = self._get_history(session_id)
        history.clear()

    def _to_payload(self, msg: BaseMessage) -> dict[str, str]:
        role = "assistant"
        if isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "assistant"
        else:
            role = msg.type
        return {"role": role, "content": self._extract_text(msg)}

    @staticmethod
    def _extract_text(value: Any) -> str:
        if hasattr(value, "content"):
            content = value.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for chunk in content:
                    if isinstance(chunk, dict):
                        text = chunk.get("text")
                        if text:
                            parts.append(str(text))
                    else:
                        parts.append(str(chunk))
                return "\n".join(parts).strip()
            return str(content)
        return str(value)
