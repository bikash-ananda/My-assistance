from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from .config import Settings


@dataclass
class Completion:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


class Provider(Protocol):
    name: str

    async def complete(self, messages: list[dict[str, str]]) -> Completion: ...


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings):
        self.url = settings.ollama_url
        self.model = settings.ollama_model

    async def complete(self, messages: list[dict[str, str]]) -> Completion:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                self.url + "/api/chat",
                json={"model": self.model, "messages": messages, "stream": False, "options": {"num_predict": 512}},
            )
            response.raise_for_status()
            payload = response.json()
        return Completion(
            text=payload.get("message", {}).get("content", ""),
            prompt_tokens=payload.get("prompt_eval_count"),
            completion_tokens=payload.get("eval_count"),
        )


def configured_provider(settings: Settings) -> Provider | None:
    if settings.provider != "ollama" or not settings.ollama_model:
        return None
    target = urlsplit(settings.ollama_url)
    if target.scheme != "http" or target.hostname not in {"127.0.0.1", "localhost", "::1"}:
        return None
    if target.username or target.password:
        return None
    return OllamaProvider(settings)