"""Unit tests for CitationVerifier."""
from prismcortex.models import Evidence, Node
from prismcortex.verifier import CitationVerifier


def test_supported_claim_high_score():
    v = CitationVerifier()
    r = v.score("deploy budget is $55,000", "The deploy budget is $55,000.")
    assert r.score >= 0.7
    assert r.supported
    assert r.numeric_agree == 1.0


def test_numeric_mismatch_lowers_score():
    v = CitationVerifier()
    r = v.score("deploy budget is $40,000", "The deploy budget is $55,000.")
    assert r.numeric_agree == 0.0
    assert r.score < 0.55
    assert not r.supported


def test_unrelated_claim():
    v = CitationVerifier()
    r = v.score("primary database is Postgres", "The CEO lives on Mars.")
    assert r.score < 0.4
    assert not r.supported


def test_best_support_across_memories():
    v = CitationVerifier()
    memories = [
        "primary database is Postgres",
        "deploy budget is $55,000",
        "CA parental leave is 12 weeks",
    ]
    r = v.best_support(memories, "Our deploy budget is $55,000")
    assert "55,000" in r.memory_span or "55000" in r.memory_span.replace(",", "")
    assert r.supported


def test_accepts_node_and_evidence():
    v = CitationVerifier()
    node = Node(id="n1", label="deploy budget is $40,000", embedding=[0.1])
    ev = Evidence(fact="deploy budget is $40,000")
    assert v.score(node, "deploy budget is $40,000").supported
    assert v.score(ev, "deploy budget is $40,000").supported


def test_empty_memories():
    r = CitationVerifier().verify([], "anything")
    assert r.score == 0.0
    assert not r.supported
