from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request


def json_post(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url=url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} {exc.reason}: {details}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Request failed: {exc.reason}") from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON response: {raw[:500]}") from exc


def call_ollama(
    model: str,
    prompt: str,
    host: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "top_p": top_p,
            "num_predict": max_tokens,
        },
    }
    data = json_post(
        url=f"{host.rstrip('/')}/api/generate",
        payload=payload,
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    return (data.get("response") or "").strip()


def call_openai_chat(
    model: str,
    prompt: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    data = json_post(
        url="https://api.openai.com/v1/chat/completions",
        payload=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        timeout=timeout,
    )
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"OpenAI returned no choices: {data}")
    content = choices[0].get("message", {}).get("content", "")
    return (content or "").strip()


def call_model(
    model_name: str,
    prompt: str,
    ollama_host: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    timeout: int,
) -> str:
    lower = model_name.lower()
    if lower.startswith("gpt-"):
        return call_openai_chat(
            model=model_name,
            prompt=prompt,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    return call_ollama(
        model=model_name,
        prompt=prompt,
        host=ollama_host,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        timeout=timeout,
    )
