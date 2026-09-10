from app.requirement_engine import canonicalize, plan, requirement_gate


def task(requirement="join orders and customers"):
    return {"name": "complex", "requirement": requirement,
            "target_config": {"type": "VERTICA", "schema": "etl", "table": "result"}}


def test_missing_join_is_blocking():
    profile = {"sources": [{"id": "a", "type": "VERTICA"}, {"id": "b", "type": "CSV"}], "issues": []}
    spec = canonicalize({}, task(), profile)
    gate = requirement_gate(task(), spec, profile)
    assert gate["status"] == "NEEDS_INPUT"
    assert gate["issues"][0]["field"] == "joins"


def test_mixed_complex_plan_stages_files_in_vertica():
    profile = {"sources": [{"id": "a", "type": "VERTICA"}, {"id": "b", "type": "EXCEL"}], "issues": []}
    spec = canonicalize({"joins": [{"left": "a", "right": "b", "join_type": "left", "conditions": ["a.id=b.id"]}]}, task(), profile)
    result = plan(spec)
    assert result["execution_plan"]["strategy"] == "VERTICA_STAGING_AND_SQL_PUSHDOWN"
    assert result["execution_plan"]["staging_required"] is True


def test_regression_requires_review_even_when_complete():
    profile = {"sources": [{"id": "a", "type": "VERTICA"}], "issues": []}
    analytics = {"type": "linear_regression", "target": "y", "features": ["x"], "train_range": "2025",
                 "split": "80/20", "metrics": ["rmse"], "model_name": "m", "purpose": "forecast"}
    spec = canonicalize({"analytics": [analytics]}, task("run regression"), profile)
    assert requirement_gate(task("run regression"), spec, profile)["status"] == "REVIEW_REQUIRED"
