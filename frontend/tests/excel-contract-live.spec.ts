import {test, expect} from '@playwright/test';
import {readFileSync} from 'node:fs';
import {execFileSync} from 'node:child_process';

test('Excel 契約真實補正、等待鎖定、回讀與舊版保留', async ({page, request}) => {
  test.setTimeout(90000);
  expect(process.env.WORKBENCH_TEST_URL).toBe('http://127.0.0.1:5195');
  expect((await (await request.get('/api/ready')).json()).execution_enabled).toBe(false);
  const original = (await (await request.get('/api/settings/groups')).json()).values.data_connections_targets;
  const nonce = Date.now();
  const profile = `excel-ui-${nonce}`;
  const response = await request.put(`/api/settings/ai-profiles/${profile}`, {data: {
    display_name: 'Synthetic Excel UI - no model calls', provider_type: 'LITELLM_BEDROCK', region: 'us-east-1',
    model_routes: Object.fromEntries(['requirement_gate', 'etl_specification', 'qa_review'].map(role => [role, 'bedrock/amazon.nova-micro-v1:0'])),
  }});
  expect(response.ok()).toBe(true);
  let taskId = '', childId = '';
  try {
    const savedSettings = await request.put('/api/settings/groups/data_connections_targets', {data: {
      ...original, etl_qa: {connection_id: 'excel-ui-synthetic', host: 'synthetic.invalid', port: 5433, database: 'synthetic', user: 'synthetic'},
    }});
    expect(savedSettings.ok()).toBe(true);
    const project = await (await request.post('/api/projects', {data: {project_name: `Excel補正-${nonce}`,
      default_ai_profile: profile, default_connection: 'excel-ui-synthetic'}})).json();
    const bytes = Buffer.from(readFileSync(new URL('./fixtures/excel-selection.base64', import.meta.url), 'utf8').trim(), 'base64');
    const upload = await (await request.post('/api/task-sources/upload', {multipart: {
      file: {name: 'synthetic.xlsx', mimeType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', buffer: bytes},
    }})).json();
    const selection = await (await request.post(`/api/task-sources/${upload.upload_id}/excel-profile`, {data: {
      checksum: upload.checksum, size: upload.size, worksheet: '明細', header_row: 2,
    }})).json();
    const {sample_rows, ...selected} = selection;
    const created = await request.post('/api/tasks', {data: {project_id: project.project_id, name: 'Excel 契約補正驗收',
      requirement: '保留全部資料，用於合成來源契約確認，不執行 ETL', source_type: 'EXCEL',
      source_config: {sources: [{...upload, ...selected, type: 'EXCEL', has_actual_data: true}]},
      target_schema: 'ai_sample', target_table: `excel_ui_${nonce}`, target_config: {requirements_v1: {version: 1, write_mode: 'APPEND', date_scope: 'ALL'}},
    }});
    expect(created.status()).toBe(201);
    taskId = (await created.json()).id;
    const prepared = await request.post(`/api/tasks/${taskId}/runs`, {data: {mode: 'PREPARE', request_key: `excel-parent-${nonce}`}});
    expect(prepared.status()).toBe(201);
    const parent = await prepared.json();
    expect((await request.post(`/api/tasks/${taskId}/approvals`, {data: {run_id: parent.run_id,
      kind: 'INPUT_REVIEW', decision: 'APPROVE', input_checksum: parent.input_checksum, settings_checksum: parent.settings_checksum}})).ok()).toBe(true);
    // One control-only pass inside the isolated API, where its uploaded bytes live.
    // Refuse to claim another pending Run; model and Hop dispatch remain disabled.
    const script = `import os,sys,json
from app.run_queue import RunQueue
from app.control_worker import run_once
assert os.environ['WORKBENCH_EXECUTION_ENABLED']=='false'
q=RunQueue(os.environ['DATABASE_URL'])
with q.conn() as c:
 rows=c.execute("SELECT r.run_id FROM platform.task_run r JOIN platform.task_run_approval a USING(run_id) WHERE r.state='QUEUED' AND a.decision='APPROVE'").fetchall()
 assert [str(r['run_id']) for r in rows]==[sys.argv[1]]
print(json.dumps(run_once(q)))`;
    const result = execFileSync('wsl', ['-d', 'RockyLinux9', '-u', 'root', '--', 'docker', 'exec',
      'ai-etl-ui-regression-api-1', 'python', '-c', script, parent.run_id], {encoding: 'utf8', timeout: 30000});
    expect(JSON.parse(result).status).toBe('NEEDS_INPUT');
    await page.goto(`/#/projects/${project.project_id}/tasks/${taskId}/requirements`);
    await expect(page.getByRole('region', {name: 'Excel 讀取契約摘要'})).toContainText('尚未確認');
    await page.getByRole('button', {name: '補正需求並建立新版', exact: true}).click();
    const form = page.getByRole('form', {name: '需求補正'});
    await form.getByRole('button', {name: '設定 Excel 讀取契約'}).click();
    await expect(form.getByLabel('Excel 空白列處理')).toHaveValue('');
    await form.getByLabel('Excel 空白列處理').selectOption('PRESERVE');
    await page.setViewportSize({width: 390, height: 1000});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
    await page.screenshot({path: test.info().outputPath('excel-contract-editor.png'), fullPage: true});
    await form.getByRole('group', {name: 'Excel 讀取契約補正'}).screenshot({path: test.info().outputPath('excel-contract-fields.png')});
    let release!: () => void, intercepted = false;
    const pending = new Promise<void>(resolve => {release = resolve});
    await page.route(`**/api/tasks/${taskId}/runs/${parent.run_id}/revisions`, async route => {
      intercepted = true; await pending; await route.continue();
    });
    const saved = page.waitForResponse(r => r.url().endsWith(`/runs/${parent.run_id}/revisions`) && r.request().method() === 'POST');
    try {
      await form.getByRole('button', {name: '保存補正並建立新版'}).click();
      await expect.poll(() => intercepted).toBe(true);
      await expect(form.getByLabel('Excel 空白列處理')).toBeDisabled();
      await expect(form.getByRole('button', {name: '放棄補正'})).toBeDisabled();
    } finally {release()}
    const saveResult = await saved;
    expect(saveResult.status()).toBe(201);
    const runs = (await (await request.get(`/api/tasks/${taskId}/runs`)).json()).runs;
    const child = runs.find((run: any) => run.parent_run_id === parent.run_id);
    expect(child).toBeTruthy(); childId = child.run_id;
    await expect(page.getByRole('region', {name: 'Excel 讀取契約摘要'})).toContainText('保留為 NULL');
    await page.reload();
    await expect(page.getByRole('region', {name: 'Excel 讀取契約摘要'})).toContainText('保留為 NULL');
    const persisted = await (await request.get(`/api/tasks/${taskId}/runs/${childId}`)).json();
    expect(persisted.approval).toBeNull(); expect(persisted.write_started).toBe(false);
    expect(persisted.parent_run_id).toBe(parent.run_id); expect(persisted.input_checksum).not.toBe(parent.input_checksum);
    const history = await (await request.get(`/api/tasks/${taskId}/runs/${parent.run_id}`)).json();
    expect(history.state).toBe('CANCELLED'); expect(history.approval.decision).toBe('APPROVE');
    expect(history.input_summary.excel_input_contract_v1.contract_status).toBe('MISSING_OR_INVALID');
  } finally {
    if (taskId) {
      const runs = (await (await request.get(`/api/tasks/${taskId}/runs`)).json()).runs;
      for (const run of runs.filter((value: any) => value.state === 'QUEUED' && !value.approval && !value.write_started))
        expect((await request.post(`/api/tasks/${taskId}/runs/${run.run_id}/cancel`)).ok()).toBe(true);
    }
    expect((await request.put('/api/settings/groups/data_connections_targets', {data: original})).ok()).toBe(true);
  }
});
