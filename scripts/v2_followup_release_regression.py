"""GET-only before/after fingerprint regression for eight immutable Releases."""
import hashlib
import json
import sys
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
phase = sys.argv[1]
assert phase in ('before', 'after')
folder = ROOT / 'runtime-temp/v2-followup-closure-deploy'
folder.mkdir(exist_ok=True)
cases = []
for filename in ('ui-accept-auto-delivery-2026-10-10.json', 'v2-followup-delivery-2026-10-11.json'):
    proof = json.loads((ROOT / 'docs/verification' / filename).read_text(encoding='utf-8-sig'))
    cases += [(c['key'], '/api/tasks', c['task_id'], c['run_id'], c['release']) for c in proof['cases']]
old = json.loads((ROOT / 'docs/verification/v2-followup-preserved-releases-2026-10-11.json').read_text(encoding='utf-8-sig'))
for c in old:
    if c['case'].startswith('old_'):
        cases.append((c['case'], '/api/evidence/pilot/tasks', c['task'], c['run'],
                      {'checksum': c['sha256'], 'file_size': c['bytes']}))
assert len(cases) == 8 and len({c[3] for c in cases}) == 8

def get(path):
    with urlopen('http://127.0.0.1:5197' + path, timeout=30) as reply:
        return reply.read()

records = []
for key, prefix, task, run_id, expected in cases:
    base = f'{prefix}/{task}/runs/{run_id}'
    before = json.loads(get(base))
    release = json.loads(get(base + '/release'))
    assert release['status'] == 'RELEASE_READY' and release['release_ready']
    saved = release['release']
    assert saved['checksum'] == expected['checksum'] and saved['file_size'] == expected['file_size']
    raw = get(base + '/release/' + saved['release_id'] + '/download')
    assert hashlib.sha256(raw).hexdigest() == saved['checksum'] and len(raw) == saved['file_size']
    after = json.loads(get(base))
    assert before == after
    count = sum(e['event_type'] == 'WRITE_STARTED' for e in after['events'])
    assert count == 1
    records.append(dict(case=key, task_id=task, run_id=run_id, release_id=saved['release_id'],
                        bytes=len(raw), sha256=saved['checksum'], write_started=count,
                        updated_at=after['updated_at'],
                        run_hash=hashlib.sha256(json.dumps(after, sort_keys=True, default=str).encode()).hexdigest(),
                        release_hash=hashlib.sha256(json.dumps(release, sort_keys=True, default=str).encode()).hexdigest()))
if phase == 'after':
    assert records == json.loads((folder / 'before.json').read_text(encoding='utf-8'))
(folder / (phase + '.json')).write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
print(json.dumps(dict(phase=phase, cases=8, status='PASS', writes=0)))
