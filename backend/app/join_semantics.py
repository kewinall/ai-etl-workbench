"""Compare a proposed Join to version-bound operator intent, without executing it."""
from .join_contract import JoinContractV1, join_condition_issues


def validate_join_semantics(proposed, snapshot):
    """Only parsed semantic values enter evidence; never echo arbitrary SQL/text.

    Keys here retain original source-column identities. Compilation resolves
    them through the same confirmed source-qualified Naming Contract.
    A match is not authorization or proof of native Hop execution semantics.
    """
    if join_condition_issues(snapshot):
        return [{'code': 'SPEC_JOIN_REQUIREMENT_INVALID', 'field_path': 'joins',
                 'message': '已確認輸入缺少有效 Join 契約，不可由設計自行補足'}]
    try:
        expected = JoinContractV1.model_validate(snapshot['target_config']['join_contract_v1'])
        actual = JoinContractV1.model_validate({'version': 1, 'joins': proposed})
    except (KeyError, ValueError):
        return [{'code': 'SPEC_JOIN_SCHEMA_INVALID', 'field_path': 'joins',
                 'message': 'Join 規格不合法或使用未支援的語意；不可忽略未知欄位'}]
    wanted, observed = expected.joins[0].model_dump(), actual.joins[0].model_dump()
    issues = []
    for field in wanted:
        if wanted[field] != observed[field]:
            issues.append({'code': 'SPEC_JOIN_SEMANTICS_MISMATCH',
                'field_path': 'joins.0.' + field, 'node_id': wanted['id'],
                'proposed_node_id': observed['id'],
                'requirement_path': 'join_contract_v1.joins.0.' + field,
                'expected': wanted[field], 'actual': observed[field],
                'message': 'Join 設計與已確認需求不同；必須修正规格或建立需求新版本'})
    return issues
