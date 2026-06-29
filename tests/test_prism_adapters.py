"""Production-adapter tests against the REAL Prism packages.

Skipped (not faked) when a package isn't installed. No Gemini key needed — these
exercise projection, durable caching, and resonance wiring, not the LLM.
"""
import pytest


def test_prismlang_projector_is_deterministic():
    pytest.importorskip("prismlang")
    from prismcortex.adapters.prism import PrismLangProjector

    p = PrismLangProjector(tenant_id="test-tenant")
    assert p.dim > 0
    a = p.embed("my deploy budget is $40,000")
    b = p.embed("my deploy budget is $40,000")
    assert a == b                      # CPU-stable: same text → same vector (read-path determinism)
    assert len(a) == p.dim
    assert isinstance(p.classify("my database is postgres"), str)


def test_prismlib_cache_durable_exact_key(tmp_path):
    pytest.importorskip("prism")
    from prismcortex.adapters.prism import PrismLibCache

    db = str(tmp_path / "cache.db")
    c1 = PrismLibCache(db_path=db)
    c1.put("ans:deadbeef", "the budget is $40,000")
    assert c1.has("ans:deadbeef")
    assert c1.get("ans:deadbeef") == "the budget is $40,000"
    assert c1.get("ans:missing") is None

    c2 = PrismLibCache(db_path=db)          # cache-as-failover: survives a fresh process
    assert c2.get("ans:deadbeef") == "the budget is $40,000"


def test_prismresonance_adapter_ingests(tmp_path):
    pytest.importorskip("prismresonance")
    try:
        from prismcortex.adapters.prism import PrismLangProjector, PrismResonanceAdapter

        proj = PrismLangProjector(tenant_id="test-tenant")
        res = PrismResonanceAdapter(
            embedding_dim=proj.dim,
            state_path=str(tmp_path / "res.db"),
            onnx_path=str(tmp_path / "res.onnx"),
        )
    except Exception as exc:  # ONNX runtime / compile env not available
        pytest.skip(f"prismresonance engine unavailable in this env: {exc}")

    res.ingest("chunk_1", proj.embed("amin"), "NORMAL")
    res.reinforce("chunk_1")
    res.consolidate()       # sleep() — discrete decay heartbeat
    res.shutdown()
