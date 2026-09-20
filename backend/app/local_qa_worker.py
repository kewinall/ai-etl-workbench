"""One explicitly authorized QA request, no polling, fallback, or retry."""
import argparse
import json
import subprocess
from .copilot_gateway import complete_copilot
from .qa_gateway import complete_qa_review
from .local_qa_bridge import PUBLIC_ERRORS


def bridge(data):
    command=['wsl.exe','-d','RockyLinux9','-u','root','--','docker','exec','-i',
        'ai-etl-workbench-api-1','python','-m','app.bootstrap','python','-m','app.local_qa_bridge']
    result=subprocess.run(command,input=json.dumps(data),capture_output=True,text=True,
        encoding='utf-8',timeout=25,creationflags=subprocess.CREATE_NO_WINDOW)
    try:value=json.loads(result.stdout)
    except ValueError:raise ValueError('LOCAL_QA_BRIDGE_UNAVAILABLE') from None
    if result.returncode or value.get('status')=='ERROR':
        code=value.get('code')
        raise ValueError(code if code in PUBLIC_ERRORS else 'LOCAL_QA_BRIDGE_FAILED')
    return value


def run_once(task_id,run_id,comparison_id=None,context_checksum=None,*,authorize_model_call=False,website_authorized=False,
             transport=bridge,completion=complete_copilot):
    if authorize_model_call is not True and website_authorized is not True:raise ValueError('QA_MODEL_CALL_CONSENT_REQUIRED')
    identity={'task_id':task_id,'run_id':run_id}
    record=transport({**identity,'action':'claim_authorized' if website_authorized else 'claim','comparison_id':comparison_id,
        'context_checksum':context_checksum,'authorize_model_call':True})
    if record['status']!='DISPATCH_RESERVED':return {'status':record['status']}
    identity.update(invocation_id=record['invocation_id'],claim_token=record['claim_token'])
    def check():
        if transport({**identity,'action':'check'})['status']!='CLAIM_ACTIVE':
            raise ValueError('QA_CLAIM_LOST')
    try:
        review,trace=complete_qa_review(record['run'],record['profile'],record['context'],
            native_completion=completion,before_call=check)
        check()
        return transport({**identity,'action':'finish','review':review,'trace':trace})
    except Exception:
        try:transport({**identity,'action':'uncertain'})
        except Exception:pass
        return {'status':'QA_OUTCOME_UNKNOWN','invocation_id':record['invocation_id']}


def main():
    parser=argparse.ArgumentParser()
    for name in ('task-id','run-id'):parser.add_argument('--'+name,required=True)
    for name in ('comparison-id','context-checksum'):parser.add_argument('--'+name)
    parser.add_argument('--authorize-model-call',action='store_true')
    parser.add_argument('--website-authorized',action='store_true')
    args=parser.parse_args()
    print(json.dumps(run_once(args.task_id,args.run_id,args.comparison_id,args.context_checksum,
        authorize_model_call=args.authorize_model_call,website_authorized=args.website_authorized)))


if __name__=='__main__':main()
