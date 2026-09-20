from __future__ import annotations

import base64, hashlib, json, os, re, time, uuid
from datetime import datetime, timezone
from typing import Any

IDENTIFIER_RE=re.compile(r"[^a-z0-9_]+")
TYPE_ALIASES={"int":"INTEGER","integer":"INTEGER","bigint":"BIGINT","float":"FLOAT","double":"FLOAT","decimal":"NUMERIC(18,4)","numeric":"NUMERIC(18,4)","number":"NUMERIC(18,4)","date":"DATE","datetime":"TIMESTAMP","timestamp":"TIMESTAMP","bool":"BOOLEAN","boolean":"BOOLEAN"}
ZH_DICTIONARY={"姓名":"name","名稱":"name","客戶":"customer","客戶編號":"customer_id","訂單":"order","訂單編號":"order_id","日期":"date","金額":"amount","數量":"quantity","地址":"address","電話":"phone","電子郵件":"email","狀態":"status","產品":"product","產品編號":"product_id","類別":"category","城市":"city","縣市":"city","建立時間":"created_at","更新時間":"updated_at"}

def checksum(value:Any)->str:
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()

def normalize_identifier(value:str,ordinal:int)->str:
    raw=value.strip().lower()
    for zh,en in sorted(ZH_DICTIONARY.items(),key=lambda item:len(item[0]),reverse=True): raw=raw.replace(zh,en)
    raw=IDENTIFIER_RE.sub("_",raw).strip("_")
    if not raw or not re.fullmatch(r"[a-z_][a-z0-9_]*",raw): raw=f"column_{ordinal}"
    return raw[:60]

def inferred_vertica_type(values:list[Any], declared:str|None=None)->str:
    if declared:
        return TYPE_ALIASES.get(str(declared).lower(),str(declared).upper())
    meaningful=[v for v in values if v not in (None,"")]
    if not meaningful:return "VARCHAR(255)"
    text=[str(v).strip() for v in meaningful]
    if all(re.fullmatch(r"(?i:true|false|0|1)",x) for x in text):return "BOOLEAN"
    if all(re.fullmatch(r"[-+]?\d+",x) for x in text):return "BIGINT"
    if all(re.fullmatch(r"[-+]?(?:\d+\.\d+|\d+)",x) for x in text):return "NUMERIC(18,4)"
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}",x) for x in text):return "DATE"
    if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?",x) for x in text):return "TIMESTAMP"
    return f"VARCHAR({min(2048,max(32,max(len(x) for x in text)*2))})"

def naming_suggestions(profile:dict[str,Any], project_rules:dict[str,Any]|None=None)->dict[str,Any]:
    aliases=(project_rules or {}).get("column_aliases") or {}
    columns=[];seen=set()
    for source in profile.get("sources",[]):
        examples=source.get("masked_examples") or []
        for ordinal,field in enumerate(source.get("fields") or [],start=len(columns)+1):
            original=str(field.get("name") or "").strip(); base=str(aliases.get(original) or normalize_identifier(original,ordinal)); name=base
            suffix=2
            while name in seen:name=f"{base}_{suffix}";suffix+=1
            seen.add(name)
            values=[row.get(original) for row in examples if original in row]
            columns.append({"source_name":original,"english_name":name,"vertica_type":inferred_vertica_type(values,field.get("type")),"confidence":1.0 if original in aliases or original.isascii() else 0.72,"reason":"project_dictionary" if original in aliases else "deterministic_normalizer"})
    return {"contract_type":"NamingContractV1","status":"DRAFT","columns":columns,"checksum":checksum(columns)}

def requirement_issues(task:dict[str,Any])->list[dict[str,Any]]:
    issues=[];src=task.get("source_config") or {};target=task.get("target_config") or {}
    if not str(task.get("requirement") or "").strip():issues.append({"issue_type":"MISSING","field_path":"requirement","message":"缺少需求描述","suggestion":{"required":True}})
    sources=src.get("sources") or ([src] if src else [])
    if not sources:issues.append({"issue_type":"MISSING","field_path":"source_config.sources","message":"至少需要一個資料來源","suggestion":{"required":True}})
    for index,source in enumerate(sources):
        if source.get("has_actual_data") is False and not source.get("fields"):
            issues.append({"issue_type":"MISSING","field_path":f"source_config.sources[{index}].fields","message":"無既有資料表或檔案時，必須提供欄位與型別","suggestion":{"required":True}})
    for key in ("schema","table"):
        if not target.get(key):issues.append({"issue_type":"MISSING","field_path":f"target_config.{key}","message":f"缺少目標 {key}","suggestion":{"required":True}})
    if re.search(r"(?i)drop\s+(table|schema)|truncate\s+table",str(task.get("requirement") or "")):
        issues.append({"issue_type":"UNSAFE","field_path":"requirement","message":"需求包含破壞性 SQL；僅平台受控 ai_sample 範例來源表可重建","suggestion":{"allowed_scope":"ai_sample managed tables"}})
    return issues

def litellm_complete(profile:dict[str,Any], role:str, messages:list[dict[str,str]], secret:str|None=None)->tuple[dict[str,Any],dict[str,Any]]:
    from .model_gateway import complete_json
    return complete_json(profile,role,messages,secret=secret)

def encrypt_secret(value:str)->tuple[bytes,bytes]:
    key=os.getenv("PLATFORM_SETTINGS_ENCRYPTION_KEY","").strip()
    if not key:raise ValueError("PLATFORM_SETTINGS_ENCRYPTION_KEY is not configured")
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        raw=base64.urlsafe_b64decode(key + "=" * (-len(key)%4))
        if len(raw)!=32:raise ValueError
    except Exception as exc:raise ValueError("PLATFORM_SETTINGS_ENCRYPTION_KEY must be a base64 AES-256 key") from exc
    nonce=os.urandom(12);return AESGCM(raw).encrypt(nonce,value.encode(),None),nonce

def decrypt_secret(cipher:bytes,nonce:bytes)->str:
    key=os.getenv("PLATFORM_SETTINGS_ENCRYPTION_KEY","").strip();raw=base64.urlsafe_b64decode(key + "=" * (-len(key)%4))
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(raw).decrypt(nonce,cipher,None).decode()
