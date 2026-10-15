"""OpenAI-compatible LLM + embedding client. Ollama locally, vLLM in production:
switching is LLM_BASE_URL / LLM_MODEL only."""

import json
import logging
import math
import time
from typing import Any

import httpx

from .audit import audit
from .config import get_settings

log = logging.getLogger("ekb.llm")

_client = httpx.Client(timeout=httpx.Timeout(150.0, connect=10.0))


def _post(path: str, payload: dict[str, Any], *, base_url: str, api_key: str = "", attempts: int = 3) -> dict[str, Any]:
    url = base_url.rstrip("/") + path
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    for i in range(attempts):
        try:
            r = _client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError):
            if i == attempts - 1:
                raise
            time.sleep(2**i)
    raise RuntimeError("unreachable")


def chat(
    messages: list[dict[str, str]],
    *,
    actor: str,
    purpose: str,
    json_mode: bool = False,
    temperature: float = 0.1,
    max_tokens: int = 1200,
) -> str:
    s = get_settings()
    payload: dict[str, Any] = {
        "model": s.llm_model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    t0 = time.perf_counter()
    data = _post("/chat/completions", payload, base_url=s.llm_base_url, api_key=s.llm_api_key)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    text = data["choices"][0]["message"]["content"] or ""
    audit(
        actor,
        "LLM_CALL",
        purpose,
        {"model": s.llm_model, "latency_ms": latency_ms, "usage": data.get("usage"), "json_mode": json_mode},
    )
    return text


def chat_json(messages: list[dict[str, str]], *, actor: str, purpose: str, max_tokens: int = 1500) -> Any:
    text = chat(messages, actor=actor, purpose=purpose, json_mode=True, max_tokens=max_tokens)
    return json.loads(text)


def _normalise(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    s = get_settings()
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = [t[:8000] for t in texts[i : i + batch_size]]
        data = _post("/embeddings", {"model": s.embed_model, "input": batch}, base_url=s.embed_base_url or s.llm_base_url)
        rows = sorted(data["data"], key=lambda d: d["index"])
        out.extend(_normalise(r["embedding"]) for r in rows)
    return out


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
