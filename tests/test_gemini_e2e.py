"""End-to-end tests with REAL Gemini (no mocks).

Skipped — not faked — when no API key is present, so the suite stays green offline
while never substituting random/mock data for a real model call.

Run with:  GEMINI_API_KEY=...  pytest tests/test_gemini_e2e.py -v
"""
import os

import pytest

from prismcortex import DigestOutcome, reference_memory

pytestmark = pytest.mark.skipif(
    not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")),
    reason="No GEMINI_API_KEY / GOOGLE_API_KEY — real-Gemini e2e tests skipped (not mocked).",
)


@pytest.fixture
def mem(tmp_path):
    return reference_memory(cache_path=str(tmp_path / "cache.json"))


def test_digest_then_recall_returns_the_fact(mem):
    mem.digest("My production deploy budget is $40,000.")
    res = mem.recall("What is my deploy budget?")
    assert "40" in res.answer
    assert res.cache_hit is False


def test_recall_is_byte_identical_on_replay(mem):
    mem.digest("My production deploy budget is $40,000.")
    first = mem.recall("What is my deploy budget?")
    second = mem.recall("What is my deploy budget?")
    assert second.cache_hit is True
    assert first.answer == second.answer            # determinism by construction
    assert first.subgraph_hash == second.subgraph_hash


def test_correction_changes_answer_and_keeps_history(mem):
    mem.digest("My production deploy budget is $40,000.")
    before = mem.recall("What is my deploy budget?")
    mem.digest("Correction: my deploy budget is now $55,000.")  # ALERT → fast-track
    after = mem.recall("What is my deploy budget?")
    assert "55" in after.answer
    assert after.answer != before.answer            # changed graph → changed answer
    # old fact preserved for time-travel/audit
    hist = [e for e in mem.store.all_edges()]
    assert any(e.valid_to is not None for e in hist)


def test_identical_input_is_idempotent(mem):
    first = mem.digest("My favorite database is Postgres.")
    second = mem.digest("My favorite database is Postgres.")
    assert second.outcome is DigestOutcome.SKIPPED  # memoized write path


def test_low_salience_is_skipped_without_llm(mem):
    res = mem.digest("ok thanks")
    assert res.outcome is DigestOutcome.SKIPPED
