from pathlib import Path

import pytest

from app.etl_analyzer import AnalyzerError, analyze_file, discover_files, resolve_source


KTR = """<transformation>
<info><name>LOAD_CUSTOMER</name><parameters><parameter><name>RUN_DATE</name><default_value>2026-01-01</default_value></parameter></parameters></info>
<step><name>Read customer</name><type>TableInput</type><sql>SELECT id, amount FROM ods.customer WHERE active='Y'</sql><GUI><xloc>10</xloc><yloc>20</yloc></GUI></step>
<step><name>Only valuable</name><type>FilterRows</type><condition><leftvalue>amount</leftvalue><function>&gt;</function><rightvalue>100</rightvalue></condition></step>
<step><name>Write customer</name><type>TableOutput</type><schema>dw</schema><table>dim_customer</table><password>must-not-leak</password></step>
<order><hop><from>Read customer</from><to>Only valuable</to><enabled>Y</enabled></hop><hop><from>Only valuable</from><to>Write customer</to><enabled>Y</enabled></hop></order>
</transformation>"""


def test_analyze_pentaho_transformation(tmp_path: Path):
    source = tmp_path / "load_customer.ktr"
    source.write_text(KTR, encoding="utf-8")
    result = analyze_file(source, tmp_path)
    assert result["process"] == {"name": "LOAD_CUSTOMER", "type": "pipeline", "platform": "PENTAHO", "source_file": "load_customer.ktr"}
    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2
    assert result["sources"][0]["objects"] == ["ods.customer"]
    assert result["targets"][0]["objects"] == ["dw.dim_customer"]
    assert {x["category"] for x in result["logic"]} == {"FILTER"}
    assert result["parameters"][0]["name"] == "RUN_DATE"
    assert any(x["target_column"] == "dim_customer" or x["node"] == "Write customer" for x in result["column_lineage"]) is False
    assert "must-not-leak" not in result["redacted_source"]
    assert "***REDACTED***" in result["redacted_source"]


def test_discovery_and_path_safety(tmp_path: Path):
    (tmp_path / "a.kjb").write_text("<job><name>A</name></job>", encoding="utf-8")
    (tmp_path / "ignore.txt").write_text("x", encoding="utf-8")
    assert [x["path"] for x in discover_files(tmp_path)] == ["a.kjb"]
    with pytest.raises(AnalyzerError):
        resolve_source(tmp_path, "../outside.ktr")


def test_rejects_dtd(tmp_path: Path):
    source = tmp_path / "unsafe.ktr"
    source.write_text('<!DOCTYPE x [<!ENTITY a "x">]><transformation/>', encoding="utf-8")
    with pytest.raises(AnalyzerError):
        analyze_file(source, tmp_path)
