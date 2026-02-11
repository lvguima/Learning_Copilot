from __future__ import annotations

import os
from typing import Any

import httpx

from ..config import LLMConfig


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def _extract_user_text(self, message: dict[str, Any]) -> str:
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    return str(part.get("text", ""))
            return str(content)
        return str(content)

    def _extract_output_text(self, body: dict[str, Any]) -> str:
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError(f"Malformed LLM response: missing choices. body_keys={list(body.keys())}")

        choice0 = choices[0] if isinstance(choices[0], dict) else {}
        message = choice0.get("message") if isinstance(choice0.get("message"), dict) else {}
        candidates: list[str] = []

        # OpenAI-compatible primary field.
        content = message.get("content")
        if isinstance(content, str):
            candidates.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if "text" in part:
                        candidates.append(str(part.get("text", "")))
                    elif part.get("type") == "output_text":
                        candidates.append(str(part.get("text", "")))

        # Some providers expose reasoning in separate fields.
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str):
            candidates.append(reasoning)

        # Some compatibility layers still expose plain `text`.
        if isinstance(choice0.get("text"), str):
            candidates.append(str(choice0.get("text")))

        merged = "\n".join([item.strip() for item in candidates if isinstance(item, str) and item.strip()]).strip()
        if merged:
            return merged

        finish_reason = choice0.get("finish_reason")
        message_keys = list(message.keys()) if isinstance(message, dict) else []
        raise RuntimeError(
            "LLM returned empty content. "
            f"finish_reason={finish_reason}, message_keys={message_keys}, choice_keys={list(choice0.keys())}"
        )

    async def generate(self, messages: list[dict[str, Any]]) -> str:
        if self.config.provider == "echo":
            for message in reversed(messages):
                if message["role"] == "user":
                    text = self._extract_user_text(message)
                    return f"[echo] {text[:800]}"
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
            if response.status_code >= 400:
                detail = response.text
                try:
                    data = response.json()
                    detail = str(data.get("error") or data.get("detail") or data)
                except Exception:
                    pass
                raise RuntimeError(
                    f"Upstream LLM HTTP {response.status_code}: {detail}"
                )
            body = response.json()
            return self._extract_output_text(body)

