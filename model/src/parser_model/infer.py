"""OpenAI-compatible chat client (Ollama, llama.cpp server, vLLM) with constrained output.

``--constrained`` first sends ``response_format`` of type ``json_schema``. If the server rejects
it (HTTP 4xx), the client falls back through each server's native option, in order, and keeps
using the first one that works:

1. ``guided_json`` (vLLM)
2. ``json_schema`` (llama.cpp server)
3. Ollama's native ``/api/chat`` with ``format`` set to the schema
4. ``response_format`` of type ``json_object`` (valid JSON, but not schema-shaped)
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

REJECTED = {400, 404, 405, 415, 422, 501}
THINK_PARAMS = ("chat_template_kwargs", "reasoning_effort", "think")
CONSTRAINED_MODES = ("json_schema", "guided_json", "llama_cpp", "ollama_native", "json_object")


@dataclass
class InferConfig:
    base_url: str = "http://localhost:11434/v1"
    model: str = ""
    temperature: float = 0.0
    no_think: bool = False
    constrained: bool = False
    api_key: str | None = None
    max_tokens: int = 4096
    timeout: float = 600.0


@dataclass
class Completion:
    text: str
    raw: str
    mode: str
    seconds: float
    usage: dict[str, Any] = field(default_factory=dict)


class InferError(RuntimeError):
    pass


def clean_output(raw: str) -> str:
    """Drop ``<think>`` blocks and a surrounding markdown code fence; nothing else."""
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    text = re.sub(r"^.*?</think>", "", text, flags=re.DOTALL)  # opening tag was in the prompt
    text = text.strip()
    fence = re.match(r"^```[A-Za-z]*\s*\n(.*?)\n?```\s*$", text, flags=re.DOTALL)
    return fence.group(1).strip() if fence else text


class ChatClient:
    def __init__(
        self,
        config: InferConfig,
        schema: dict[str, Any] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.config = config
        self.schema = schema
        self._mode_index = 0
        self._think_params_ok = True
        headers = {"Authorization": f"Bearer {config.api_key or 'none'}"}
        self._http = httpx.Client(timeout=config.timeout, headers=headers, transport=transport)

    @property
    def mode(self) -> str:
        return CONSTRAINED_MODES[self._mode_index] if self.config.constrained else "free"

    def close(self) -> None:
        self._http.close()

    def complete(self, messages: list[dict[str, Any]]) -> Completion:
        if self.config.constrained and self.schema is None:
            raise InferError("--constrained needs a schema")
        messages = self._with_no_think(messages)
        started = time.monotonic()
        while True:
            mode = self.mode
            url, payload = self._request(messages, mode)
            response = self._post(url, payload)
            can_fall_back = self._mode_index < len(CONSTRAINED_MODES) - 1
            if response.status_code in REJECTED and self.config.constrained and can_fall_back:
                self._mode_index += 1
                continue
            if response.status_code >= 400:
                raise InferError(f"HTTP {response.status_code} from {url}: {response.text[:500]}")
            body = response.json()
            raw, usage = _read_body(body, mode)
            return Completion(clean_output(raw), raw, mode, time.monotonic() - started, usage)

    def _with_no_think(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.config.no_think:
            return messages
        out = [dict(m) for m in messages]
        out[-1]["content"] = f"{out[-1]['content']} /no_think"
        return out

    def _request(self, messages: list[dict[str, Any]], mode: str) -> tuple[str, dict[str, Any]]:
        cfg = self.config
        base = cfg.base_url.rstrip("/")
        if mode == "ollama_native":
            root = base.removesuffix("/v1")
            payload: dict[str, Any] = {
                "model": cfg.model,
                "messages": messages,
                "stream": False,
                "format": self.schema,
                "options": {"temperature": cfg.temperature, "num_predict": cfg.max_tokens},
            }
            if cfg.no_think:
                payload["think"] = False
            return f"{root}/api/chat", payload

        payload = {
            "model": cfg.model,
            "messages": messages,
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            "stream": False,
        }
        if mode == "json_schema":
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "scene", "schema": self.schema, "strict": True},
            }
        elif mode == "guided_json":
            payload["guided_json"] = self.schema
        elif mode == "llama_cpp":
            payload["json_schema"] = self.schema
        elif mode == "json_object":
            payload["response_format"] = {"type": "json_object"}
        if cfg.no_think and self._think_params_ok:
            payload["chat_template_kwargs"] = {"enable_thinking": False}
            payload["reasoning_effort"] = "none"
        return f"{base}/chat/completions", payload

    def _post(self, url: str, payload: dict[str, Any]) -> httpx.Response:
        response = self._http.post(url, json=payload)
        # Strict servers reject the thinking switches; retry once without them.
        if (
            response.status_code in REJECTED
            and self._think_params_ok
            and self.config.no_think
            and any(p in payload for p in THINK_PARAMS)
            and _mentions_think_param(response.text)
        ):
            self._think_params_ok = False
            payload = {k: v for k, v in payload.items() if k not in THINK_PARAMS}
            response = self._http.post(url, json=payload)
        return response


def _mentions_think_param(text: str) -> bool:
    return any(p in text for p in (*THINK_PARAMS, "enable_thinking"))


def _read_body(body: dict[str, Any], mode: str) -> tuple[str, dict[str, Any]]:
    if mode == "ollama_native":
        usage = {k: body[k] for k in ("prompt_eval_count", "eval_count") if k in body}
        return body.get("message", {}).get("content", ""), usage
    message = body["choices"][0]["message"]
    return message.get("content") or "", body.get("usage", {})
