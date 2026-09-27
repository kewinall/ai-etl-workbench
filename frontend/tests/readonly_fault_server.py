"""Local UI fault injection; read-only upstream, no production listener.

Run with Python from any directory; browse http://127.0.0.1:5194.
First project list/evaluation requests fail once; retry reads real local API.
Uploads are consumed locally, delayed and rejected; never forwarded or stored.
Never use this server as the Pilot deployment.
"""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from time import sleep
from urllib.request import urlopen
from urllib.error import HTTPError

DIST = Path(__file__).resolve().parents[1] / 'dist'
seen = set()
lock = Lock()


class Handler(SimpleHTTPRequestHandler):
    def do_PUT(self):
        # Observe pending UI state without changing any saved configuration.
        if self.path not in ('/api/projects','/api/tasks') and not self.path.startswith(('/api/settings/ai-profiles/', '/api/projects/')):
            self.send_error(405)
            return
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 65536:
            self.send_error(413)
            return
        self.rfile.read(length)
        sleep(15)
        self.send_response(503)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"detail":"UI_DELAYED_SETTINGS_FAULT_NO_WRITE"}')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, *_):
        pass

    def do_POST(self):
        if self.path in ('/api/projects','/api/tasks'):
            return self.do_PUT()  # Delay/reject locally; never create records.
        # Fault injection only: never forward a write to the real API.
        if self.path != '/api/task-sources/upload':
            self.send_error(405)
            return
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 1024 * 1024:
            self.send_error(413)
            return
        self.rfile.read(length)
        sleep(15)
        self.send_response(503)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{"detail":"UI_DELAYED_UPLOAD_FAULT_NO_WRITE"}')

    def do_GET(self):
        if not self.path.startswith('/api/'):
            return super().do_GET()
        if self.path == '/api/projects' or self.path.endswith('/evaluation') or (self.path.startswith('/api/projects/') and self.path.endswith('/tasks')):
            with lock:
                fail = self.path not in seen
                seen.add(self.path)
            if fail:
                self.send_response(503)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(b'{"detail":"UI_FAULT_INJECTION_ONCE"}')
                return
        try:
            with urlopen('http://127.0.0.1:5183' + self.path, timeout=15) as response:
                data = response.read()
                self.send_response(response.status)
                self.send_header('Content-Type', response.headers.get('Content-Type', 'application/json'))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(data)
        except HTTPError as exc:
            self.send_error(exc.code)
        except Exception:
            self.send_error(502, 'Local upstream unavailable')


if __name__ == '__main__':
    if not (DIST / 'index.html').is_file():
        raise SystemExit('Build frontend first')
    print('Read-only UI fault server on 127.0.0.1:5194', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 5194), Handler).serve_forever()
