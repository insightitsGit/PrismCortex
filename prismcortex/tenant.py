"""Multi-tenant memory isolation — one Memory (graph + cache + staging) per tenant."""
from __future__ import annotations

import os
import threading

from .engine import Memory


class TenantMemoryManager:
    """Builds and caches isolated Memory instances keyed by tenant_id + region."""

    def __init__(self, data_dir: str, backend: str, *, use_ann: bool = True) -> None:
        self._data_dir = data_dir
        self._backend = backend
        self._use_ann = use_ann
        self._memories: dict[str, Memory] = {}
        self._generations: dict[str, int] = {}
        self._llms: dict[str, object] = {}
        self._lock = threading.Lock()

    def _key(self, tenant_id: str, region: str) -> str:
        return f"{region}:{tenant_id}"

    def peek(self, tenant_id: str, region: str = "default"):
        key = self._key(tenant_id, region)
        with self._lock:
            if key in self._memories:
                return self._memories[key], self._llms[key]
        return None, None

    def generation(self, tenant_id: str, region: str = "default") -> int:
        return self._generations.get(self._key(tenant_id, region), 0)

    def reset(self, tenant_id: str, region: str = "default") -> None:
        key = self._key(tenant_id, region)
        with self._lock:
            mem = self._memories.pop(key, None)
            if mem is not None and hasattr(mem.resonance, "shutdown"):
                try:
                    mem.resonance.shutdown()
                except Exception:  # noqa: BLE001
                    pass
            self._generations[key] = self._generations.get(key, 0) + 1
            self._llms.pop(key, None)

    def get(self, tenant_id: str, region: str = "default") -> tuple[Memory, object]:
        key = self._key(tenant_id, region)
        with self._lock:
            if key in self._memories:
                return self._memories[key], self._llms[key]
            mem, llm = self._build(tenant_id, region)
            self._memories[key] = mem
            self._llms[key] = llm
            return mem, llm

    def _build(self, tenant_id: str, region: str) -> tuple[Memory, object]:
        from .adapters.prism import PrismLibCache
        from .adapters.reference import InProcessMesh, ListStaging
        from .server_helpers import CountingGemini

        key = self._key(tenant_id, region)
        gen = self._generations.get(key, 0)
        tenant_dir = os.path.join(self._data_dir, "tenants", region, tenant_id)
        os.makedirs(tenant_dir, exist_ok=True)

        llm = CountingGemini(model=os.environ.get("PRISMCORTEX_MODEL"))
        cache = PrismLibCache(db_path=os.path.join(tenant_dir, f"cache_{gen}.db"))

        if self._backend == "prism":
            from .adapters.prism import PrismLangProjector, PrismResonanceAdapter

            projector = PrismLangProjector(tenant_id=f"{tenant_id}:{region}")
            resonance = PrismResonanceAdapter(
                embedding_dim=projector.dim,
                state_path=os.path.join(tenant_dir, f"resonance_{gen}.db"),
                onnx_path=os.path.join(self._data_dir, "resonance_engine.onnx"),
            )
        else:
            from .adapters.reference import HashingProjector, InProcessResonance

            projector = HashingProjector(dim=384)
            resonance = InProcessResonance()

        if self._use_ann:
            from .adapters.ann import AnnGraphStore
            store = AnnGraphStore(tenant_id=tenant_id)
        else:
            from .adapters.reference import InMemoryGraphStore
            store = InMemoryGraphStore()

        mem = Memory(
            projector=projector,
            extractor=llm,
            renderer=llm,
            store=store,
            resonance=resonance,
            cache=cache,
            mesh=InProcessMesh(),
            staging=ListStaging(),
            tenant_id=tenant_id,
        )
        return mem, llm
