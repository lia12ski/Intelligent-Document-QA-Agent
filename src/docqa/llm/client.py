from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import requests

from docqa.config import Settings


class LlmClient(Protocol):
    provider_name: str

    def generate(self, prompt: str) -> str:
        ...


@dataclass(frozen=True)
class MockLlmClient:
    provider_name: str = "mock"

    def generate(self, prompt: str) -> str:
        _ = prompt
        return ""


@dataclass(frozen=True)
class OpenAICompatibleClient:
    api_key: str
    model: str
    base_url: str = "https://api.openai.com/v1"
    timeout_seconds: int = 60
    provider_name: str = "openai"

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY or LLM_API_KEY is required for LLM_PROVIDER=openai")
        if not self.model:
            raise RuntimeError("OPENAI_MODEL or LLM_MODEL is required for LLM_PROVIDER=openai")

        url = self.base_url.rstrip("/") + "/chat/completions"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You answer only from the provided context and cite page or clause evidence.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0,
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        choices = payload.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response does not contain choices")
        message = choices[0].get("message") or {}
        content = message.get("content", "")
        if not content.strip():
            raise RuntimeError("LLM response content is empty")
        return content.strip()


@dataclass(frozen=True)
class OllamaClient:
    base_url: str
    model: str
    timeout_seconds: int = 60
    provider_name: str = "ollama"

    def generate(self, prompt: str) -> str:
        if not self.model:
            raise RuntimeError("OLLAMA_MODEL is required for LLM_PROVIDER=ollama")
        response = requests.post(
            self.base_url.rstrip("/") + "/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("response", "")
        if not content.strip():
            raise RuntimeError("Ollama response content is empty")
        return content.strip()


def build_llm_client(settings: Settings) -> LlmClient | None:
    provider = settings.llm_provider.strip().lower()
    if provider in {"", "mock", "disabled", "none"}:
        return None
    if provider == "deepseek" or (provider == "openai" and settings.deepseek_api_key and not settings.openai_api_key):
        return OpenAICompatibleClient(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
            provider_name="deepseek",
        )
    if provider in {"openai", "openai-compatible", "compatible"}:
        return OpenAICompatibleClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            base_url=settings.openai_base_url or "https://api.openai.com/v1",
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if provider == "ollama":
        return OllamaClient(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")
