"""Salience gate — the cheap novelty check that runs *before* the expensive extraction.

Biology gates encoding on novelty/urgency (the amygdala) instead of recording every
moment. We do the same: low-value turns ("ok thanks") never trigger an LLM extraction
call, and high-urgency turns fast-track straight to consolidation. This is the
difference between a demo and something with a sane per-turn cost.

These are deterministic heuristics — no randomness, no model call. A production build
can replace this with prismresonance's FrequencyFamily classifier behind the same
function signature.
"""
from __future__ import annotations

from .models import Band

_URGENCY = (
    "urgent", "asap", "critical", "emergency", "immediately", "right now",
    "breaking", "alert", "deadline", "outage", "down ", "failure",
)
_CORRECTION = (
    "actually", "correction", "i meant", "not ", "no, ", "wrong", "instead",
    "update ", "change ", "rather ", "should be", "is now",
)
_LOW_VALUE = frozenset({
    "ok", "okay", "k", "thanks", "thank you", "thx", "cool", "nice", "great",
    "got it", "sure", "yes", "no", "yep", "nope", "hi", "hello", "hey", "bye",
    "lol", "haha", "good", "fine",
})


def assess(text: str) -> Band:
    """Classify a payload's salience band. Cheap, deterministic, runs on every turn."""
    t = " ".join(text.lower().split())
    if not t:
        return Band.ARCHIVE
    if t.rstrip("!.") in _LOW_VALUE:
        return Band.ARCHIVE
    if len(t.split()) <= 2:
        return Band.NEUTRAL
    if any(w in t for w in _URGENCY):
        return Band.EMERGENCY
    if any(w in t for w in _CORRECTION):
        return Band.ALERT
    return Band.NORMAL
