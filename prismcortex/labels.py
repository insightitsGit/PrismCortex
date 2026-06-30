"""Label normalization and lightweight entity matching helpers.

Used by the engine and graph store so paraphrased subjects ("the deploy budget" vs
"deploy budget") and relation wording drift ("is scheduled for" vs "scheduled for")
do not fork facts or miss conflicts.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_WORD = re.compile(r"[a-z0-9]+")
_CANON_PREFIX = re.compile(r"^(?:(?:the|my|our|their|its|a|an)\s+)+", re.I)

_REL_STOP = frozenset({
    "is", "are", "the", "a", "an", "of", "for", "to", "at", "in", "on", "was",
    "were", "be", "been", "has", "have", "had", "by", "with", "as", "now",
})

_MONTHS = frozenset({
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
})


def canonical_label(label: str) -> str:
    """Strip leading articles/possessives so the same entity gets one label key."""
    s = label.strip()
    while True:
        m = _CANON_PREFIX.match(s)
        if not m:
            break
        s = s[m.end():].strip()
    return s.lower() or label.strip().lower()


def content_tokens(text: str) -> set[str]:
    return {t for t in _WORD.findall(text.lower()) if t not in _REL_STOP}


def token_overlap(a: str, b: str) -> float:
    """Jaccard overlap on content tokens — 1.0 for identical, 0.0 for disjoint."""
    ta, tb = content_tokens(a), content_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def norm_relation(relation: str) -> str:
    toks = [t for t in _WORD.findall(relation.lower()) if t not in _REL_STOP]
    return " ".join(toks) or relation.strip().lower()


def relations_compatible(a: str, b: str) -> bool:
    """True when two relation phrasings likely describe the same fact slot."""
    na, nb = norm_relation(a), norm_relation(b)
    if na == nb:
        return True
    ta, tb = content_tokens(na), content_tokens(nb)
    return bool(ta and tb and (ta & tb))


def looks_like_correctable_value(label: str) -> bool:
    """Dates, amounts, durations, and other facts that get corrected over time."""
    s = label.strip().lower()
    if any(c.isdigit() for c in s):
        return True
    if s in _MONTHS:
        return True
    if re.search(r"\b\d+\s*(?:sec|second|min|minute|hour|day|week|month|year)s?\b", s):
        return True
    if s.startswith(("$", "€", "£")):
        return True
    return False


_alias_to_canon: dict[str, dict[str, str]] = {}
_canon_aliases: dict[str, dict[str, set[str]]] = {}


def register_alias(canonical: str, alias: str, *, tenant_id: str = "default") -> None:
    canon = canonical_label(canonical)
    al = alias.strip().lower()
    _alias_to_canon.setdefault(tenant_id, {})[al] = canon
    _canon_aliases.setdefault(tenant_id, {}).setdefault(canon, set()).add(al)


def resolve_alias(label: str, *, tenant_id: str = "default") -> str:
    key = label.strip().lower()
    mapped = _alias_to_canon.get(tenant_id, {}).get(key)
    if mapped:
        return mapped
    return canonical_label(label)


def aliases_snapshot(*, tenant_id: str = "default") -> dict[str, list[str]]:
    return {k: sorted(v) for k, v in _canon_aliases.get(tenant_id, {}).items()}


def load_aliases(path: str, *, tenant_id: str = "default") -> None:
    p = Path(path)
    if not p.exists():
        return
    for canon, aliases in json.loads(p.read_text(encoding="utf-8")).items():
        for al in aliases:
            register_alias(canon, al, tenant_id=tenant_id)


def save_aliases(path: str, *, tenant_id: str = "default") -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(aliases_snapshot(tenant_id=tenant_id), indent=2), encoding="utf-8")
