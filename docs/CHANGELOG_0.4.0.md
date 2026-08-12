# PrismCortex 0.4.0 — constraints, sanitizer, citation verifier

## ConstraintCompiler (`prismcortex.constraints`)

Parses natural-language queries for numeric / temporal bounds and emits:

- JSON filter dicts (`compile_json`)
- Parameterized PostgreSQL / pgvector `WHERE` fragments (`compile_sql`)

```python
from prismcortex import ConstraintCompiler
c = ConstraintCompiler().compile("budgets over $50k before 2026-01-01")
c.to_json()
c.to_sql()
```

## CorpusSanitizer (`prismcortex.sanitizer`)

Strips prompt-injection / jailbreak payloads from memory strings before they enter
a model context (`[IGNORE PREVIOUS]`, role markers, DAN, prompt exfil, …).

## CitationVerifier (`prismcortex.verifier`)

Non-LLM 0..1 entailment score between recalled memory spans (`Node` labels /
`Evidence.fact` / strings) and a generated statement. Numeric consistency is checked
when both sides cite amounts.

## Memory.recall hooks

Optional (defaults: sanitize + extract constraints on; verify off):

| Flag | Default | Effect |
|------|---------|--------|
| `sanitize_retrieval` | `True` | Sanitize node labels in a subgraph copy before render |
| `extract_constraints` | `True` | Attach `RecallResult.constraints` JSON |
| `verify_citations` | `False` | Attach `RecallResult.citation_score` |

Additive `RecallResult` fields: `constraints`, `citation_score`, `sanitized`.

## Known gaps (documented, not claimed done)

| Topic | Status |
|-------|--------|
| Multi-modal / tabular sanitization | Future — see [ROADMAP](../ROADMAP.md#post-040-edge-cases-future-releases) |
| Pinecone / Qdrant / Milvus filter adapters | Future — pgvector SQL path works today |
