import {execFileSync} from 'node:child_process';

// Run one control-only pass (the same Python the isolated API image runs) for a single approved Run.
// Default keeps the original target: the isolated compose API container on the Windows/WSL host.
// WORKBENCH_CONTROL_PYTHON=<python> runs it against a local isolated API instead; the caller's environment
// (DATABASE_URL, WORKBENCH_EXECUTION_ENABLED=false, ...) and WORKBENCH_CONTROL_CWD must point at that API.
export function controlOnce(script: string, runId: string): string {
  const python = process.env.WORKBENCH_CONTROL_PYTHON;
  if (python) return execFileSync(python, ['-c', script, runId], {encoding: 'utf8', timeout: 30000, cwd: process.env.WORKBENCH_CONTROL_CWD, env: process.env});
  return execFileSync('wsl', ['-d', 'RockyLinux9', '-u', 'root', '--', 'docker', 'exec',
    process.env.WORKBENCH_CONTROL_CONTAINER || 'ai-etl-ui-regression-api-1', 'python', '-c', script, runId], {encoding: 'utf8', timeout: 30000});
}

// These tests rewrite platform settings and create synthetic data, so they only run where explicitly allowed.
export const syntheticWritesAllowed = () => process.env.WORKBENCH_ALLOW_SYNTHETIC_UI === '1';

// Synthetic SA review plus the existing human SA handoff approval for one Run, written directly to the isolated
// control DB (same transport as controlOnce). No provider or model is called. The backend now requires a current
// same-Run SA approval before a specification can be saved or approved, so live tests that exercise the design stage
// use this instead of overriding the UI eligibility. Never run against 5197／5183.
export const SYNTHETIC_SA_APPROVAL = `import os,sys,json
from app.run_queue import RunQueue
from app.sa_journal import SAJournal
from app.sa_approval import read,approve
assert os.environ['WORKBENCH_EXECUTION_ENABLED']=='false'
q=RunQueue(os.environ['DATABASE_URL'])
run_id=sys.argv[1]
with q.conn() as c:
 task_id=c.execute('SELECT task_id FROM platform.task_run WHERE run_id=%s',(run_id,)).fetchone()['task_id']
run=q.detail(task_id,run_id)
journal=SAJournal(q);reserved=journal.reserve(task_id,run_id);ctx=reserved['context']
review=dict(version=1,run_id=run_id,input_checksum=run['input_checksum'],context_checksum=ctx['context_checksum'],
 status='READY_FOR_REVIEW',summary='Synthetic SA review for an isolated UI test; no model call',
 evidence_ids=[item['id'] for item in ctx['evidence']],issues=[])
journal.finish(task_id,reserved['invocation_id'],review)
offer=read(q,task_id,run_id)
assert offer['status']=='AWAITING_CONFIRMATION',offer
print(json.dumps({'status':approve(q,task_id,run_id,offer['binding']['checksum'],confirmed=True)['developer_authorized'] and 'APPROVED_CURRENT'}))`;
export const syntheticSaApproval = (runId: string) => JSON.parse(controlOnce(SYNTHETIC_SA_APPROVAL, runId).trim().split('\n').pop()!);
