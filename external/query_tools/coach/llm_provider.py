"""Provider-agnostic LLM adapter (OpenAI + Anthropic)."""

from __future__ import print_function

import json
import os

try:
    from urllib import request as urllib_request
except ImportError:
    import urllib2 as urllib_request  # type: ignore


def _provider():
    p = os.environ.get("VRE_LLM_PROVIDER", "").lower()
    if p:
        return p
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return ""


def _model(default_openai="gpt-4o-mini", default_anthropic="claude-sonnet-4-20250514"):
    return os.environ.get("VRE_LLM_MODEL") or (
        default_anthropic if _provider() == "anthropic" else default_openai
    )


def complete(system, user, temperature=0.35):
    provider = _provider()
    if provider == "anthropic":
        return _anthropic_complete(system, user, temperature)
    if provider == "openai":
        return _openai_complete(system, user, temperature)
    return None


def _openai_complete(system, user, temperature):
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return None
    body = json.dumps({
        "model": _model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")
    req = urllib_request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
        },
    )
    resp = urllib_request.urlopen(req, timeout=90)
    payload = json.loads(resp.read().decode("utf-8"))
    return payload["choices"][0]["message"]["content"]


def _anthropic_complete(system, user, temperature):
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None
    body = json.dumps({
        "model": _model(),
        "max_tokens": 2048,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "temperature": temperature,
    }).encode("utf-8")
    req = urllib_request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    resp = urllib_request.urlopen(req, timeout=90)
    payload = json.loads(resp.read().decode("utf-8"))
    blocks = payload.get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    return text
