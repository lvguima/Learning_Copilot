from __future__ import annotations

import os

import httpx

from ..config import LLMConfig


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    async def generate(self, messages: list[dict[str, str]]) -> str:
        if self.config.provider == "echo":
            for message in reversed(messages):
                if message["role"] == "user":
                    return f"[echo] {message['content'][:800]}"
            return "[echo] no user message"

        api_key = os.getenv(self.config.api_key_env, "")
        if not api_key:
            raise RuntimeError(f"Missing API key in env var: {self.config.api_key_env}")

        url = self.config.endpoint.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            body = response.json()
            return body["choices"][0]["message"]["content"]

