"""Retrieval corpus sanitizer — strip prompt-injection payloads before LLM context."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Optional


@dataclass
class SanitizeResult:
    text: str
    redacted: bool = False
    matched_patterns: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.redacted


class CorpusSanitizer:
    """Rule/regex sanitizer for memory strings entering a model context window."""

    # (name, pattern, replacement) — replacement may be empty (strip) or a marker.
    DEFAULT_RULES: list[tuple[str, re.Pattern[str], str]] = [
        (
            "ignore_previous",
            re.compile(
                r"\[\s*ignore\s+previous(?:\s+instructions?)?\s*\]|"
                r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b|"
                r"\bdisregard\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b",
                re.I,
            ),
            "",
        ),
        (
            "system_override",
            re.compile(
                r"\[\s*system\s*\]|"
                r"<\s*/?\s*system\s*>|"
                r"\bsystem\s*:\s*you\s+are\b|"
                r"\boverride\s+system\s+prompt\b",
                re.I,
            ),
            "",
        ),
        (
            "role_markers",
            re.compile(
                r"<\|?\s*(?:im_start|im_end|system|assistant|user)\s*\|?>|"
                r"\[/?INST\]|"
                r"<<\s*SYS\s*>>|<<\s*/\s*SYS\s*>>",
                re.I,
            ),
            "",
        ),
        (
            "dan_jailbreak",
            re.compile(
                r"\bdo\s+anything\s+now\b|\bDAN\s+mode\b|"
                r"\bjailbreak\b|\bdeveloper\s+mode\s+enabled\b",
                re.I,
            ),
            "",
        ),
        (
            "prompt_exfil",
            re.compile(
                r"\b(?:reveal|show|print|dump)\s+(?:your\s+)?(?:system\s+)?prompt\b|"
                r"\brepeat\s+(?:your\s+)?instructions\b",
                re.I,
            ),
            "",
        ),
        (
            "new_instructions",
            re.compile(
                r"\bnew\s+instructions?\s*:|"
                r"\bfrom\s+now\s+on\s*,?\s*you\s+(?:must|will|shall)\b|"
                r"\byou\s+are\s+now\s+(?:DAN|unrestricted|jailbroken|"
                r"an?\s+(?:AI|LLM|assistant|chatbot)\b)",
                re.I,
            ),
            "",
        ),
        (
            "hidden_payload_tags",
            re.compile(
                r"<\s*(?:!--)?\s*(?:ADMIN|SECRET|INJECT|PAYLOAD)\b[^>]*>|"
                r"```\s*(?:system|prompt)\b[\s\S]*?```",
                re.I,
            ),
            "",
        ),
    ]

    def __init__(self, *, extra_rules: Optional[list[tuple[str, str, str]]] = None) -> None:
        self._rules = list(self.DEFAULT_RULES)
        if extra_rules:
            for name, pattern, repl in extra_rules:
                self._rules.append((name, re.compile(pattern, re.I | re.M), repl))

    def sanitize(self, text: str) -> SanitizeResult:
        if not text:
            return SanitizeResult(text="")
        out = text
        matched: list[str] = []
        for name, pattern, repl in self._rules:
            if pattern.search(out):
                matched.append(name)
                out = pattern.sub(repl, out)
        # Collapse whitespace left by stripping.
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = re.sub(r"\n{3,}", "\n\n", out).strip()
        return SanitizeResult(text=out, redacted=bool(matched), matched_patterns=matched)

    def sanitize_many(self, texts: Iterable[str]) -> list[SanitizeResult]:
        return [self.sanitize(t) for t in texts]

    def is_suspicious(self, text: str) -> bool:
        return self.sanitize(text).redacted
