"""The compiler: the thin Claude API wrapper, the only stochastic step in generation.

Sends a prompt, parses JSON back, retries on bad output, so the rest of the pipeline is deterministic.
"""

from __future__ import annotations

import json
from typing import Any

import anthropic
from dotenv import load_dotenv

load_dotenv()


class Compiler:
    def __init__(self, model: str, max_tokens: int = 4000, retries: int = 3) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.retries = retries
        self.client = anthropic.Anthropic()

    def json(self, system: str, user: str) -> dict[str, Any]:
        last = ""
        for _ in range(self.retries):
            msg = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system + "\n\nReturn ONLY a single JSON object: no prose, no markdown, no code fences.",
                messages=[{"role": "user", "content": user}],
            )
            text = "".join(b.text for b in msg.content if b.type == "text")
            start, end = text.find("{"), text.rfind("}")
            if start != -1 and end != -1:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            last = text
        raise ValueError(f"model did not return valid JSON in {self.retries} tries: {last[:200]!r}")
