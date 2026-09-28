"""Versioned parsing masks bound to executed HPL; not strict-parser attestation."""
from hashlib import sha256
from xml.etree import ElementTree as ET
from .etl_specification import _type


def expected_formats(plan, hpl_checksum):
    return dict(version=1, hpl_checksum=hpl_checksum,
        scope='EXECUTED_HPL_FORMAT_OPTIONS_RECHECKED_NO_REPLAY',
        sources=[dict(node_id=s['id'], source_ref=s.get('source_ref', 'source.0'),
            fields=[dict(name=f['stream_name'], format={
                'DATE': 'yyyy-MM-dd', 'TIMESTAMP': 'yyyy-MM-dd HH:mm:ss'
            }.get(_type(f['data_type'])[0], '')) for f in s['fields']])
            for s in plan['stages'] if s['component'] in ('CSVInput', 'ExcelInput')],
        limitation='Configured Hop masks only; not proof of strict rejection of every malformed date, timezone behavior or exhaustive parser testing.')


def inspect_formats(compiled):
    if sha256(compiled['hpl'].encode()).hexdigest() != compiled['hpl_checksum']:
        raise ValueError('QA_FORMAT_HPL_CHECKSUM_CHANGED')
    expected = expected_formats(compiled['plan'], compiled['hpl_checksum'])
    root = ET.fromstring(compiled['hpl'])
    for source in expected['sources']:
        nodes = [n for n in root.findall('transform') if n.findtext('name') == source['node_id']]
        expected_component = next(s['component'] for s in compiled['plan']['stages'] if s['id'] == source['node_id'])
        if len(nodes) != 1 or nodes[0].findtext('type') != expected_component:
            raise ValueError('QA_FORMAT_SOURCE_CHANGED')
        fields = [dict(name=f.findtext('name'), format=f.findtext('format'))
                  for f in nodes[0].findall('./fields/field')]
        if fields != source['fields']:
            raise ValueError('QA_FORMAT_OPTIONS_CHANGED')
    return expected


def should_enrich(record):
    if not record:
        return True
    context = record['input_json']['context']
    if (context.get('semantics', {}).get('execution_details') or {}).get('source_formats'):
        return True
    # Keep old PASS, pending and unknown invocations byte-for-byte stable.
    return (record.get('status') == 'VALIDATED_NOT_APPROVED'
            and (record.get('output_json') or {}).get('review', {}).get('status') == 'NEEDS_REVIEW')
