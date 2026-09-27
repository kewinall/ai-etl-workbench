"""Short-lived loopback server for the guarded recovery CLI, not deployment."""
from contextlib import contextmanager
import re
import socket
import threading
import time

import uvicorn
from starlette.responses import Response


class RecoveryReadOnly:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        allowed = (re.fullmatch(r'/api/projects/[0-9a-f-]{36}/pilot-measurements', path)
                   or re.fullmatch(r'/api/tasks/[^/]+/runs/[0-9a-f-]{36}/release/[0-9a-f-]{36}/download', path))
        if scope['type'] != 'http' or scope.get('method') != 'GET' or not allowed:
            if scope['type'] == 'websocket':
                await send({'type': 'websocket.close', 'code': 1008})
                return
            await Response(status_code=405)(scope, receive, send)
            return
        await self.app(scope, receive, send)


@contextmanager
def serve(app):
    sock = socket.socket()
    thread = None
    server = None
    try:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(RecoveryReadOnly(app),
            log_level='critical', access_log=False, lifespan='off', ws='none',
            timeout_graceful_shutdown=5))
        thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
        thread.start()
        deadline = time.monotonic() + 5
        while not server.started:
            if not thread.is_alive() or time.monotonic() >= deadline:
                raise ValueError('RECOVERY_HTTP_START_FAILED')
            time.sleep(.05)
        yield f'http://127.0.0.1:{port}'
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(10)
        sock.close()
        if thread is not None and thread.is_alive():
            raise ValueError('RECOVERY_HTTP_STOP_FAILED')
