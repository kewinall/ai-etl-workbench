import {test, expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';

test('JSON 真實上傳確認、换檔失效、欄位式補正及歷史核准保留', async ({page, request}) => {
  test.setTimeout(90000);
  expect(process.env.WORKBENCH_TEST_URL).toBe('http://127.0.0.1:5195');
  expect((await (await request.get('/api/ready')).json()).execution_enabled).toBe(false);
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const original = (await (await request.get('/api/settings/groups')).json()).values.data_connections_targets;
  const nonce = Date.now(), profileId = `json-ui-${nonce}`;
  expect((await request.put(`/api/settings/ai-profiles/${profileId}`, {data: {
    display_name: 'Synthetic JSON UI - no model calls', provider_type: 'LITELLM_BEDROCK', region: 'us-east-1',
    model_routes: Object.fromEntries(['requirement_gate', 'etl_specification', 'qa_review'].map(role => [role, 'bedrock/amazon.nova-micro-v1:0'])),
  }})).ok()).toBe(true);
  let taskId = '';
  try {
    expect((await request.put('/api/settings/groups/data_connections_targets', {data: {
      ...original, etl_qa: {connection_id: 'json-ui-synthetic', host: 'synthetic.invalid', port: 5433, database: 'synthetic', user: 'synthetic'},
    }})).ok()).toBe(true);
    const project = await (await request.post('/api/projects', {data: {project_name: `JSON確認-${nonce}`,
      default_ai_profile: profileId, default_connection: 'json-ui-synthetic'}})).json();
    await page.goto(`/#/projects/${project.project_id}/tasks/new`);
    await page.getByRole('textbox', {name: 'Task 名稱', exact: true}).fill('JSON 來源與契約確認');
    await page.getByRole('textbox', {name: '需求描述', exact: true}).fill('保留全部合成資料；測試來源確認，不執行 ETL。');
    const picker = page.getByRole('button', {name: '選擇並上傳檔案', exact: true});
    const upload = () => picker.setInputFiles({name: 'synthetic.json', mimeType: 'application/json',
      buffer: Buffer.from('\ufeff[{"客戶編號":"001","金額":12.34},{"客戶編號":"002"},{}]')});
    await upload();
    const panel = page.getByRole('region', {name: 'JSON 來源結構確認'});
    const create = page.getByRole('button', {name: '建立 Task', exact: true});
    await expect(panel).toContainText('資料筆數：3');
    await expect(create).toBeDisabled();
    await panel.getByRole('button', {name: '確認 JSON 檔案與欄位'}).click();
    await expect(create).toBeEnabled();
    await upload();
    await expect(panel.getByRole('status')).toContainText('尚未確認');
    await expect(create).toBeDisabled();
    let release!: () => void, intercepted = false;
    const pending = new Promise<void>(resolve => {release = resolve});
    await page.route('**/api/task-sources/*/json-profile', async route => {
      intercepted = true; await pending; await route.continue();
    });
    try {
      await panel.getByRole('button', {name: '確認 JSON 檔案與欄位'}).click();
      await expect.poll(() => intercepted).toBe(true);
      await expect(create).toBeDisabled();
      await expect(page.getByRole('button', {name: '取消全部 Task 草稿'})).toBeDisabled();
    } finally {release()}
    await expect(create).toBeEnabled();
    await page.unroute('**/api/task-sources/*/json-profile');
    await page.setViewportSize({width: 390, height: 1000});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
    await panel.screenshot({path: test.info().outputPath('json-source-confirmation.png')});
    const savedResponse = page.waitForResponse(r => r.url().endsWith('/api/tasks') && r.request().method() === 'POST');
    await create.click();
    const saved = await savedResponse;
    expect(saved.status()).toBe(201);
    taskId = (await saved.json()).id;
    const task = await (await request.get(`/api/tasks/${taskId}`)).json();
    const source = task.source_config.sources[0];
    expect(source.json_profile_binding_v1.row_count).toBe(3);
    expect(source.json_profile_binding_v1.content_checksum).toBe(source.checksum);
    expect(source).not.toHaveProperty('sample_rows');
    const unconfirmed = {...saved.request().postDataJSON(), creation_request_key: undefined};
    unconfirmed.source_config.sources[0].json_profile_binding_v1 = null;
    expect((await request.post('/api/tasks', {data: unconfirmed})).status()).toBe(422);
    const prepared = await request.post(`/api/tasks/${taskId}/runs`, {data: {mode: 'PREPARE', request_key: `json-parent-${nonce}`}});
    expect(prepared.status()).toBe(201);
    const parent = await prepared.json();
    expect((await request.post(`/api/tasks/${taskId}/approvals`, {data: {run_id: parent.run_id,
      kind: 'INPUT_REVIEW', decision: 'APPROVE', input_checksum: parent.input_checksum, settings_checksum: parent.settings_checksum}})).ok()).toBe(true);
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
    await expect(page.getByRole('region', {name: '已保存的 JSON 來源確認'})).toContainText('3 筆');
    await expect(page.getByRole('region', {name: 'JSON 讀取契約摘要'})).toContainText('尚未確認');
    await page.getByRole('button', {name: '補正需求並建立新版', exact: true}).click();
    const form = page.getByRole('form', {name: '需求補正'});
    const editor = form.getByRole('group', {name: 'JSON 讀取契約補正'});
    await expect(editor.getByRole('checkbox')).not.toBeChecked();
    await editor.getByRole('checkbox').check();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
    await editor.screenshot({path: test.info().outputPath('json-policy-fields.png')});
    const revised = page.waitForResponse(r => r.url().endsWith(`/runs/${parent.run_id}/revisions`) && r.request().method() === 'POST');
    await form.getByRole('button', {name: '保存補正並建立新版'}).click();
    const revision = await revised;
    expect(revision.status()).toBe(201);
    // The app reloads immediately after saving; read persisted state rather than
    // a browser response body that navigation may have already discarded.
    const runs = (await (await request.get(`/api/tasks/${taskId}/runs`)).json()).runs;
    const child = runs.find((run: any) => run.parent_run_id === parent.run_id);
    expect(child).toBeTruthy();
    await expect(page.getByRole('region', {name: 'JSON 讀取契約摘要'})).toContainText('已確認：物件陣列');
    await page.reload();
    await expect(page.getByRole('region', {name: 'JSON 讀取契約摘要'})).toContainText('已確認：物件陣列');
    const persisted = await (await request.get(`/api/tasks/${taskId}/runs/${child.run_id}`)).json();
    expect(persisted.approval).toBeNull(); expect(persisted.write_started).toBe(false);
    expect(persisted.input_checksum).not.toBe(parent.input_checksum);
    const history = await (await request.get(`/api/tasks/${taskId}/runs/${parent.run_id}`)).json();
    expect(history.state).toBe('CANCELLED'); expect(history.approval.decision).toBe('APPROVE');
    expect(history.input_summary.json_input_contract_v1.contract_status).toBe('MISSING_OR_INVALID');
    expect(errors).toEqual([]);
  } finally {
    if (taskId) {
      const runs = (await (await request.get(`/api/tasks/${taskId}/runs`)).json()).runs;
      for (const run of runs.filter((r: any) => ['QUEUED', 'NEEDS_REVIEW'].includes(r.state) && !r.write_started))
        expect((await request.post(`/api/tasks/${taskId}/runs/${run.run_id}/cancel`)).ok()).toBe(true);
    }
    expect((await request.put('/api/settings/groups/data_connections_targets', {data: original})).ok()).toBe(true);
  }
});
