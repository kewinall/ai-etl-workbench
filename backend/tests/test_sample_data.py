import pytest
from pathlib import Path

from app.sample_data import _rows, _vertica_type


def test_materialize_only_sources_without_actual_data(tmp_path, monkeypatch):
    import app.sample_data as sample_data
    monkeypatch.setattr(sample_data, "ROOT", tmp_path)
    actual = tmp_path / "actual.csv"; actual.write_text("id\n1\n", encoding="utf-8")
    result = sample_data.materialize_samples("TASK-MIXED", {"sources": [
        {"id": "a", "type": "CSV", "alias": "actual", "has_actual_data": True, "path": str(actual)},
        {"id": "b", "type": "CSV", "alias": "generated", "has_actual_data": False,
         "fields": [{"name": "code", "type": "VARCHAR(20)"}]},
    ]})
    assert result["sources"][0]["path"] == str(actual)
    assert result["sources"][1]["path"].endswith("source_2.csv")
    assert Path(result["sources"][1]["path"]).is_file()


def test_generated_rows_follow_declared_fields():
    fields=[{"name":"sale_id","type":"INT"},{"name":"order_date","type":"DATE"},{"name":"amount","type":"NUMERIC(18,2)"}]
    rows=_rows(fields,10)
    assert len(rows)==10
    assert rows[0]["sale_id"]==1001
    assert rows[0]["order_date"]=="2026-01-01"


def test_unsafe_type_is_rejected():
    with pytest.raises(ValueError):_vertica_type("VARCHAR(10); DROP TABLE x")
