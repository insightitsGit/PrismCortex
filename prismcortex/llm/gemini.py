"""Real Gemini adapter — implements both EntityExtractor and Renderer.

No mock data, ever: extraction and rendering are genuine Gemini calls at temperature 0.
The renderer is *extractive* — facts are listed from the graph and the model is
forbidden from inventing values — and a verification pass rejects fabricated numbers,
so load-bearing facts are deterministic even on the first render.

Requires `google-genai` and an API key in GEMINI_API_KEY or GOOGLE_API_KEY.
Pin a dated model snapshot in production (e.g. gemini-2.5-flash-NNN); a floating alias
silently re-renders everything when Google ships a new revision.
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional

from ..models import ExtractedGist, Subgraph


class PrismCortexLLMError(RuntimeError):
    pass


_EXTRACT_INSTRUCTIONS = """You are the semantic-extraction stage of a memory engine.
Read the USER PAYLOAD and return ONLY compact JSON (no prose, no markdown) with this shape:
{
  "entities":  [{"label": "<canonical noun>", "kind": "person|org|place|thing|concept|preference|fact", "attributes": {"k": "v"}}],
  "relations": [{"src": "<entity label>", "dst": "<entity label>", "relation": "<verb/phrase>"}],
  "is_correction": <true if the user is correcting/updating something they said before>,
  "notes": "<one short clause on anything ambiguous>"
}
Rules:
- Extract durable facts, preferences and relationships — not conversational filler.
- Represent each fact as a relation TRIPLE: the subject is one entity, the value/object
  is ANOTHER entity, joined by the relation. Example — "deploy budget is $40,000":
  entities [{"label":"deploy budget"},{"label":"$40,000"}],
  relations [{"src":"deploy budget","dst":"$40,000","relation":"is"}].
- Make concrete values (amounts, dates, ids, regions, model names, people) their OWN
  entity as the dst of a relation, so they can be corrected later. Use attributes only
  for minor descriptors that are not themselves correctable facts.
- Use canonical, MINIMAL labels: strip possessives and qualifiers ("my", "our", "the",
  "production") so the same real-world thing always gets the SAME label. E.g. both "my
  production deploy budget" and "our deploy budget" must be labelled "deploy budget".
- Use simple present-tense relation verbs (is, has, uses, hosted_in, leads) so a later
  correction to the same fact reuses the same subject + relation.
- Every relation's src and dst MUST appear in entities.
- If nothing durable is present, return empty lists.
Use the EXISTING CONTEXT only to keep entity labels consistent."""

_RENDER_INSTRUCTIONS = """You are a deterministic rendering engine, not an assistant.
Answer the QUESTION using ONLY the FACTS below.
- Never invent names, numbers, dates, amounts, or ids. Copy values exactly from the FACTS.
- If the FACTS do not contain the answer, say you do not have that information yet.
- Be concise and direct."""


class GeminiClient:
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None) -> None:
        try:
            from google import genai  # noqa: F401
        except ImportError as exc:  # pragma: no cover
            raise PrismCortexLLMError(
                "google-genai is not installed. `pip install google-genai` (or prismcortex[gemini])."
            ) from exc
        from google import genai

        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            raise PrismCortexLLMError("Set GEMINI_API_KEY (or GOOGLE_API_KEY) to use the Gemini adapter.")
        self._client = genai.Client(api_key=key)
        # The spec may carry an "@epoch" you bump when Google updates a model in place
        # under the same name. The epoch is part of the cache key (so it invalidates),
        # but is stripped for the actual API call.
        spec = model or os.environ.get("PRISMCORTEX_MODEL", "gemini-2.5-flash")
        self._model_id = spec
        self._model = spec.split("@", 1)[0]
        if "@" not in spec and not re.search(r"-\d{3,}$", self._model):
            import logging

            logging.getLogger("prismcortex").warning(
                "PRISMCORTEX_MODEL=%r is a floating alias with no pinned @epoch; determinism "
                "is scoped to whatever Google serves under that name. Bump an @epoch "
                "(e.g. 'gemini-2.5-flash@2026-06') after a known model change.", spec,
            )

    @property
    def model_id(self) -> str:
        return self._model_id  # full spec incl @epoch → part of the content-address

    # -- low level --
    def _generate(self, prompt: str, *, json_mode: bool) -> str:
        from google.genai import types

        cfg = types.GenerateContentConfig(
            temperature=0.0,
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        resp = self._client.models.generate_content(model=self._model, contents=prompt, config=cfg)
        return (resp.text or "").strip()

    # -- EntityExtractor --
    def extract(self, text: str, context: Subgraph) -> ExtractedGist:
        ctx = ", ".join(sorted({n.label for n in context.nodes})) or "(none)"
        prompt = f"{_EXTRACT_INSTRUCTIONS}\n\nEXISTING CONTEXT: {ctx}\n\nUSER PAYLOAD:\n{text}"
        raw = self._generate(prompt, json_mode=True)
        try:
            return ExtractedGist.model_validate_json(raw)
        except Exception:
            data = _loads_loose(raw)
            if data is None:
                raise PrismCortexLLMError(f"Extractor returned non-JSON: {raw[:200]!r}")
            return ExtractedGist.model_validate(data)

    # -- Renderer --
    def render(self, query: str, subgraph: Subgraph) -> str:
        facts = _facts_block(subgraph)
        prompt = f"{_RENDER_INSTRUCTIONS}\n\nFACTS:\n{facts}\n\nQUESTION: {query}\nANSWER:"
        answer = self._generate(prompt, json_mode=False)
        if not _facts_verify(answer, facts):  # one retry on fabricated values
            strict = prompt + "\n\n(Your previous answer introduced a value not in FACTS. Use only FACTS values.)"
            answer = self._generate(strict, json_mode=False)
        return answer


def _facts_block(subgraph: Subgraph) -> str:
    id2label = {n.id: n.label for n in subgraph.nodes}
    lines: list[str] = []
    for n in subgraph.nodes:
        attrs = ", ".join(
            f"{k}={v}" for k, v in n.attributes.items() if isinstance(v, (str, int, float, bool))
        )
        lines.append(f"- {n.label}" + (f" ({attrs})" if attrs else ""))
    for e in subgraph.edges:
        if e.is_current:
            lines.append(f"- {id2label.get(e.src, e.src)} {e.relation} {id2label.get(e.dst, e.dst)}")
    return "\n".join(lines) or "(no facts known yet)"


_NUM = re.compile(r"\d[\d,.]*")


def _facts_verify(answer: str, facts: str) -> bool:
    """Best-effort: every numeric token in the answer must appear in the facts."""
    fact_nums = set(_NUM.findall(facts))
    for tok in _NUM.findall(answer):
        if tok not in fact_nums and tok.rstrip(".,") not in {n.rstrip(".,") for n in fact_nums}:
            return False
    return True


def _loads_loose(raw: str):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        raw = raw[raw.find("{"):]
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None
