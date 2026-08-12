# AI / LLM context — PrismCortex

> Concise reference for humans and coding assistants.
> Do not invent APIs beyond this file and the package/repo source.
> Package: **`prismcortex` 0.4.1** · Import: **`prismcortex`**

---

## 10-sentence project summary

1. Deterministic, auditable, self-consolidating memory for AI agents (byte-identical replay, bitemporal audit).
2. Primary users: Regulated teams needing compliance-grade agent memory, not a chat-log vector store.
3. Core problem: Chat-log / SaaS memory fails audit, correction, and residency requirements.
4. Install/use from the repository README — do not invent extra CLI flags here.
5. Key surface: from prismcortex import reference_memory  # see README / DESIGN.md
6. Compared with: vector chat logs · hosted memory SaaS · plain Postgres notes.
7. When NOT to use: You only need ephemeral chat history with no audit requirements.
8. Read architecture.md for stack placement.
9. Prefer facts from README / existing docs over marketing inference.
10. If an API is not listed in README or source, assume it does not exist.

---

## Core concepts

See README for product-specific terms. Keep terminology consistent with that file.

---

## Key APIs

```
from prismcortex import reference_memory  # see README / DESIGN.md
```

---

## Common use cases

- Chat-log / SaaS memory fails audit, correction, and residency requirements.
- See README examples and any `examples/` folder in the repo.

---

## Migration guidance

Start from the closest tool in: vector chat logs · hosted memory SaaS · plain Postgres notes. Follow README install and examples. Do not invent migration scripts that are not in the repo.

---

## Limitations / when NOT to use

- You only need ephemeral chat history with no audit requirements.
- Do not invent capabilities beyond README and source.

---

## Frequently compared projects

| Notes |
|-------|
| vector chat logs · hosted memory SaaS · plain Postgres notes |

---

## Links

- [ai-overview.md](ai-overview.md) · [llm-context.md](llm-context.md) · [architecture.md](architecture.md)
- ../README.md
