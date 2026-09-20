"""Fixed compiler HWF completion, in addition to its pipeline node evidence."""
import re
from .hop_log_evidence import hop_log_evidence


def workflow_log_evidence(process,expected_nodes,workflow_name):
    if not isinstance(workflow_name,str) or not re.fullmatch(r'etl_[a-f0-9]{16}',workflow_name):
        raise ValueError('INVALID_EXPECTED_WORKFLOW')
    evidence=hop_log_evidence(process,expected_nodes)
    prefix=r'^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} - '+re.escape(workflow_name)+r' - '
    patterns={
        'start':re.compile(prefix+r'Starting action \[Run pipeline\]\s*$'),
        'success':re.compile(prefix+r'Finished action \[Run pipeline\] \(result=\[true\]\)\s*$'),
        'failure':re.compile(prefix+r'Finished action \[Run pipeline\] \(result=\[false\]\)\s*$'),
        'finished':re.compile(prefix+r'Workflow execution finished\s*$'),
    }
    found={key:[] for key in patterns}
    for index,line in enumerate(process['output'].decode('utf-8',errors='replace').splitlines()):
        for key,pattern in patterns.items():
            if pattern.fullmatch(line):found[key].append(index)
    complete=(all(len(found[key])==1 for key in ('start','success','finished'))
        and not found['failure']
        and found['start'][0]<found['success'][0]<found['finished'][0]
        and evidence['result']['status']=='COMPLETED')
    if not complete and evidence['result']['status']=='COMPLETED':
        evidence['result']['status']='FAILED' if found['failure'] else 'UNKNOWN'
    return {**evidence,'workflow_completed':complete}
