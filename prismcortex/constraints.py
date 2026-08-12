"""Numeric and temporal constraint compiler for retrieval backends.

Parses natural-language queries for explicit bounds and emits JSON filters plus
PostgreSQL / pgvector-compatible ``WHERE`` fragments. Does not execute SQL —
callers bind params safely.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional


_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}


@dataclass
class NumericConstraint:
    op: str  # eq | gt | gte | lt | lte
    value: float
    field: str = "value"
    currency: bool = False


@dataclass
class TemporalConstraint:
    op: str  # eq | gt | gte | lt | lte
    value: str  # ISO date YYYY-MM-DD
    field: str = "valid_from"


@dataclass
class CompiledConstraints:
    """Structured filters for JSON APIs and parameterized SQL."""

    numeric: list[NumericConstraint] = field(default_factory=list)
    temporal: list[TemporalConstraint] = field(default_factory=list)
    raw_query: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "numeric": [
                {"field": n.field, "op": n.op, "value": n.value, "currency": n.currency}
                for n in self.numeric
            ],
            "temporal": [
                {"field": t.field, "op": t.op, "value": t.value}
                for t in self.temporal
            ],
            "query": self.raw_query,
        }

    def to_sql(self, *, table_alias: str = "m") -> tuple[str, dict[str, Any]]:
        """Return ``(where_clause, params)`` for PostgreSQL / pgvector metadata filters.

        Numeric values are read from ``(metadata->>'value')::numeric``.
        Temporal bounds use ``valid_from`` / ``valid_to`` columns when present.
        """
        clauses: list[str] = []
        params: dict[str, Any] = {}
        a = table_alias

        for i, n in enumerate(self.numeric):
            key = f"num_{i}"
            col = f"({a}.metadata->>'{n.field}')::numeric"
            clauses.append(f"{col} {_sql_op(n.op)} %({key})s")
            params[key] = n.value

        for i, t in enumerate(self.temporal):
            key = f"ts_{i}"
            col = f"{a}.{t.field}"
            clauses.append(f"{col} {_sql_op(t.op)} %({key})s::timestamptz")
            params[key] = t.value

        if not clauses:
            return "TRUE", {}
        return " AND ".join(clauses), params

    @property
    def empty(self) -> bool:
        return not self.numeric and not self.temporal


def _sql_op(op: str) -> str:
    return {"eq": "=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[op]


def _parse_number(raw: str) -> float:
    s = raw.strip().lower().replace(",", "").replace("$", "")
    mult = 1.0
    if s.endswith("k"):
        mult = 1_000.0
        s = s[:-1]
    elif s.endswith("m"):
        mult = 1_000_000.0
        s = s[:-1]
    return float(s) * mult


def _parse_date_token(text: str) -> Optional[str]:
    text = text.strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if m:
        return text
    m = re.match(
        r"^(january|february|march|april|may|june|july|august|september|october|"
        r"november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"\.?\s+(\d{1,2}),?\s+(\d{4})$",
        text,
        re.I,
    )
    if m:
        month = _MONTHS[m.group(1).lower()]
        return f"{int(m.group(3)):04d}-{month:02d}-{int(m.group(2)):02d}"
    m = re.match(
        r"^(january|february|march|april|may|june|july|august|september|october|"
        r"november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"\.?\s+(\d{4})$",
        text,
        re.I,
    )
    if m:
        month = _MONTHS[m.group(1).lower()]
        return f"{int(m.group(2)):04d}-{month:02d}-01"
    m = re.match(r"^(\d{4})$", text)
    if m:
        return f"{m.group(1)}-01-01"
    return None


class ConstraintCompiler:
    """Compile natural-language numeric/date bounds into JSON + SQL filters."""

    _BETWEEN = re.compile(
        r"\bbetween\s+\$?([\d,.]+[km]?)\s+and\s+\$?([\d,.]+[km]?)\b",
        re.I,
    )
    _CMP = re.compile(
        r"\b(?P<phrase>at\s+least|at\s+most|no\s+more\s+than|no\s+less\s+than|"
        r"greater\s+than|less\s+than|more\s+than|over|under|above|below|"
        r"exactly|=|>=|<=|>|<)\s*\$?(?P<val>[\d,.]+[km]?)\b",
        re.I,
    )
    _TEMPORAL = re.compile(
        r"\b(?P<phrase>before|after|since|until|on|from)\s+"
        r"(?P<date>\d{4}-\d{2}-\d{2}|"
        r"(?:january|february|march|april|may|june|july|august|september|october|"
        r"november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"\.?\s+\d{1,2},?\s+\d{4}|"
        r"(?:january|february|march|april|may|june|july|august|september|october|"
        r"november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
        r"\.?\s+\d{4}|\d{4})\b",
        re.I,
    )

    _PHRASE_OP = {
        "at least": "gte",
        "no less than": "gte",
        "greater than": "gt",
        "more than": "gt",
        "over": "gt",
        "above": "gt",
        "at most": "lte",
        "no more than": "lte",
        "less than": "lt",
        "under": "lt",
        "below": "lt",
        "exactly": "eq",
        "=": "eq",
        ">=": "gte",
        "<=": "lte",
        ">": "gt",
        "<": "lt",
    }

    _TEMPORAL_OP = {
        "before": "lt",
        "until": "lte",
        "after": "gt",
        "since": "gte",
        "from": "gte",
        "on": "eq",
    }

    def compile(self, query: str) -> CompiledConstraints:
        q = query or ""
        out = CompiledConstraints(raw_query=q)
        currency_hint = "$" in q or bool(re.search(r"\b(budget|usd|dollars?|cost|price)\b", q, re.I))

        for m in self._BETWEEN.finditer(q):
            lo, hi = _parse_number(m.group(1)), _parse_number(m.group(2))
            if lo > hi:
                lo, hi = hi, lo
            out.numeric.append(NumericConstraint(op="gte", value=lo, currency=currency_hint))
            out.numeric.append(NumericConstraint(op="lte", value=hi, currency=currency_hint))

        for m in self._CMP.finditer(q):
            phrase = re.sub(r"\s+", " ", m.group("phrase").lower().strip())
            op = self._PHRASE_OP.get(phrase)
            if not op:
                continue
            # Skip spans already covered by "between X and Y"
            if self._BETWEEN.search(m.group(0)):
                continue
            out.numeric.append(
                NumericConstraint(op=op, value=_parse_number(m.group("val")), currency=currency_hint)
            )

        for m in self._TEMPORAL.finditer(q):
            phrase = m.group("phrase").lower()
            iso = _parse_date_token(m.group("date"))
            if not iso:
                continue
            out.temporal.append(
                TemporalConstraint(op=self._TEMPORAL_OP[phrase], value=iso, field="valid_from")
            )

        return out

    def compile_json(self, query: str) -> dict[str, Any]:
        return self.compile(query).to_json()

    def compile_sql(self, query: str, *, table_alias: str = "m") -> tuple[str, dict[str, Any]]:
        return self.compile(query).to_sql(table_alias=table_alias)

    def filter_subgraph_labels(
        self,
        labels: list[str],
        constraints: Optional[CompiledConstraints] = None,
        *,
        query: Optional[str] = None,
    ) -> list[str]:
        """Keep labels whose embedded numbers satisfy numeric constraints (best-effort)."""
        c = constraints or (self.compile(query or "") if query else CompiledConstraints())
        if c.empty or not c.numeric:
            return list(labels)
        kept = []
        for label in labels:
            nums = [_parse_number(x) for x in re.findall(r"\$?([\d,.]+[km]?)", label)]
            if not nums:
                kept.append(label)
                continue
            if any(self._value_ok(v, c.numeric) for v in nums):
                kept.append(label)
        return kept

    @staticmethod
    def _value_ok(value: float, constraints: list[NumericConstraint]) -> bool:
        for c in constraints:
            if c.op == "eq" and value != c.value:
                return False
            if c.op == "gt" and not (value > c.value):
                return False
            if c.op == "gte" and not (value >= c.value):
                return False
            if c.op == "lt" and not (value < c.value):
                return False
            if c.op == "lte" and not (value <= c.value):
                return False
        return True


def parse_iso_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()
