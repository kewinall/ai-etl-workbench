from app.delivery_compiler import compile_delivery_components
from app.qa_target_contract import expected_target
from app.qa_single_source_contract import expected_contract
from app.sa_contract import digest
from test_source_order_compilation import ordered_design
from test_etl_specification import design


def test_only_ordered_ordinal_is_not_null_and_qa_hash_matches():
    for factory,ordered in ((ordered_design,True),(design,False)):
        compiled=compile_delivery_components(*factory())
        spec=compiled['specification']
        details=dict(compiler_plan=compiled['plan'],output_types=compiled['output_types'],hpl_checksum=compiled['hpl_checksum'],
                     csv_input_contract={'header':True},csv_structure_validation={})
        source=next(s for s in compiled['plan']['stages'] if s['component']=='CSVInput')
        details['csv_structure_validation']['source_columns_checksum']=digest([f['source_name'] for f in source['fields']])
        single=expected_contract(spec,details)['target_ddl']
        target=expected_target(spec,details)
        assert single['checksum']==target['checksum']==compiled['ddl_checksum']
        assert single['columns']==target['columns']
        assert compiled['ddl'].count('NOT NULL')==int(ordered)
        for column in single['columns']:
            assert column['nullable'] is not (ordered and column['name']=='source_position')
        if ordered:assert '"source_position" BIGINT NOT NULL' in compiled['ddl']
