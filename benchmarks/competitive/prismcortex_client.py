"""Mem0-compatible async client backed by PrismCortex reference_memory.

Used by the mem0ai/memory-benchmarks runner (monkeypatched in place of Mem0Client).
Retrieval returns graph facts as memory strings — same pipeline Mem0 uses before
the answerer LLM (search → answer → judge).
"""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path
from typing import Any

from prismcortex import reference_memory
from prismcortex.engine import Memory

_CACHE_ROOT = Path(".prismcortex_bench_cache")


class PrismCortexClient:
    """Drop-in async replacement for benchmarks.common.mem0_client.Mem0Client."""

    def __init__(self, mode: str = "oss", **_: Any):
        self.mode = "prismcortex"
        self._memories: dict[str, Memory] = {}
        self._ingest_counts: dict[str, int] = {}
        self._ingest_limit = int(os.environ.get("PRISM_BENCH_INGEST_LIMIT", "0") or "0")
        _CACHE_ROOT.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        self._memories.clear()

    async def __aenter__(self) -> PrismCortexClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    def _memory(self, user_id: str) -> Memory:
        if user_id not in self._memories:
            user_dir = _CACHE_ROOT / user_id.replace("/", "_")
            user_dir.mkdir(parents=True, exist_ok=True)
            self._memories[user_id] = reference_memory(cache_path=str(user_dir / "render.json"))
        return self._memories[user_id]

    async def add(
        self,
        messages: list[dict[str, str]],
        user_id: str,
        observation_date: str | None = None,
        timestamp: int | None = None,
        custom_instructions: str | None = None,
        metadata: dict | None = None,
    ) -> dict | None:
        mem = self._memory(user_id)
        loop = asyncio.get_running_loop()
        results: list[dict[str, str]] = []
        for msg in messages:
            if self._ingest_limit and self._ingest_counts.get(user_id, 0) >= self._ingest_limit:
                break
            content = (msg.get("content") or "").strip()
            if not content:
                continue
            await loop.run_in_executor(None, mem.digest, content)
            self._ingest_counts[user_id] = self._ingest_counts.get(user_id, 0) + 1
            results.append({"memory": content[:500], "event": "ADD"})
        return {"results": results}

    async def search(
        self,
        query: str,
        user_id: str,
        top_k: int = 200,
        rerank: bool = False,
        score_debug: bool = False,
    ) -> list[dict]:
        mem = self._memory(user_id)
        loop = asyncio.get_running_loop()
        k = max(top_k, 8)

        def _retrieve() -> list[dict]:
            emb = mem.projector.embed(query)
            subgraph = mem._expand_subgraph(mem.store.retrieve(emb, k=k), query)
            id2label = {n.id: n.label for n in subgraph.nodes}
            id2weight = {n.id: n.weight for n in subgraph.nodes}
            out: list[dict] = []
            rank = 0
            for e in subgraph.edges:
                if not e.is_current:
                    continue
                rank += 1
                fact = f"{id2label.get(e.src, e.src)} {e.relation} {id2label.get(e.dst, e.dst)}"
                w = id2weight.get(e.src, e.weight)
                score = max(0.01, 1.0 - (rank - 1) * 0.005) * min(1.0, 0.5 + w * 0.05)
                entry: dict[str, Any] = {
                    "memory": fact,
                    "score": round(score, 4),
                    "id": e.id,
                }
                if score_debug:
                    entry["score_debug"] = {"combined_score": score, "rank": rank}
                out.append(entry)
            if not out:
                ex = mem.explain(query)
                for i, ev in enumerate(ex.evidence):
                    out.append({
                        "memory": ev.fact,
                        "score": round(max(0.01, ev.confidence - i * 0.01), 4),
                        "id": f"ev_{i}",
                    })
            out.sort(key=lambda x: x["score"], reverse=True)
            return out[:top_k]

        return await loop.run_in_executor(None, _retrieve)

    async def delete_user(self, user_id: str) -> bool:
        self._memories.pop(user_id, None)
        user_dir = _CACHE_ROOT / user_id.replace("/", "_")
        if user_dir.exists():
            shutil.rmtree(user_dir, ignore_errors=True)
        return True

    async def get_user_profile(self, user_id: str) -> dict | None:
        return None
