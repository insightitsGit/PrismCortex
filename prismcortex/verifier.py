"""Runtime citation verifier — non-LLM entailment score between memory and claims."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Union

# Soft import types — callers may pass Node labels, Evidence.fact, or plain strings.
try:
    from .models import Evidence, Node
except ImportError:  # pragma: no cover
    Node = object  # type: ignore
    Evidence = object  # type: ignore


_STOP = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "to", "of", "in", "on", "for", "and", "or", "our", "my", "your", "we",
    "it", "its", "this", "that", "with", "as", "at", "by", "from",
})


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9$%./-]+", (text or "").lower()) if t not in _STOP]


def _numbers(text: str) -> list[float]:
    out: list[float] = []
    for m in re.findall(r"\$?([\d,]+(?:\.\d+)?)\s*([km])?", text or "", flags=re.I):
        raw, suffix = m
        try:
            val = float(raw.replace(",", ""))
        except ValueError:
            continue
        if suffix.lower() == "k":
            val *= 1_000
        elif suffix.lower() == "m":
            val *= 1_000_000
        out.append(val)
    return out


def _memory_text(item: Union[str, "Node", "Evidence", object]) -> str:
    if isinstance(item, str):
        return item
    if hasattr(item, "fact"):
        return str(getattr(item, "fact") or "")
    if hasattr(item, "label"):
        return str(getattr(item, "label") or "")
    return str(item)


@dataclass
class VerificationResult:
    score: float  # 0.0 .. 1.0
    supported: bool
    claim_coverage: float
    numeric_agree: float
    memory_span: str
    details: str = ""


class CitationVerifier:
    """Low-latency, non-LLM check: does cited memory support a generated statement?

    Score blends (1) content-word coverage of the claim by the memory span and
    (2) numeric consistency when both sides mention numbers. Threshold default 0.55.
    """

    def __init__(self, *, threshold: float = 0.55) -> None:
        self.threshold = threshold

    def score(
        self,
        memory: Union[str, "Node", "Evidence", object],
        statement: str,
    ) -> VerificationResult:
        mem = _memory_text(memory)
        claim = statement or ""
        mem_toks = set(_tokens(mem))
        claim_toks = _tokens(claim)

        if not claim_toks:
            return VerificationResult(
                score=1.0 if not mem else 0.0,
                supported=not bool(mem),
                claim_coverage=1.0,
                numeric_agree=1.0,
                memory_span=mem,
                details="empty claim",
            )

        covered = sum(1 for t in claim_toks if t in mem_toks)
        coverage = covered / len(claim_toks)

        mem_nums = _numbers(mem)
        claim_nums = _numbers(claim)
        if claim_nums and mem_nums:
            # Best match within 1% relative or $1 absolute.
            agrees = 0
            for cn in claim_nums:
                if any(abs(cn - mn) <= max(1.0, 0.01 * abs(cn)) for mn in mem_nums):
                    agrees += 1
            numeric = agrees / len(claim_nums)
        elif claim_nums and not mem_nums:
            numeric = 0.0
        else:
            numeric = 1.0  # no numeric claim to falsify

        # Coverage dominates; numeric veto when claim asserts numbers.
        if claim_nums:
            score = 0.55 * coverage + 0.45 * numeric
        else:
            score = coverage

        score = round(max(0.0, min(1.0, score)), 4)
        return VerificationResult(
            score=score,
            supported=score >= self.threshold,
            claim_coverage=round(coverage, 4),
            numeric_agree=round(numeric, 4),
            memory_span=mem,
            details=f"covered={covered}/{len(claim_toks)}",
        )

    def best_support(
        self,
        memories: Sequence[Union[str, "Node", "Evidence", object]],
        statement: str,
    ) -> VerificationResult:
        if not memories:
            return VerificationResult(
                score=0.0,
                supported=False,
                claim_coverage=0.0,
                numeric_agree=0.0,
                memory_span="",
                details="no memories",
            )
        results = [self.score(m, statement) for m in memories]
        return max(results, key=lambda r: r.score)

    def verify(
        self,
        memories: Iterable[Union[str, "Node", "Evidence", object]],
        statement: str,
    ) -> VerificationResult:
        return self.best_support(list(memories), statement)
