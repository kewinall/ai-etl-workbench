"""Opt-in local creation-response-loss probe; only synthetic Task creation.

Run: python creation_retry_server.py --project-id <synthetic project UUID>
Never forwards other writes, uploads, execution or approval requests.
"""
import argparse
import json
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from uuid import UUID
from readonly_fault_server import Handler, seen, lock

class RetryHandler(Handler):
    def do_POST(self):
        length=int(self.headers.get('Content-Length','0'))
        if self.path!='/api/tasks' or not 0<length<=65536:
            self.send_error(405);return
        try:
            body=self.rfile.read(length)
            data=json.loads(body)
            assert data['project_id']==self.server.project_id
            assert data['name']=='UI response loss verification'
            assert data['target_schema']=='ai_sample'
            assert data['target_table']=='never_executed_response_loss'
            assert data.get('operation')=='NEW'
            assert all(s.get('has_actual_data') is False for s in data['source_config']['sources'])
            key=str(UUID(data['creation_request_key']))
        except Exception:
            self.send_error(422);return
        # No automatic retries if the upstream result is unknown.
        try:
            with urlopen(Request('http://127.0.0.1:5183/api/tasks',data=body,
                                headers={'Content-Type':'application/json'}),timeout=20) as response:
                result=response.read()
        except Exception:
            self.send_error(502);return
        with lock:
            first=key not in seen
            seen.add(key)
        self.send_response(503 if first else 201)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(b'{"detail":"SIMULATED_RESPONSE_LOSS_AFTER_CREATE_RETRY_UNCHANGED"}' if first else result)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--project-id',type=UUID,required=True)
    args=parser.parse_args()
    seen.add('/api/projects')
    server=ThreadingHTTPServer(('127.0.0.1',5195),RetryHandler)
    server.project_id=str(args.project_id)
    print('Synthetic creation response-loss probe on 127.0.0.1:5195',flush=True)
    server.serve_forever()
