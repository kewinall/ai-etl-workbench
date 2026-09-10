from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


SUPPORTED_EXTENSIONS = {".ktr", ".kjb", ".hpl", ".hwf"}
MAX_SOURCE_BYTES = 5 * 1024 * 1024
SECRET_TAGS = {"password", "passwd", "pwd", "secret", "token", "access_token"}

SOURCE_TYPES = {
    "TableInput", "CsvInput", "TextFileInput", "ExcelInput", "JsonInput",
    "XMLInputStream", "GetFileNames", "KafkaConsumerInput",
}
TARGET_TYPES = {
    "TableOutput", "InsertUpdate", "Delete", "TextFileOutput", "ExcelOutput",
    "JsonOutput", "XMLJoin", "KafkaProducerOutput",
}
LOGIC_TYPES = {
    "FilterRows": "FILTER", "MergeJoin": "JOIN", "JoinRows": "JOIN",
    "DatabaseLookup": "LOOKUP", "StreamLookup": "LOOKUP", "GroupBy": "AGGREGATION",
    "MemoryGroupBy": "AGGREGATION", "Calculator": "CALCULATION", "Formula": "CALCULATION",
    "SelectValues": "FIELD_MAPPING", "StringOperations": "FIELD_MAPPING",
    "ModifiedJavaScriptValue": "CUSTOM_SCRIPT", "UserDefinedJavaClass": "CUSTOM_SCRIPT",
    "ExecSQL": "SQL", "ExecuteSQLScript": "SQL", "SQL": "SQL",
}


class AnalyzerError(ValueError):
    pass


