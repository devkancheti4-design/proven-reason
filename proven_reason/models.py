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

__all__ = ["Ollama", "Callable_", "FusedReasoner", "fuse", "strip_body"]


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
