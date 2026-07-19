# PrismCortex 0.3.0 — correction events for PrismShine

## MemoryEvent / `on_event`

```python
from prismcortex import MemoryEvent, MemoryEventKind

unsub = mem.on_event(callback)   # Callable[[MemoryEvent], None] -> Unsubscribe
unsub()                          # remove subscriber
```

### `MemoryEvent` schema

| Field | Type | Notes |
|-------|------|-------|
| `kind` | `"accommodate" \| "conflict_opened" \| "conflict_resolved" \| "forget"` | |
| `subject` | `str \| None` | Entity label |
| `relation` | `str \| None` | |
| `old_value` | `str \| None` | Pre-correction / prior contested value |
| `new_value` | `str \| None` | |
| `valid_from` | `datetime` | |
| `source_event_id` | `str \| None` | Provenance `source_id` or forget target |
| `tenant_id` | `str \| None` | Memory tenant |

Dispatch is **synchronous**. Callback exceptions are logged and swallowed. One sleep
ACCOMMODATE emits both `accommodate` and `conflict_resolved`.

### MeshBroadcast

**Not** required on the Protocol. Optional duck-type: if `mesh.broadcast_event(event)`
exists (as on `InProcessMesh`), it is called after local subscribers.

## Evidence correction metadata (additive)

`Evidence` now includes `valid_from`, `supersedes_prior`, `prior_value` (defaults keep
existing clients compatible). Current-edge-only explain semantics unchanged.

## Packaging

```toml
prism      = [..., "prismlib>=0.5.0", ...]
prism-plus = [..., "prismlib-plus>=0.8.0", ...]  # mutually exclusive with prism
```
