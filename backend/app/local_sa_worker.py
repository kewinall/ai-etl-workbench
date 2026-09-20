"""Single-run Windows worker. Docker-exec bridge avoids exposing PostgreSQL or copying credentials."""
import argparse
import json
import subprocess
import signal
from pathlib import Path
from uuid import uuid4
from threading import Event, Thread
from .copilot_gateway import complete_copilot, CopilotError
from .worker_presence import PresenceReporter


def bridge(data, *, distribution='RockyLinux9', container='ai-etl-workbench-api-1'):
    command = ['wsl.exe', '-d', distribution, '-u', 'root', '--', 'docker', 'exec', '-i', container,
               'python', '-m', 'app.bootstrap', 'python', '-m', 'app.local_sa_bridge']
    result = subprocess.run(command, input=json.dumps(data), capture_output=True, text=True,
                            encoding='utf-8', timeout=25, creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        value = json.loads(result.stdout)
    except ValueError:
        raise CopilotError('LOCAL_WORKER_BRIDGE_UNAVAILABLE') from None
    if result.returncode or value.get('status') == 'ERROR':
        raise CopilotError(value.get('code', 'LOCAL_WORKER_BRIDGE_FAILED'))
    return value


def run_once(task_id=None, run_id=None, *, transport=bridge, completion=complete_copilot):
    identity = {'task_id': task_id, 'run_id': run_id}
    record = transport({**identity, 'action': 'claim'})
    if record['status'] != 'DISPATCH_RESERVED':
        return {'status': record['status']}
    identity.update(task_id=str(record.get('task_id', task_id)), run_id=str(record.get('run_id', run_id)))
    identity.update(invocation_id=record['invocation_id'], claim_token=record['claim_token'])
    stop, lost = Event(), Event()
    def check():
        if lost.is_set():
            raise CopilotError('SA_LEASE_LOST')
        transport({**identity, 'action': 'heartbeat'})
    def heartbeat():
        while not stop.wait(10):
            try:
                check()
            except Exception:
                lost.set()
                return
    thread = Thread(target=heartbeat, daemon=True)
    thread.start()
    try:
        review, trace = completion(record['input_json'], record['model'], before_call=check)
        check()
        return transport({**identity, 'action': 'finish', 'review': review, 'trace': trace})
    except Exception as error:
        code = str(error) if isinstance(error, CopilotError) else 'LOCAL_WORKER_INTERRUPTED'
        try:
            transport({**identity, 'action': 'uncertain', 'trace': {'error_code': code, 'usage': None}})
        except Exception:
            pass
        return {'status': 'OUTCOME_REQUIRES_RECONCILIATION', 'code': code, 'invocation_id': record['invocation_id']}
    finally:
        stop.set()
        thread.join(timeout=26)


def serve(*, allow_model_dispatch=False, stop=None, stop_file=None, transport=bridge, completion=complete_copilot, poll_seconds=3, log=print):
    if not 1 <= poll_seconds <= 30:
        raise ValueError('INVALID_POLL_INTERVAL')
    stop = stop or Event()
    instance_id = str(uuid4())
    mode = 'EXECUTE' if allow_model_dispatch else 'OBSERVE'
    def report(activity):
        return transport({'action': 'presence', 'instance_id': instance_id, 'mode': mode, 'activity': activity})
    with PresenceReporter(report) as presence:
        log(json.dumps({'status': 'STARTED', 'instance_id': instance_id, 'mode': mode}))
        previous = None
        while not stop.is_set() and not (stop_file and Path(stop_file).exists()):
            try:
                presence.activity = 'BUSY'
                result = run_once(transport=transport, completion=completion) if allow_model_dispatch else transport({'action': 'observe'})
            except Exception:
                result = {'status': 'LOCAL_WORKER_STORE_UNAVAILABLE'}
            finally:
                presence.activity = 'IDLE'
            if result != previous:
                log(json.dumps(result, ensure_ascii=False))
                previous = result
            stop.wait(poll_seconds)
    log(json.dumps({'status': 'STOPPED', 'instance_id': instance_id}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--task-id')
    parser.add_argument('--run-id')
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--allow-model-dispatch', action='store_true')
    parser.add_argument('--stop-file', type=Path)
    args = parser.parse_args()
    if args.serve:
        if args.task_id or args.run_id:
            parser.error('--serve cannot target a single run')
        stop = Event()
        for name in (signal.SIGTERM, signal.SIGINT):
            signal.signal(name, lambda *_: stop.set())
        serve(allow_model_dispatch=args.allow_model_dispatch, stop=stop, stop_file=args.stop_file, log=lambda message: print(message, flush=True))
    else:
        if not args.task_id or not args.run_id or args.allow_model_dispatch or args.stop_file:
            parser.error('single-run mode requires --task-id and --run-id only')
        print(json.dumps(run_once(args.task_id, args.run_id), ensure_ascii=False))


if __name__ == '__main__':
    main()
