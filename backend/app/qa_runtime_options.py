"""Read exact executed HPL options; references are not per-run test results."""
from hashlib import sha256
from xml.etree import ElementTree as ET
from .etl_specification import _type


def expected_options(plan,hpl_checksum):
    sources=[]
    for stage in plan['stages']:
        if stage['component']!='CSVInput':continue
        fields=[]
        for field in stage['fields']:
            kind=_type(field['data_type'])
            fields.append(dict(name=field['stream_name'],type={'STRING':'String','INTEGER':'Integer',
                'DECIMAL':'BigNumber','BOOLEAN':'Boolean','DATE':'Date','TIMESTAMP':'Date'}[kind[0]],
                length=str(kind[2] if kind[0] in ('STRING','DECIMAL') else -1),
                precision=str(kind[3] if kind[0]=='DECIMAL' else -1),trim_type='none'))
        sources.append(dict(node_id=stage['id'],source_ref=stage.get('source_ref','source.0'),
                            lazy_conversion='N',fields=fields))
    target=next(stage for stage in plan['stages'] if stage['component']=='TableOutput')
    return dict(version=1,hpl_checksum=hpl_checksum,
        scope='EXECUTED_HPL_OPTIONS_RECHECKED_NO_REPLAY',sources=sources,
        target=dict(node_id=target['id'],ignore_errors='N',use_batch='Y',commit='1000',truncate='N'),
        error_handling_hops=False,
        atomicity='NO_ALL_BATCH_ROLLBACK_GUARANTEE_DO_NOT_RETRY_WRITES',
        behavior_reference=dict(scope='SEPARATE_ENGINE_PROBES_NOT_THIS_RUN_OR_RUNTIME_VERSION_ATTESTATION',
            engines='Apache Hop 2.12.0 / Vertica 25.3.0-2',
            evidence_document='docs/verification/join-stage3-2026-09-26.md',
            native_csv_test='test_csv_runtime_native.py',database_probe='probe_vertica_width.py',
            observations=['CSVInput empty string becomes NULL; trim_type=none preserves surrounding spaces.',
                'CSVInput invalid integer fails the pipeline; VARCHAR length metadata does not truncate a 33-character value.',
                'Unmodified compiler TableOutput accepted 32-byte VARCHAR(32) and failed on 33-byte ASCII and UTF-8 values; fresh sessions saw zero rows for the single-row failures.'],
            limits='Separate synthetic probes; not exhaustive parser/encoding/type testing, current-run version attestation or proof of rollback of previously committed batches.'))


def inspect_options(compiled):
    xml=compiled['hpl']
    if sha256(xml.encode()).hexdigest()!=compiled['hpl_checksum']:
        raise ValueError('QA_RUNTIME_HPL_CHECKSUM_CHANGED')
    root=ET.fromstring(xml)
    expected=expected_options(compiled['plan'],compiled['hpl_checksum'])
    if root.findall('./transform_error_handling/error') or root.findall('./error_handling/error'):
        raise ValueError('QA_RUNTIME_ERROR_HANDLING_CHANGED')
    for source in expected['sources']:
        node=root.find(f"./transform[name='{source['node_id']}']")
        if node is None or node.findtext('type')!='CSVInput' or node.findtext('lazy_conversion')!='N':
            raise ValueError('QA_RUNTIME_SOURCE_OPTIONS_CHANGED')
        fields=[{key:field.findtext(key) for key in ('name','type','length','precision','trim_type')}
                for field in node.findall('./fields/field')]
        if fields!=source['fields']:raise ValueError('QA_RUNTIME_SOURCE_OPTIONS_CHANGED')
    target=expected['target'];node=root.find(f"./transform[name='{target['node_id']}']")
    if node is None or node.findtext('type')!='TableOutput' or any(node.findtext(key)!=value for key,value in target.items() if key!='node_id'):
        raise ValueError('QA_RUNTIME_TARGET_OPTIONS_CHANGED')
    return expected
