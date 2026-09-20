"""Conservative Hop 2.12 BASIC log evidence. Does not grant QA or release."""
from hashlib import sha256
import re

SUMMARY=re.compile(r'^\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} - ([A-Za-z_][A-Za-z0-9_]*)\.0 - Finished processing \(I=(\d+), O=(\d+), R=(\d+), W=(\d+), U=(\d+), E=(\d+)\)\s*$')


def hop_log_evidence(process,expected_nodes):
    data=process.get('output')
    if not isinstance(data,bytes) or len(data)>10*1024*1024:
        raise ValueError('INVALID_HOP_LOG')
    if not expected_nodes or len(set(expected_nodes))!=len(expected_nodes) or any(not isinstance(n,str) or not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',n) for n in expected_nodes):
        raise ValueError('INVALID_EXPECTED_NODES')
    checksum=sha256(data).hexdigest()
    nodes={};duplicate=False
    for line in data.decode('utf-8',errors='replace').splitlines():
        match=SUMMARY.fullmatch(line)
        if not match:continue
        name=match[1]
        if name in nodes:duplicate=True
        nodes[name]=dict(zip(('input','output','read','written','updated','errors'),map(int,match.groups()[1:])))
    complete=not duplicate and set(nodes)==set(expected_nodes)
    errors=sum(n['errors'] for n in nodes.values())
    code=process.get('exit_code')
    valid_code=type(code) is int and 0<=code<=2147483647
    normal=process.get('started') is True and process.get('reason')=='EXITED' and valid_code
    status='UNKNOWN'
    if normal and (code!=0 or errors>0):status='FAILED'
    elif normal and complete and code==0 and errors==0:status='COMPLETED'
    return {'result':{'status':status,'exit_code':code if valid_code else None,
                      'errors':errors if errors<=2147483647 else None,'log_checksum':checksum},
            'nodes':nodes,'complete_node_evidence':complete,'qa_passed':False}
