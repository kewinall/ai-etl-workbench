"""Explicit operator source-order input; never infer order from prose or IDs."""


def order_evidence(snapshot):
    target=snapshot.get('target_config') or {}
    if 'source_order_v1' not in target:
        return None
    from .etl_specification import SourceOrderV1
    try:
        return SourceOrderV1.model_validate(target['source_order_v1']).model_dump()
    except ValueError:
        return {'invalid':True}


def order_issues(snapshot):
    target=snapshot.get('target_config') or {}
    if 'source_order_v1' not in target:
        return []
    from .etl_specification import SourceOrderV1
    from .transformation_contract import parsed_intent
    try:
        SourceOrderV1.model_validate(target['source_order_v1'])
        sources=(snapshot.get('source_config') or {}).get('sources') or []
        if len(sources)!=1 or sources[0].get('type')!='CSV':
            raise ValueError('SINGLE_CSV_REQUIRED')
        intent=parsed_intent(snapshot)
        if intent is None or intent.filters or intent.aggregation is not None or '$source_order.source.0' not in intent.output_columns:
            raise ValueError('FULL_PROJECTION_WITH_ORDINAL_REQUIRED')
    except ValueError:
        return [dict(issue_type='UNSUPPORTED',field_path='target_config.source_order_v1',
                     message='保留來源順序須為單一 CSV、無篩選與聚合，並於轉換意圖輸出包含來源序號',
                     suggestion={'required':True})]
    return []
