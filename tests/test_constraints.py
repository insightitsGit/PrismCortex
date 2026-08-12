"""Unit tests for ConstraintCompiler."""
from prismcortex.constraints import ConstraintCompiler


def test_numeric_over_budget():
    c = ConstraintCompiler().compile("budgets over $50,000")
    assert len(c.numeric) == 1
    assert c.numeric[0].op == "gt"
    assert c.numeric[0].value == 50_000
    assert c.numeric[0].currency is True


def test_between_and_at_least():
    c = ConstraintCompiler().compile("leave between 8 and 12 weeks, at least 10")
    ops = {(n.op, n.value) for n in c.numeric}
    assert ("gte", 8.0) in ops
    assert ("lte", 12.0) in ops
    assert ("gte", 10.0) in ops


def test_k_suffix():
    c = ConstraintCompiler().compile("cost under 40k")
    assert c.numeric[0].op == "lt"
    assert c.numeric[0].value == 40_000


def test_temporal_before_iso():
    c = ConstraintCompiler().compile("policies before 2026-01-01")
    assert len(c.temporal) == 1
    assert c.temporal[0].op == "lt"
    assert c.temporal[0].value == "2026-01-01"


def test_temporal_since_month_year():
    c = ConstraintCompiler().compile("facts since March 2025")
    assert c.temporal[0].op == "gte"
    assert c.temporal[0].value == "2025-03-01"


def test_json_and_sql_shape():
    compiled = ConstraintCompiler().compile("spend over $10k before 2026-06-01")
    js = compiled.to_json()
    assert js["numeric"][0]["op"] == "gt"
    assert js["temporal"][0]["value"] == "2026-06-01"
    where, params = compiled.to_sql(table_alias="m")
    assert "::numeric" in where
    assert "valid_from" in where
    assert params["num_0"] == 10_000
    assert params["ts_0"] == "2026-06-01"


def test_empty_query():
    c = ConstraintCompiler().compile("what is our leave policy?")
    assert c.empty
    where, params = c.to_sql()
    assert where == "TRUE"
    assert params == {}


def test_filter_subgraph_labels():
    cc = ConstraintCompiler()
    constraints = cc.compile("budgets over $45,000")
    kept = cc.filter_subgraph_labels(
        ["deploy budget is $40,000", "deploy budget is $55,000", "Postgres"],
        constraints,
    )
    assert "deploy budget is $55,000" in kept
    assert "deploy budget is $40,000" not in kept
    assert "Postgres" in kept  # non-numeric kept
