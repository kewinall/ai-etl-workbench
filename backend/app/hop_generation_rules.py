"""Generation policy distilled from 2,085 converted Pentaho/Hop jobs.

Keep this module data-oriented: generation and validation both consume the same
catalog so the selected pattern and its safety rules cannot drift apart.
"""

NATIVE_COMPONENTS = {
    "SelectValues", "TableInput", "SortRows", "TableOutput", "SystemInfo",
    "TextFileOutput", "Dummy", "MergeJoin", "FilterRows", "GetVariable",
    "Formula", "Constant", "TextFileInput2", "ReplaceString", "Calculator",
    "GroupBy", "DataGrid", "SimpleMapping", "ConcatFields", "RowsToResult",
    "ExcelInput", "FieldSplitter", "RegexEval", "SwitchCase",
    "PipelineExecutor", "Normaliser", "Denormaliser", "MemoryGroupBy",
    "MappingInput", "MappingOutput", "SetVariable", "ExecSQL", "Sequence",
    "Unique", "CsvInput", "CSVInput",
}

REVIEW_COMPONENTS = {
    "JsonInput", "JsonOutput", "MetaInject", "MultiwayMergeJoin",
    "AnalyticQuery", "StreamLookup", "InsertUpdate", "ShapeFileReader",
    "SSH", "ExecProcess", "Validator", "JavaFilter", "Append", "WriteToLog",
    "ScriptValueMod",
}

COMPONENT_FREQUENCY = {
    "SelectValues": 2244, "TableInput": 1638, "SortRows": 1398,
    "TableOutput": 1005, "SystemInfo": 842, "TextFileOutput": 792,
    "Dummy": 736, "MergeJoin": 647, "FilterRows": 612,
    "GetVariable": 589, "Formula": 464, "Constant": 455,
    "TextFileInput2": 268, "ReplaceString": 265, "Calculator": 193,
    "GroupBy": 166, "SimpleMapping": 162, "ScriptValueMod": 157,
}


def generation_plan(task: dict) -> dict:
    """Choose a proven corpus pattern before rendering HPL."""
    source = task.get("source", "CSV")
    config = task.get("source_config") or {}
    if source == "POSTGRESQL_TABLE":
        sources = config.get("sources") or [config]
        if len(sources) > 1 or config.get("query"):
            pattern = "table-query-to-table"
            components = ["TableInput", "TableOutput"]
            reason = "Existing jobs commonly encapsulate joins and calculations in a read-only TableInput query."
        else:
            pattern = "table-to-table"
            components = ["TableInput", "TableOutput"]
            reason = "TableInput → TableOutput is a proven high-frequency transfer pattern."
    elif config.get("aggregation"):
        if config.get("module"):
            pattern = "csv-filter-module-sort-group-output"
            components = ["CSVInput", "FilterRows", "SimpleMapping", "SortRows", "GroupBy", "TableOutput"]
            reason = "The calculation is isolated as a reusable MappingInput → Calculator → MappingOutput module."
        else:
            pattern = "csv-filter-calculate-sort-group-output"
            components = ["CSVInput", "FilterRows", "Calculator", "SortRows", "GroupBy", "TableOutput"]
            reason = "The corpus requires sorted input before GroupBy and prefers Calculator over scripts."
    else:
        pattern = "csv-filter-output"
        components = ["CSVInput", "FilterRows", "TableOutput"]
        reason = "A minimal input → validation filter → mapped output pattern matches the requested transfer."
    return {
        "catalog": "transfer-project-2085-flows-2026-08-12",
        "pattern": pattern,
        "components": components,
        "reason": reason,
        "rules": [
            "explicit output field mappings",
            "typed inputs and constants",
            "SortRows before GroupBy or MergeJoin",
            "review-gated external side effects",
        ],
    }


def validate_pipeline_graph(root) -> list[str]:
    """Validate component policy and ordering constraints on an HPL XML root."""
    errors: list[str] = []
    transforms = root.findall("transform")
    names = {node.findtext("name") or "" for node in transforms}
    types = {node.findtext("name") or "": node.findtext("type") or "" for node in transforms}
    incoming: dict[str, list[str]] = {name: [] for name in names}
    for hop in root.findall("order/hop"):
        source, target = hop.findtext("from") or "", hop.findtext("to") or ""
        if source not in names or target not in names:
            errors.append(f"Hop references missing transform: {source} -> {target}")
            continue
        incoming[target].append(source)

    known = NATIVE_COMPONENTS | REVIEW_COMPONENTS
    for name, component in types.items():
        if not component:
            errors.append(f"Transform type missing: {name}")
        elif component not in known:
            errors.append(f"Component is not in the reviewed generation catalog: {component}")
        elif component in REVIEW_COMPONENTS:
            errors.append(f"Component requires explicit review before generation: {component}")

    for name, component in types.items():
        predecessors = incoming.get(name, [])
        if component == "GroupBy" and not any(types.get(item) == "SortRows" for item in predecessors):
            errors.append(f"GroupBy must receive sorted input directly: {name}")
        if component == "MergeJoin":
            if len(predecessors) < 2:
                errors.append(f"MergeJoin requires at least two input streams: {name}")
            elif any(types.get(item) != "SortRows" for item in predecessors):
                errors.append(f"Every MergeJoin input must come directly from SortRows: {name}")
    return errors
