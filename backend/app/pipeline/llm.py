"""
LLM orchestration wrapper.

Every pipeline module calls `structured_call()` which:
1. Sends a system prompt + user content to the Anthropic API
2. Demands JSON-only output matching a Pydantic schema
3. Validates against the schema
4. On validation failure, feeds the error back to the model for one repair pass

This enforces the hard rule: structured JSON between all modules.
"""
from __future__ import annotations

import json
from typing import Type, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from ..config import get_settings

settings = get_settings()
T = TypeVar("T", bound=BaseModel)

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def _extract_json(text: str) -> dict:
    """Strip markdown fences and locate the outermost JSON object."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model output.")
    return json.loads(text[start:end + 1])


def structured_call(
    system: str,
    user_content: str | list,
    schema: Type[T],
    model: str | None = None,
    max_tokens: int = 4096,
    temperature: float = 0.4,
) -> tuple[T, dict]:
    """Returns (validated_object, usage_dict). One automatic repair pass on schema failure."""
    model = model or settings.model_reasoning
    schema_json = json.dumps(schema.model_json_schema(), indent=1)

    system_full = (
        f"{system}\n\n"
        "OUTPUT CONTRACT:\n"
        "Respond with ONLY a JSON object valid against this JSON Schema. "
        "No prose, no markdown fences, no commentary.\n"
        f"{schema_json}"
    )

    messages = [{"role": "user", "content": user_content}]
    usage = {"tokens_in": 0, "tokens_out": 0}

    for attempt in range(2):
        resp = client().messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_full,
            messages=messages,
        )
        usage["tokens_in"] += resp.usage.input_tokens
        usage["tokens_out"] += resp.usage.output_tokens
        raw = "".join(b.text for b in resp.content if b.type == "text")

        try:
            data = _extract_json(raw)
            return schema.model_validate(data), usage
        except (ValueError, json.JSONDecodeError, ValidationError) as exc:
            if attempt == 1:
                raise RuntimeError(f"Schema validation failed after repair pass: {exc}") from exc
            messages = messages + [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": (
                    "Your output failed validation with this error:\n"
                    f"{exc}\n\nReturn ONLY the corrected JSON object."
                )},
            ]
    raise RuntimeError("unreachable")
