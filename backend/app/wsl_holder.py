"""Manual WSL liveness only. No database, ETL, Docker or model operations."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import stat
from threading import Event
from uuid import UUID, uuid4

ROOT = Path('/run/ai-etl-workbench-holder')


def validate_root(root, create=False):
    if create:
        root.mkdir(mode=0o700, exist_ok=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('HOLDER_DIRECTORY_IDENTITY_REJECTED')


def identity(pid):
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    ticks = Path('/proc/{}/stat'.format(pid)).read_text().rsplit(')', 1)[1].split()[19]
    return boot, ticks


def record(root, data):
    temporary = root / ('state-' + str(uuid4()) + '.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(data, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(root / 'state.json')


def status(root=ROOT):
    if not root.exists():
        return {'status': 'NOT_STARTED'}
    validate_root(root)
    try:
        fd = os.open(root / 'holder.lock', os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return {'status': 'NOT_STARTED'}
    try:
        held = False
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            held = True
        try:
            data = json.loads((root / 'state.json').read_text())
        except FileNotFoundError:
            return {'status': 'STARTING' if held else 'NOT_STARTED'}
        if not held:
            return {**data, 'status': 'STOPPED' if data['status'] == 'STOPPED' else 'LOST'}
        try:
            actual = identity(data['pid'])
        except (FileNotFoundError, ProcessLookupError):
            raise ValueError('HOLDER_OWNER_UNVERIFIED') from None
        if actual != (data['boot_id'], data['start_ticks']):
            raise ValueError('HOLDER_OWNER_UNVERIFIED')
        return {**data, 'status': 'RUNNING'}
    finally:
        os.close(fd)


def stop(root, token):
    token = str(UUID(token))
    observed = status(root)
    if observed['status'] != 'RUNNING' or observed.get('token') != token:
        raise ValueError('HOLDER_STOP_OWNER_MISMATCH')
    # A unique session flag cannot stop a replacement session or a reused PID.
    try:
        fd = os.open(root / ('stop-' + token), os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(fd)
    return {'status': 'STOP_REQUESTED', 'token': token}


def serve(root, token):
    token = str(UUID(token))
    validate_root(root, create=True)
    fd = os.open(root / 'holder.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('HOLDER_ALREADY_RUNNING') from None
        flag = root / ('stop-' + token)
        if flag.exists():
            raise ValueError('HOLDER_SESSION_ALREADY_STOPPED')
        pause = Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: pause.set())
        boot, ticks = identity(os.getpid())
        data = {'status': 'RUNNING', 'token': token, 'pid': os.getpid(), 'boot_id': boot, 'start_ticks': ticks}
        record(root, data)
        print(json.dumps(data), flush=True)
        try:
            while not pause.wait(1):
                if flag.exists():
                    break
        finally:
            record(root, {**data, 'status': 'STOPPED'})
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('serve', 'status', 'stop'))
    parser.add_argument('--token')
    args = parser.parse_args()
    try:
        if args.action == 'serve':
            serve(ROOT, args.token)
            return 0
        result = status() if args.action == 'status' else stop(ROOT, args.token)
    except Exception as error:
        code = str(error) if isinstance(error, ValueError) and str(error).startswith('HOLDER_') else 'HOLDER_OPERATION_FAILED'
        print(json.dumps({'status': 'ERROR', 'code': code}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
