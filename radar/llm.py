"""Thin, optional LLM wrapper.

Everything here degrades gracefully: if the ``openai`` package or an API key is
missing, ``available()`` returns False and the pipeline runs fully
deterministically (and free). Only relevance scoring, screenshot OCR, and
AI-lab page extraction depend on this.
"""

from __future__ import annotations

import base64
import json
import os
from typing import Optional

_DEFAULT_MODEL = os.environ.get("RADAR_LLM_MODEL", "gpt-4o-mini")


class LLM:
    def __init__(self, model: Optional[str] = None):
        self.model = model or _DEFAULT_MODEL
        self._client = None
        self._init_error: Optional[str] = None
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            self._init_error = "OPENAI_API_KEY not set"
            return
        try:
            from openai import OpenAI  # type: ignore

            self._client = OpenAI(api_key=api_key)
        except Exception as exc:  # pragma: no cover - import/runtime guard
            self._init_error = f"openai client unavailable: {exc}"

    def available(self) -> bool:
        return self._client is not None

    @property
    def init_error(self) -> Optional[str]:
        return self._init_error

    def complete_json(self, system: str, user: str, max_tokens: int = 1024) -> Optional[dict]:
        """Ask the model for a JSON object and parse it. Returns None on failure."""
        if not self.available():
            return None
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception:
            return None

    def vision_json(self, prompt: str, image_bytes: bytes, mime: str = "image/png",
                    max_tokens: int = 1500) -> Optional[dict]:
        """Send an image + prompt, expect a JSON object back."""
        if not self.available():
            return None
        try:
            b64 = base64.b64encode(image_bytes).decode("ascii")
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{mime};base64,{b64}"},
                            },
                        ],
                    }
                ],
                temperature=0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return json.loads(resp.choices[0].message.content)
        except Exception:
            return None
