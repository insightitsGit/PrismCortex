"""Lightweight request tracing — structured spans without a heavy OTEL dependency.

Each request gets a trace_id; engine operations emit span events into JSON logs.
Set PRISMCORTEX_TRACE=1 (default on) to enable.
"""
from __future__ import annotations

import contextvars
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

_TRACE_ON = os.environ.get("PRISMCORTEX_TRACE", "1") != "0"
_current: contextvars.ContextVar[Optional["Trace"]] = contextvars.ContextVar("trace", default=None)


@dataclass
class Span:
    name: str
    start: float
    end: Optional[float] = None
    attrs: dict[str, Any] = field(default_factory=dict)

    @property
    def ms(self) -> float:
        end = self.end or time.perf_counter()
        return round((end - self.start) * 1000, 2)

    def finish(self, **attrs: Any) -> None:
        self.end = time.perf_counter()
        self.attrs.update(attrs)


@dataclass
class Trace:
    trace_id: str
    spans: list[Span] = field(default_factory=list)

    def span(self, name: str, **attrs: Any) -> Span:
        s = Span(name=name, start=time.perf_counter(), attrs=dict(attrs))
        self.spans.append(s)
        return s

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "spans": [{"name": s.name, "ms": s.ms, **s.attrs} for s in self.spans],
        }


def start_trace(trace_id: Optional[str] = None) -> Trace:
    t = Trace(trace_id=trace_id or uuid.uuid4().hex[:16])
    _current.set(t)
    return t


def current_trace() -> Optional[Trace]:
    return _current.get()


def trace_enabled() -> bool:
    return _TRACE_ON


class traced:
    """Context manager: ``with traced("digest"): ...``"""

    def __init__(self, name: str, **attrs: Any) -> None:
        self.name = name
        self.attrs = attrs
        self.span: Optional[Span] = None

    def __enter__(self) -> Span:
        tr = _current.get()
        if tr is None or not _TRACE_ON:
            self.span = Span(name=self.name, start=time.perf_counter())
            return self.span
        self.span = tr.span(self.name, **self.attrs)
        return self.span

    def __exit__(self, *exc) -> None:
        if self.span:
            self.span.finish()
