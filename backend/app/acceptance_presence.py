"""Local-only Docker transport for scoped service liveness; grants no work."""
import json
import os
import sys
from .run_queue import RunQueue
from .worker_presence import WorkerRegistry

if __name__ == '__main__':
    data=json.loads(sys.stdin.read(4096))
    result=WorkerRegistry(RunQueue(os.environ['DATABASE_URL'])).touch(**data)
    print(json.dumps(result))
