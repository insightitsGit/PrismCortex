"""Gemini LLM client matching mem0 memory-benchmarks LLMClient interface."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any, TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")


class GeminiLLMClient:
    """Async answerer/judge using google-genai (GEMINI_API_KEY)."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        provider: str = "gemini",
        api_key: str | None = None,
        **_: Any,
    ):
        self.model = model
        self.provider = "gemini"
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError("Set GEMINI_API_KEY for standard benchmarks")
        from google import genai

        self._client = genai.Client(api_key=key)

    async def generate(
        self,
        system: str = "",
        user: str = "",
        temperature: float = 0,
        max_tokens: int = 4096,
    ) -> str:
        prompt = f"{system}\n\n{user}".strip() if system else user
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._generate_sync, prompt, temperature, max_tokens)

    def _generate_sync(self, prompt: str, temperature: float, max_tokens: int) -> str:
        for attempt in range(3):
            try:
                resp = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config={"temperature": temperature, "max_output_tokens": max_tokens},
                )
                return (resp.text or "").strip()
            except Exception as exc:
                logger.warning("Gemini generate attempt %d failed: %s", attempt + 1, exc)
        return ""

    async def generate_structured(
        self,
        system: str,
        user: str,
        response_format: type[T] | None = None,
        temperature: float = 0,
        max_tokens: int = 4096,
    ) -> Any:
        prompt = f"{system}\n\n{user}\n\nRespond with JSON only: {{\"label\": \"CORRECT\" or \"WRONG\", \"reasoning\": \"...\"}}"
        raw = await self.generate(system="", user=prompt, temperature=temperature, max_tokens=max_tokens)
        parsed = self._parse_json(raw)
        if response_format is not None:
            return response_format(**parsed)
        return parsed

    @staticmethod
    def _parse_json(raw: str) -> dict:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        m = re.search(r"\{[^{}]*\"label\"[^{}]*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                pass
        if "CORRECT" in raw.upper():
            return {"label": "CORRECT", "reasoning": raw[:200]}
        return {"label": "WRONG", "reasoning": raw[:200]}