def discover_files(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    if not root.is_dir():
        return []
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append({
                "path": path.relative_to(root).as_posix(),
                "name": path.name,
                "extension": path.suffix.lower(),
                "size": path.stat().st_size,
                "project": path.relative_to(root).parts[0] if len(path.relative_to(root).parts) > 1 else "root",
            })
    return files


def resolve_source(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    candidate = (root / relative_path.replace("/", "\\")).resolve()
    if root != candidate and root not in candidate.parents:
        raise AnalyzerError("檔案路徑超出 ETL Analyzer 掃描目錄")
    if not candidate.is_file():
        raise AnalyzerError("找不到指定的 ETL 檔案")
    if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise AnalyzerError("只支援 .ktr、.kjb、.hpl、.hwf")
    if candidate.stat().st_size > MAX_SOURCE_BYTES:
        raise AnalyzerError("單一 ETL 檔案不可超過 5 MB")
    return candidate


def _text(element: ET.Element, *paths: str) -> str:
    for path in paths:
        value = element.findtext(path)
        if value and value.strip():
            return value.strip()
    return ""


def _redacted_xml(root: ET.Element) -> str:
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag in SECRET_TAGS and node.text:
            node.text = "***REDACTED***"
    return ET.tostring(root, encoding="unicode")


def _sql_tables(sql: str) -> list[str]:
    if not sql:
        return []
    pattern = r'(?is)\b(?:from|join|update|into)\s+((?:["\w$]+\.)?["\w$]+)'
    return sorted({m.group(1).replace('"', "") for m in re.finditer(pattern, sql)})


def _sql_field_rules(sql: str) -> list[dict[str, Any]]:
    match = re.search(r"(?is)\bselect\s+(.*?)\s+from\b", sql)
    if not match:return []
    parts, current, depth = [], [], 0
    for char in match.group(1):
        depth += 1 if char == '(' else -1 if char == ')' else 0
        if char == ',' and depth == 0:parts.append(''.join(current).strip());current=[]
        else:current.append(char)
    if current:parts.append(''.join(current).strip())
    rules=[]
    for expression in parts:
        alias_match=re.search(r'(?is)\s+as\s+"?([\w$]+)"?\s*$',expression) or re.search(r'(?is)\s+"?([\w$]+)"?\s*$',expression)
        target=alias_match.group(1) if alias_match else expression.split('.')[-1].strip(' "')
        columns=[f"{a}.{b}" for a,b in re.findall(r'\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b',expression)]
        if not columns and re.fullmatch(r'"?[A-Za-z_]\w*"?',expression.strip()):columns=[expression.strip(' "')]
        rules.append({'target_column':target,'source_columns':sorted(set(columns)),'expression':expression,'confidence':'MEDIUM' if not columns else 'HIGH'})
    return rules


def _condition_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    parts = []
    for item in node.iter():
        if item.tag.rsplit("}", 1)[-1].lower() in {"leftvalue", "function", "rightvalue", "value", "operator"}:
            value = (item.text or "").strip()
            if value:
                parts.append(value)
    return " ".join(parts[:30])


def _field_rules(item: ET.Element, node_type: str) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if node_type == "TableInput":
        rules.extend(_sql_field_rules(_text(item,"sql","SQL","query")))
    elif node_type == "SelectValues":
        for field in item.findall("fields/field"):
            source = _text(field, "name")
            target = _text(field, "rename") or source
            if source:
                rules.append({"target_column": target, "source_columns": [source], "expression": "RENAME" if target != source else "DIRECT", "confidence": "HIGH"})
    elif node_type == "Calculator":
        for field in item.findall("calculation"):
            target = _text(field, "field_name")
            sources = [_text(field, name) for name in ("field_a", "field_b", "field_c")]
            rules.append({"target_column": target, "source_columns": [x for x in sources if x], "expression": _text(field, "calc_type") or "CALCULATION", "confidence": "HIGH"})
    elif node_type == "Formula":
        for field in item.findall("formula"):
            formula = _text(field, "formula_string")
            rules.append({"target_column": _text(field, "field_name"), "source_columns": re.findall(r"\[([^]]+)\]", formula), "expression": formula, "confidence": "HIGH"})
    elif node_type in {"GroupBy", "MemoryGroupBy"}:
        for field in item.findall("group/field"):
            name = _text(field, "name")
            if name: rules.append({"target_column": name, "source_columns": [name], "expression": "GROUP_BY", "confidence": "HIGH"})
        for field in item.findall("fields/field"):
            target, source = _text(field, "aggregate"), _text(field, "subject", "valuefield")
            if target: rules.append({"target_column": target, "source_columns": [source] if source else [], "expression": _text(field, "type") or "AGGREGATE", "confidence": "HIGH"})
    elif node_type == "TableOutput":
        for field in item.findall("fields/field"):
            source, target = _text(field, "stream_name", "name"), _text(field, "column_name", "name")
            if source or target: rules.append({"target_column": target or source, "source_columns": [source] if source else [], "expression": "TARGET_MAPPING", "confidence": "HIGH"})
    elif node_type in {"DatabaseLookup", "StreamLookup"}:
        for field in item.findall("return/returnvalue") + item.findall("returnvalue"):
            source, target = _text(field, "name", "field"), _text(field, "rename", "new_name")
            if source: rules.append({"target_column": target or source, "source_columns": [source], "expression": "LOOKUP", "confidence": "MEDIUM"})
    return [rule for rule in rules if rule.get("target_column")]


def _node_detail(item: ET.Element, node_type: str) -> dict[str, Any]:
    sql = _text(item, "sql", "SQL", "query")
    schema = _text(item, "schema", "schema_name")
    table = _text(item, "table", "tablename", "table_name")
    filename = _text(item, "filename", "file/name", "file_name")
    dependency = _text(item, "filename", "file_name", "transname", "jobname")
    detail: dict[str, Any] = {}
    if sql:
        detail["sql"] = sql
        detail["sql_tables"] = _sql_tables(sql)
    if table:
        detail["table"] = f"{schema}.{table}" if schema else table
    if filename:
        detail["file"] = filename
    if dependency and node_type.lower() in {"trans", "job", "pipeline", "workflow"}:
        detail["dependency"] = dependency
    if node_type in {"FilterRows", "Filter"}:
        detail["condition"] = _condition_text(item.find(".//condition"))
    detail["field_rules"] = _field_rules(item, node_type)
    return detail


def _parse_nodes(root: ET.Element, process_type: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if process_type == "pipeline":
        elements = root.findall("step") or root.findall("transform")
    else:
        elements = root.findall("entries/entry") or root.findall("actions/action") or root.findall("action")
    nodes = []
    for index, item in enumerate(elements, 1):
        node_type = _text(item, "type", "plugin_id", "typeid") or "Unknown"
        name = _text(item, "name") or f"Unnamed {index}"
        gui = item.find("GUI")
        nodes.append({
            "id": name,
            "name": name,
            "type": node_type,
            "sequence": index,
            "x": int(_text(gui, "xloc") or 0) if gui is not None else 0,
            "y": int(_text(gui, "yloc") or 0) if gui is not None else 0,
            "detail": _node_detail(item, node_type),
        })
    hops_parent = root.find("order") if process_type == "pipeline" else root.find("hops")
    hops = []
    if hops_parent is not None:
        for hop in hops_parent.findall("hop"):
            source, target = _text(hop, "from"), _text(hop, "to")
            if source and target:
                hops.append({"from": source, "to": target, "enabled": _text(hop, "enabled").upper() != "N", "evaluation": _text(hop, "evaluation")})
    return nodes, hops


def _classify(nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    sources, targets, logic, dependencies = [], [], [], []
    for node in nodes:
        node_type = node["type"]
        detail = node["detail"]
        tables = detail.get("sql_tables", [])
        if node_type in SOURCE_TYPES or "Input" in node_type:
            sources.append({"node": node["name"], "type": node_type, "objects": tables or [detail.get("table") or detail.get("file")]})
        if node_type in TARGET_TYPES or "Output" in node_type:
            targets.append({"node": node["name"], "type": node_type, "objects": [detail.get("table") or detail.get("file")]})
        category = LOGIC_TYPES.get(node_type)
        if category:
            logic.append({"node": node["name"], "type": node_type, "category": category, "detail": detail})
        if detail.get("dependency"):
            dependencies.append(detail["dependency"])
    for group in (sources, targets):
        for item in group:
            item["objects"] = [value for value in item["objects"] if value]
    return sources, targets, logic, sorted(set(dependencies))


def _parameters(root: ET.Element) -> list[dict[str, str]]:
    result = []
    for node in root.findall(".//parameters/parameter") + root.findall(".//parameter"):
        name = _text(node, "name")
        if name and name not in {item["name"] for item in result}:
            result.append({"name": name, "default": _text(node, "default_value", "default"), "description": _text(node, "description")})
    return result


def analyze_file(path: Path, scan_root: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise AnalyzerError("基於安全考量，不接受包含 DTD 或 ENTITY 的 XML")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise AnalyzerError(f"ETL XML 格式錯誤：{exc}") from exc
    extension = path.suffix.lower()
    process_type = "pipeline" if extension in {".ktr", ".hpl"} else "workflow"
    platform = "PENTAHO" if extension in {".ktr", ".kjb"} else "APACHE_HOP"
    name = _text(root, "info/name", "name", "info/name_sync_with_filename") or path.stem
    nodes, hops = _parse_nodes(root, process_type)
    sources, targets, logic, dependencies = _classify(nodes)
    column_lineage = []
    for node in nodes:
        for rule in node["detail"].get("field_rules", []):
            column_lineage.append({"node": node["name"], "node_type": node["type"], **rule})
    warnings = []
    unknown = sorted({node["type"] for node in nodes if node["type"] == "Unknown"})
    custom = [node["name"] for node in nodes if LOGIC_TYPES.get(node["type"]) == "CUSTOM_SCRIPT"]
    if unknown:
        warnings.append({"code": "UNKNOWN_COMPONENT", "message": "部分元件無法辨識", "items": unknown})
    if custom:
        warnings.append({"code": "CUSTOM_SCRIPT_REVIEW", "message": "自訂程式邏輯需要人工或 AI Review", "items": custom})
    if not nodes:
        warnings.append({"code": "NO_NODES", "message": "檔案中沒有找到可解析的處理節點", "items": []})
    summary = f"{name} 是一個 {platform} {'Pipeline' if process_type == 'pipeline' else 'Workflow'}，包含 {len(nodes)} 個節點與 {len(hops)} 條流程連線。"
    if sources or targets:
        summary += f" 已辨識 {len(sources)} 個來源節點、{len(targets)} 個目標節點與 {len(logic)} 段主要處理邏輯。"
    relative = path.resolve().relative_to(scan_root.resolve()).as_posix()
    return {
        "schema_version": "1.0",
        "process": {"name": name, "type": process_type, "platform": platform, "source_file": relative},
        "nodes": nodes,
        "edges": hops,
        "sources": sources,
        "targets": targets,
        "logic": logic,
        "column_lineage": column_lineage,
        "dependencies": dependencies,
        "parameters": _parameters(root),
        "variables": sorted(set(re.findall(r"\$\{([^}]+)\}", raw.decode("utf-8", errors="replace")))),
        "warnings": warnings,
        "summary": summary,
        "checksum": hashlib.sha256(raw).hexdigest(),
        "source_size": len(raw),
        "redacted_source": _redacted_xml(root),
    }
