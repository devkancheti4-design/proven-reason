# Copyright 2026 Devi Eswar Kancheti
# Licensed under the Apache License, Version 2.0. See LICENSE.
"""models — fuse the reasoner with ANY model.

A "model" here is anything that maps a prompt string to a reply string. Three
ready-made ways in, pick one:

    from proven_reason.models import Ollama, Callable_, fuse

    body = Ollama("qwen2.5-coder:7b")          # any local ollama model
    body = Callable_(my_function)              # any prompt -> str function
    body = Callable_(lambda p: openai_call(p)) # any API, wrapped in a lambda

    rz = fuse(body)                            # a Reasoner wearing that model
    out = rz.ask("divide x by two the way C does", "return x / 2;")
    out.outcome                                # PASS | FIX | REFUSE
    out.code                                   # proven code, or None

The model supplies the linguistic surface. The authored decisions supply the
judgment. The compiler supplies the truth. Swap the model freely — the other
two never change, which is the point: **the guarantee does not depend on
which model you fuse.** Measured across two batteries: four different local
models, 41 wrong answers raw between them, zero shipped once fused.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Callable, Optional

from .reasoner import Gated, Reasoner

__all__ = ["Ollama", "Anthropic", "OpenAICompat", "Callable_",
           "FusedReasoner", "fuse", "strip_body"]


def strip_body(reply: str) -> str:
    """Extract a C function body from a model reply: drop markdown fences,
    drop a signature if the model added one despite instructions."""
    t = (reply or "").strip()
    if "```" in t:
        parts = [p for p in t.split("```") if p.strip()]
        if parts:
            t = parts[0]
            for pre in ("c\n", "C\n", "c\r\n"):
                if t.startswith(pre):
                    t = t[len(pre):]
    t = t.replace("```", "").strip()
    if t.startswith(("int ", "long long ", "unsigned ")) and "{" in t:
        i, j = t.find("{"), t.rfind("}")
        if j > i:
            t = t[i + 1:j]
    return t.strip()


class Ollama:
    """Any model served by a local ollama instance. No key, no network
    beyond localhost, no cost per token.

        Ollama("qwen2.5-coder:7b")     # ollama pull qwen2.5-coder:7b
        Ollama("llama3:8b", host="http://localhost:11434")
    """

    def __init__(self, name: str, host: str = "http://localhost:11434",
                 timeout: float = 180.0, temperature: float = 0.0):
        self.name, self.host = name, host.rstrip("/")
        self.timeout, self.temperature = timeout, temperature

    def __call__(self, prompt: str) -> Optional[str]:
        req = urllib.request.Request(
            self.host + "/api/generate",
            data=json.dumps({"model": self.name, "prompt": prompt,
                             "stream": False,
                             "options": {"temperature": self.temperature}}
                            ).encode(),
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.load(r)["response"]
        except Exception as ex:                          # noqa: BLE001
            raise RuntimeError(
                "could not reach ollama at %s (%s). Install: "
                "https://ollama.com — then `ollama pull %s`."
                % (self.host, ex, self.name)) from ex


class Callable_:
    """Wrap any prompt -> str function: an API client, another process,
    a different framework. If it talks, it can be fused."""

    def __init__(self, fn: Callable[[str], str], name: str = "callable"):
        self.fn, self.name = fn, name

    def __call__(self, prompt: str) -> Optional[str]:
        return self.fn(prompt)


class Anthropic:
    """Any Claude model via the Anthropic API. Bring your own key:

        export ANTHROPIC_API_KEY=sk-ant-...
        Anthropic("claude-opus-5")        # or claude-fable-5, claude-sonnet-5

    The fuse does not care that the model is frontier-class: its answer goes
    through the same sweep as a 7B's, and PASSes only if it is right on every
    input. In the sealed duel a frontier model shipped 5 wrong answers of 13
    graded; gated, those would have been repairs and refusals instead."""

    def __init__(self, model: str = "claude-opus-5",
                 api_key: Optional[str] = None, timeout: float = 120.0,
                 max_tokens: int = 512):
        import os as _os
        self.model = model
        self.key = api_key or _os.environ.get("ANTHROPIC_API_KEY")
        self.timeout, self.max_tokens = timeout, max_tokens

    def __call__(self, prompt: str) -> Optional[str]:
        if not self.key:
            raise RuntimeError(
                "no API key: set ANTHROPIC_API_KEY or pass api_key=. "
                "(Local models via Ollama need no key at all.)")
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps({
                "model": self.model, "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }).encode(),
            headers={"Content-Type": "application/json",
                     "x-api-key": self.key,
                     "anthropic-version": "2023-06-01"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.load(r)
        return "".join(b.get("text", "") for b in out.get("content", []))


class OpenAICompat:
    """Any OpenAI-compatible endpoint: OpenAI itself, Groq, Together, vLLM,
    LM Studio, llama.cpp server — anything speaking /v1/chat/completions.

        OpenAICompat("gpt-4o", api_key=..., base_url="https://api.openai.com")
        OpenAICompat("local-model", base_url="http://localhost:8000")  # vLLM
    """

    def __init__(self, model: str, api_key: Optional[str] = None,
                 base_url: str = "https://api.openai.com",
                 timeout: float = 120.0):
        import os as _os
        self.model = model
        self.key = api_key or _os.environ.get("OPENAI_API_KEY")
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def __call__(self, prompt: str) -> Optional[str]:
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        req = urllib.request.Request(
            self.base + "/v1/chat/completions",
            data=json.dumps({"model": self.model, "temperature": 0,
                             "messages": [{"role": "user",
                                           "content": prompt}]}).encode(),
            headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.load(r)
        return out["choices"][0]["message"]["content"]


_PROMPT = ("Write the body of a C function `int f(int x)` that does this:\n"
           "%s\n\nReply with ONLY the body — the statements including "
           "`return`. No signature, no explanation, no markdown fences.")


class FusedReasoner:
    """A Reasoner wearing a model. `ask` goes ticket -> gated, proven code."""

    def __init__(self, model, reasoner: Optional[Reasoner] = None):
        self.model = model
        self.reasoner = reasoner or Reasoner()

    def ask(self, ticket: str, reference: str) -> Gated:
        """The full loop: the model proposes, the sweep judges, the shelf or
        the engine repairs, refusal ships nothing. `reference` is a C body
        defining what you actually want — the sweep needs a definition of
        correct; nothing honest can be proven against vibes."""
        reply = self.model(_PROMPT % ticket)
        candidate = strip_body(reply) if reply else None
        if not candidate:
            candidate = "return x;"      # forces the repair path honestly
        return self.reasoner.gate(candidate, reference)

    def verify(self, candidate: str, reference: str) -> Gated:
        """Skip the model; gate code you already have."""
        return self.reasoner.gate(candidate, reference)


def fuse(model, **kw) -> FusedReasoner:
    """One call: fuse(Ollama("qwen2.5-coder:7b")) -> a gated model."""
    return FusedReasoner(model, Reasoner(**kw) if kw else None)
