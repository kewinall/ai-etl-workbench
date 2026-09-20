"""One website-authorized native Copilot request; no polling, retries or tools."""
import argparse
import json
import subprocess
from .copilot_gateway import complete_copilot
from .local_developer_bridge import PUBLIC_ERRORS
from .sa_contract import digest


def bridge(data):
    command = ['wsl.exe','-d','RockyLinux9','-u','root','--','docker','exec','-i',
               'ai-etl-workbench-api-1','python','-m','app.bootstrap','python','-m','app.local_developer_bridge']
    result = subprocess.run(command, input=json.dumps(data), capture_output=True, text=True,
                            encoding='utf-8', timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
    try: value = json.loads(result.stdout)
    except ValueError: raise ValueError('LOCAL_DEVELOPER_BRIDGE_UNAVAILABLE') from None
    if result.returncode or value.get('status') == 'ERROR':
        code = value.get('code')
        raise ValueError(code if code in PUBLIC_ERRORS else 'LOCAL_DEVELOPER_BRIDGE_FAILED')
    return value


def run_once(task_id, run_id, *, transport=bridge, completion=complete_copilot):
    identity = {'task_id':task_id, 'run_id':run_id}
    record = transport({**identity, 'action':'claim'})
    if record['status'] != 'DISPATCH_RESERVED': return {'status':record['status']}
    identity.update(invocation_id=record['invocation_id'], claim_token=record['claim_token'])
    def check():
        if transport({**identity, 'action':'check'})['status'] != 'CLAIM_ACTIVE':
            raise ValueError('DEVELOPER_CLAIM_LOST')
    try:
        check()
        proposal, trace = completion(record['payload'], record['model'], before_call=check)
        check()
        trace = {**trace, 'prompt_version':record['prompt_version'], 'status':'VALIDATED_NOT_APPROVED',
                 'output_checksum':digest(proposal)}
        # Server revalidates native trace binding, schema, semantics and current versions.
        return transport({**identity, 'action':'finish', 'proposal':proposal, 'trace':trace})
    except Exception:
        try: transport({**identity, 'action':'uncertain'})
        except Exception: pass
        return {'status':'DEVELOPER_OUTCOME_UNKNOWN', 'invocation_id':record['invocation_id']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task-id', required=True); parser.add_argument('--run-id', required=True)
    args = parser.parse_args()
    print(json.dumps(run_once(args.task_id, args.run_id)))


if __name__ == '__main__': main()
