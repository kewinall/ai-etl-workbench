from app.platform_harness import inferred_vertica_type, naming_suggestions, requirement_issues

def test_profile_types_are_inferred():
    assert inferred_vertica_type(["1", "2"]) == "BIGINT"
    assert inferred_vertica_type(["2026-01-01"]) == "DATE"
    assert inferred_vertica_type(["12.50"]) == "NUMERIC(18,4)"

def test_naming_contract_is_unique_and_uses_dictionary():
    profile={"sources":[{"fields":[{"name":"客戶編號","type":"BIGINT"},{"name":"客戶編號","type":"BIGINT"}],"masked_examples":[]}]}
    contract=naming_suggestions(profile)
    assert contract["contract_type"] == "NamingContractV1"
    assert [x["english_name"] for x in contract["columns"]] == ["customer_id","customer_id_2"]

def test_requirement_gate_blocks_missing_sample_fields_and_unsafe_sql():
    task={"requirement":"建立範例表後 DROP TABLE old_data","source_config":{"sources":[{"type":"VERTICA","has_actual_data":False}]},"target_config":{"schema":"ods","table":"customer"}}
    issues=requirement_issues(task)
    assert {x["issue_type"] for x in issues} == {"MISSING","UNSAFE"}
