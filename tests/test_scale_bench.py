"""Quick scale regression — ANN path stays accurate on small graphs."""
from benchmarks.scale_bench import run_benchmark


def test_ann_scale_200_facts():
    r = run_benchmark([200, 1000], use_ann=True, ann_threshold=500, sample=50, k=8)
    last = r["levels"][-1]
    assert last["hit_at_k"] >= 0.9
    assert last["retrieve_p95_ms"] < 20
