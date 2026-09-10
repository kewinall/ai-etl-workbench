from __future__ import annotations

import re
from typing import Any


REQUIRED_ARRAYS = (
    "sources", "joins", "filters", "derivations", "windows", "aggregations",
    "analytics", "modules", "validations", "acceptance_criteria", "missing_items",
    "warnings", "assumptions",
)


def canonicalize(raw: dict[str, Any], task: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Convert model JSON to the stable contract. Completion is never trusted from the model."""
    if not isinstance(raw, dict):
        raise ValueError("Copilot output must be one JSON object")
    spec = dict(raw)
    for key in REQUIRED_ARRAYS:
        value = spec.get(key, [])
        if not isinstance(value, list):
            raise ValueError(f"{key} must be an array")
        spec[key] = value
    spec["sources"] = spec["sources"] or profile.get("sources", [])
    spec["target"] = spec.get("target") or task.get("target_config") or {}
    if not isinstance(spec["target"], dict):
        raise ValueError("target must be an object")
    spec["schema_version"] = "1.0"
    spec.pop("complete", None)
    return spec


def requirement_gate(task: dict[str, Any], spec: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    text = (task.get("requirement") or "").lower()
    issues: list[dict[str, Any]] = list(profile.get("issues") or [])

    def blocking(field: str, reason: str, candidates=None, default=None):
        issues.append({"severity": "BLOCKING", "field": field, "reason": reason,
                       "candidates": candidates or [], "suggested_default": default})

    if (len(spec["sources"]) > 1 or "join" in text or "合併" in text) and not spec["joins"]:
        blocking("joins", "多來源處理缺少每段 Join Key、Join Type、基數與未匹配策略",
                 [s.get("alias") or s.get("id") for s in spec["sources"]])
    for index, join in enumerate(spec["joins"]):
        missing = [k for k in ("left", "right", "join_type", "conditions") if not join.get(k)]
        if missing:
            blocking(f"joins[{index}].{missing[0]}", "Join 定義不完整，無法驗證欄位與基數")
        if not join.get("cardinality"):
            issues.append({"severity": "WARNING", "field": f"joins[{index}].cardinality",
                           "reason": "未提供預期基數，執行時必須以重複鍵檢查保護", "candidates": [],
                           "suggested_default": "many_to_one"})
    wants_window = any(x in text for x in ("moving average", "移動平均", "rolling"))
    if wants_window and not spec["windows"]:
        blocking("windows", "移動平均缺少數值欄位、partition、時間排序及 ROWS/RANGE frame")
    for index, window in enumerate(spec["windows"]):
        if not window.get("order") or not window.get("frame"):
            blocking(f"windows[{index}]", "Window 必須指定排序欄位及明確 frame")
    wants_regression = bool(re.search(r"regression|迴歸", text)) or any(
        str(a.get("type", "")).lower().endswith("regression") for a in spec["analytics"] if isinstance(a, dict)
    )
    if wants_regression:
        required = ("type", "target", "features", "train_range", "split", "metrics", "model_name", "purpose")
        analytics = spec["analytics"][0] if spec["analytics"] else {}
        missing = [k for k in required if not analytics.get(k)]
        if missing:
            blocking(f"analytics[0].{missing[0]}", "Regression 規格不足，禁止以 JavaScript 猜測實作")
        else:
            issues.append({"severity": "REVIEW_REQUIRED", "field": "analytics[0]",
                           "reason": "需確認目標 Vertica 版本具備已核准且可測試的回歸函式",
                           "candidates": [], "suggested_default": None})
    blocking_items = [x for x in issues if x.get("severity") == "BLOCKING"]
    review_items = [x for x in issues if x.get("severity") == "REVIEW_REQUIRED"]
    return {"valid": not blocking_items and not review_items, "issues": issues,
            "status": "NEEDS_INPUT" if blocking_items else "REVIEW_REQUIRED" if review_items else "READY"}


def plan(spec: dict[str, Any]) -> dict[str, Any]:
    sources = spec["sources"]
    has_file = any(str(s.get("type", "")).upper() in ("CSV", "EXCEL") for s in sources)
    has_vertica = any(str(s.get("type", "")).upper() == "VERTICA" for s in sources)
    complex_sql = bool(spec["joins"] or spec["windows"] or spec["aggregations"])
    nodes = [{"id": s.get("id") or s.get("alias"), "kind": "SOURCE", "type": s.get("type")} for s in sources]
    for kind in ("joins", "filters", "derivations", "windows", "aggregations", "analytics", "modules"):
        nodes.extend({"id": f"{kind}-{i+1}", "kind": kind.upper(), "definition": item}
                     for i, item in enumerate(spec[kind]))
    strategy = "VERTICA_SQL_PUSHDOWN" if has_vertica and complex_sql else "HOP_NATIVE"
    if has_file and has_vertica and complex_sql:
        strategy = "VERTICA_STAGING_AND_SQL_PUSHDOWN"
    graph = {"nodes": nodes, "edges": [{"from": nodes[i]["id"], "to": nodes[i+1]["id"]}
                                             for i in range(max(0, len(nodes)-1))]}
    execution = {"strategy": strategy, "staging_required": strategy.startswith("VERTICA_STAGING"),
                 "sql_pushdown": "SQL_PUSHDOWN" in strategy, "target_engine": "VERTICA"}
    return {"logical_graph": graph, "execution_plan": execution}


def copilot_prompt(task: dict[str, Any], profile: dict[str, Any]) -> str:
    return f"""你是企業 ETL 規格分析器。只輸出一個有效 JSON object，不要 Markdown、不要 HPL、不要執行命令。
將需求與已遮蔽的來源摘要轉為 Canonical ETL Specification。
所有陣列欄位都必須出現：{', '.join(REQUIRED_ARRAYS)}。
sources 每筆含 id,type,alias,fields；joins 含 left,right,join_type,conditions,cardinality,unmatched_policy；
windows 含 partition,order,frame；analytics 含 type,target,features,train_range,split,metrics,model_name,purpose；
modules 含 id,inputs,outputs,logic,call_site；target 必須是 object。多個 Vertica 來源時必須輸出 sql_query，且只能是使用實際 schema.object 與欄位的單一 SELECT/WITH，不得輸出 DDL/DML。不可自行宣告 complete。
TASK={task.get('name')}
REQUIREMENT={task.get('requirement')}
PROFILE={profile}
TARGET={task.get('target_config')}"""
