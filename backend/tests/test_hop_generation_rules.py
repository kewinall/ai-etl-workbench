from pathlib import Path

from app.execution import build_hpl, static_validate


def test_vertica_complex_query_pushdown(tmp_path):
    task={"id":"TEST-VERTICA-JOIN","source":"MIXED","source_config":{"query":"SELECT 1 AS value","output_fields":["value"],"sources":[{"type":"VERTICA"}]},"target":"VERTICA","target_config":{"type":"VERTICA","schema":"public","table":"result"},"requirement":"join"}
    artifact=build_hpl(task,["value"])
    assert artifact["sql_pushdown"] is True
    assert artifact["transforms"] == ["TableInput","TableOutput"]
    assert static_validate(artifact)["valid"] is True
from app.hop_generation_rules import generation_plan


def csv_task(tmp_path: Path, aggregation=None):
    config = {"file_path": str(tmp_path / "input.csv"), "encoding": "UTF-8", "delimiter": ","}
    if aggregation:
        config["aggregation"] = aggregation
    return {
        "id": "rule-test",
        "source": "CSV",
        "source_config": config,
        "target": "POSTGRESQL",
        "target_config": {"type": "POSTGRESQL", "schema": "public", "table": "result"},
    }


def test_generation_plan_selects_proven_aggregation_pattern(tmp_path):
    task = csv_task(tmp_path, {
        "group_by": "category",
        "calculation": {"name": "amount", "field_a": "price", "field_b": "quantity"},
        "sum_fields": [{"name": "total_amount", "subject": "amount"}],
    })
    plan = generation_plan(task)
    assert plan["pattern"] == "csv-filter-calculate-sort-group-output"
    assert plan["components"][-3:] == ["SortRows", "GroupBy", "TableOutput"]


def test_generated_aggregation_passes_corpus_graph_rules(tmp_path, monkeypatch):
    import app.execution as execution

    monkeypatch.setattr(execution, "ROOT", tmp_path)
    task = csv_task(tmp_path, {
        "group_by": "category",
        "calculation": {"name": "amount", "field_a": "price", "field_b": "quantity"},
        "sum_fields": [{"name": "total_amount", "subject": "amount"}],
    })
    artifact = build_hpl(task, ["category", "price", "quantity"])
    result = static_validate(artifact)
    assert result["valid"], result["errors"]
    assert result["generation_plan"]["catalog"].startswith("transfer-project-2085")


def test_aggregate_csv_date_field_uses_iso_format(tmp_path, monkeypatch):
    import app.execution as execution

    monkeypatch.setattr(execution, "ROOT", tmp_path)
    task = csv_task(tmp_path, {
        "group_by": "category",
        "calculation": {"name": "amount", "field_a": "price", "field_b": "quantity"},
        "sum_fields": [{"name": "total_amount", "subject": "amount"}],
    })
    task["source_config"]["field_types"] = {"order_date": "Date"}
    artifact = build_hpl(task, ["category", "price", "quantity", "order_date"])
    xml = Path(artifact["path"]).read_text(encoding="utf-8")
    assert "<name>order_date</name><type>Date</type><format>yyyy-MM-dd</format>" in xml


def test_module_aggregation_generates_parent_and_mapping_pipeline(tmp_path, monkeypatch):
    import app.execution as execution

    monkeypatch.setattr(execution, "ROOT", tmp_path)
    task = csv_task(tmp_path, {
        "group_by": "category",
        "calculation": {"name": "amount", "field_a": "price", "field_b": "quantity"},
        "sum_fields": [{"name": "total_amount", "subject": "amount"}],
    })
    task["source_config"]["module"] = True
    artifact = build_hpl(task, ["category", "price", "quantity"])
    parent = Path(artifact["path"]).read_text(encoding="utf-8")
    module = Path(artifact["module_path"]).read_text(encoding="utf-8")
    assert "<type>SimpleMapping</type>" in parent
    assert "<type>MappingInput</type>" in module
    assert "<type>Calculator</type>" in module
    assert "<type>MappingOutput</type>" in module
    assert static_validate(artifact)["valid"]


def test_group_by_without_sort_is_rejected(tmp_path):
    path = tmp_path / "invalid.hpl"
    path.write_text("""<pipeline><order><hop><from>Read</from><to>Group</to></hop></order>
    <transform><name>Read</name><type>TableInput</type></transform>
    <transform><name>Group</name><type>GroupBy</type></transform>
    <transform><name>Write</name><type>TableOutput</type></transform></pipeline>""", encoding="utf-8")
    result = static_validate({"path": str(path), "columns": ["id"]})
    assert not result["valid"]
    assert any("sorted input" in error for error in result["errors"])


def test_stage_external_generates_safe_hwf(tmp_path, monkeypatch):
    import app.execution as execution
    monkeypatch.setattr(execution, "ROOT", tmp_path)
    task = {"id": "TASK-EXT", "category": "STAGE", "source": "CSV",
            "source_config": {"sources": [{"type": "CSV", "fields": [{"name": "id", "type": "BIGINT"}]}]},
            "target": "VERTICA", "target_config": {"type": "VERTICA", "schema": "stage", "table": "ext_demo",
                "stage_mode": "EXTERNAL", "data_path": "/DBExternal/stage/demo_*.csv",
                "reject_path": "/DBExternal/reject", "exception_path": "/DBExternal/exception",
                "delimiter": ",", "quote": '"', "header": True}}
    artifact = execution.build_hpl(task, ["id"])
    assert artifact["artifact_type"] == "HWF"
    assert "CREATE EXTERNAL TABLE" in artifact["sql"]
    assert "SKIP 1" in artifact["sql"]
    assert execution.static_validate(artifact)["valid"]


def test_stage_flex_generates_copy_parser_hwf(tmp_path, monkeypatch):
    import app.execution as execution
    monkeypatch.setattr(execution, "ROOT", tmp_path)
    task = {"id": "TASK-FLEX", "category": "STAGE", "source": "CSV",
            "source_config": {"sources": [{"type": "CSV", "fields": [{"name": "event", "type": "VARCHAR(255)"}]}]},
            "target": "VERTICA", "target_config": {"type": "VERTICA", "schema": "stage", "table": "flex_demo",
                "stage_mode": "FLEX", "format": "JSON", "data_path": "/DBExternal/flex/*.json",
                "reject_path": "/DBExternal/reject", "exception_path": "/DBExternal/exception"}}
    artifact = execution.build_hpl(task, ["event"])
    assert "CREATE FLEX TABLE" in artifact["sql"]
    assert "PARSER fjsonparser()" in artifact["sql"]
    assert execution.static_validate(artifact)["valid"]
