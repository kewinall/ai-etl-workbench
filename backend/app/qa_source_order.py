"""Recheck executed source-position options and pinned ordered result evidence."""
from hashlib import sha256
from xml.etree import ElementTree as ET

from .comparison_store import checked_public_evidence
from .result_query_plan import compiled_result_query_plan


def validate_order_details(spec, details, checks):
    packet=details.get('source_order_evidence')
    if not isinstance(packet,dict) or set(packet)!={'version','scope','comparison','comparison_checksum','query_checksum'}:
        raise ValueError('QA_SOURCE_ORDER_EVIDENCE_REQUIRED')
    if type(packet['version']) is not int or packet['version']!=1 or packet['scope']!='PINNED_ORDERED_QUERY_AND_EXECUTED_HPL':
        raise ValueError('QA_SOURCE_ORDER_EVIDENCE_CHANGED')
    evidence=checked_public_evidence(packet['comparison'],packet['comparison_checksum'],spec['run_id'])
    ordinal=spec['source_order']['ordinal_column']
    if (evidence['version']!=2 or evidence['ordinal_column']!=ordinal
            or evidence['specification_checksum']!=details['compiler_plan']['specification_checksum']
            or evidence['naming_checksum']!=spec['naming']['checksum']
            or evidence['hop_log_checksum']!=checks['hop_execution']['checksum']
            or packet['comparison_checksum']!=checks['result_comparison']['checksum']
            or checks['result_comparison']['status']!=('PASS' if evidence['status']=='MATCH' else 'FAIL')):
        raise ValueError('QA_SOURCE_ORDER_EVIDENCE_CHANGED')
    query=compiled_result_query_plan(dict(status='VALIDATED_NOT_APPROVED',specification=spec,
        specification_checksum=evidence['specification_checksum'],output_types=details['output_types']))
    if query['checksum']!=packet['query_checksum'] or query['checksum']!=checks['result_source']['checksum']:
        raise ValueError('QA_SOURCE_ORDER_QUERY_CHANGED')
    stages=details['compiler_plan']['stages']
    sources=[s for s in stages if s['component']=='CSVInput']
    sorts=[s for s in stages if s['component']=='SortRows']
    if (len(sources)!=1 or sources[0].get('ordinal_column')!=ordinal
            or len(sorts)!=1 or sorts[0]['columns']!=[ordinal]
            or details['output_types'].get(ordinal)!='BIGINT'):
        raise ValueError('QA_SOURCE_ORDER_PLAN_CHANGED')
    if evidence['expected_count']!=details['csv_structure_validation']['records_checked']:
        raise ValueError('QA_SOURCE_ORDER_EXPECTED_SOURCE_COUNT_CHANGED')


def inspect_order(compiled, evidence, comparison_checksum, query_checksum):
    if sha256(compiled['hpl'].encode()).hexdigest()!=compiled['hpl_checksum']:
        raise ValueError('QA_SOURCE_ORDER_HPL_CHANGED')
    spec=compiled['specification']
    if spec['version']!=3:
        raise ValueError('QA_SOURCE_ORDER_SPEC_REQUIRED')
    checked_public_evidence(evidence,comparison_checksum,spec['run_id'])
    if compiled_result_query_plan(compiled)['checksum']!=query_checksum:
        raise ValueError('QA_SOURCE_ORDER_QUERY_CHANGED')
    root=ET.fromstring(compiled['hpl'])
    source=root.find("./transform[name='source']")
    sort=root.find("./transform[name='source_order_sort']")
    ordinal=spec['source_order']['ordinal_column']
    if (source is None or sort is None or source.findtext('type')!='CSVInput'
            or source.findtext('rownum_field')!=ordinal or source.findtext('parallel')!='N'
            or source.findtext('copies')!='1' or source.findtext('newline_possible')!='Y'
            or sort.findtext('type')!='SortRows' or sort.findtext('copies')!='1'
            or sort.findtext('unique_rows')!='N' or len(sort.findall('fields/field'))!=1
            or sort.findtext('fields/field/name')!=ordinal or sort.findtext('fields/field/ascending')!='Y'):
        raise ValueError('QA_SOURCE_ORDER_OPTIONS_CHANGED')
    return dict(version=1,scope='PINNED_ORDERED_QUERY_AND_EXECUTED_HPL',
                comparison=evidence,comparison_checksum=comparison_checksum,query_checksum=query_checksum)
