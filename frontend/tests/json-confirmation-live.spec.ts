import {test, expect} from '@playwright/test';
import {controlOnce, syntheticWritesAllowed} from './fixtures/control';

test('JSON 真實上傳確認、换檔失效、欄位式補正及歷史核准保留', async ({page, request}) => {
  test.setTimeout(90000);
  test.skip(!syntheticWritesAllowed(), 'Explicit isolated write permission required (rewrites platform settings; WORKBENCH_ALLOW_SYNTHETIC_UI=1)');
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
import time
# claim() uses SKIP LOCKED; an open workspace page may briefly hold the Task row, as a looping worker would retry.
for attempt in range(20):
 result=run_once(q)
 if result['status']!='IDLE': break
 time.sleep(0.5)
print('idle retries',attempt,file=sys.stderr)
print(json.dumps(result))`;
    const result = controlOnce(script, parent.run_id);
    expect(JSON.parse(result).status).toBe('NEEDS_INPUT');
    await page.goto(`/#/projects/${project.project_id}/tasks/${taskId}/requirements`);
    // Saved Task settings now live in a collapsed section of the requirements stage.
    await page.getByText('Task 保存設定（目前內容；版本輸入以上方不可變快照為準）', {exact: true}).click();
    await expect(page.getByRole('region', {name: '已保存的 JSON 來源確認'})).toContainText('3 筆');
    await expect(page.getByRole('region', {name: 'JSON 讀取契約摘要'})).toContainText('尚未確認');
    await page.getByRole('button', {name: '補正需求並建立新版', exact: true}).click();
    const form = page.getByRole('form', {name: '需求補正'});
    await form.getByLabel('寫入模式').selectOption('APPEND');
    await form.getByLabel('資料期間').selectOption('ALL');
    await form.getByLabel('目標 Schema').fill('ai_sample');
    await form.getByLabel('目標 Table').fill(`json_ui_${nonce}`);
    const editor = form.getByRole('group', {name: 'JSON 讀取契約補正'});
    await expect(editor.getByRole('checkbox')).not.toBeChecked();
    await editor.getByRole('checkbox').check();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
    await editor.screenshot({path: test.info().outputPath('json-policy-fields.png')});
    const revised = page.waitForResponse(r => r.url().endsWith(`/runs/${parent.run_id}/revisions`) && r.request().method() === 'POST');
    // Revisions now require reviewing the field diff before saving (pre-existing flow since b5f48fd).
    await form.getByRole('button', {name: '預覽修訂差異'}).click();
    await form.getByLabel('已核對差異，同意建立待需求確認的新版').check();
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
    expect((await request.post(`/api/tasks/${taskId}/naming-contract/confirm`, {data: {columns:
      source.fields.map((field: any, index: number) => ({source_name: field.name,
        english_name: ['customer_id', 'amount'][index], vertica_type: field.type,
        confidence: 1, reason: '人工指定合成測試'}))}})).ok()).toBe(true);
    expect((await request.post(`/api/tasks/${taskId}/approvals`, {data: {run_id: child.run_id,
      kind: 'INPUT_REVIEW', decision: 'APPROVE', input_checksum: persisted.input_checksum,
      settings_checksum: persisted.settings_checksum}})).ok()).toBe(true);
    const checked = controlOnce(script, child.run_id);
    expect(JSON.parse(checked).status).toBe('CHECKED');
    // SA evidence now lives in the review stage under its technical-evidence fold.
    await page.goto(`/#/projects/${project.project_id}/tasks/${taskId}/review`);
    await page.getByText('需求審查技術證據', {exact: true}).click();
    const evidence = page.getByRole('region', {name: 'SA 需求證據', exact: true});
    await evidence.getByRole('button', {name: '查看 SA 證據清單'}).click();
    await expect(evidence.getByRole('region', {name: 'JSON 讀取契約摘要'})).toContainText('已確認');
    await expect(evidence).not.toContainText('[object Object]');
    // The seven-stage UI only offers specification creation after SA approval, which needs a model call that this
    // isolated environment never makes. The backend specification API itself does not require SA approval (known
    // limitation), so this test overrides only the design-stage SA prerequisite (stage can_operate and specification_create) and keeps every JSON/SDM/compile
    // assertion against the real API.
    await page.route(`**/api/tasks/${taskId}/runs/${child.run_id}/workflow-status`, async route => {
      const response = await route.fetch(); const body = await response.json();
      const create = body.operation_qualifications?.specification_create;
      if (create && !body.milestones?.sa_approved && !body.milestones?.specification_approved) {
        body.operation_qualifications.specification_create = {...create, enabled: true, blocked_reason: null};
        body.stages = body.stages.map((stage: any) => stage.key === 'design' ? {...stage, can_operate: true, blocked_reason: null} : stage);
      }
      await route.fulfill({response, json: body});
    });
    await page.goto(`/#/projects/${project.project_id}/tasks/${taskId}/design`);
    const specs = page.getByRole('region', {name: 'ETL 規格版本', exact: true});
    await specs.getByRole('button', {name: '建立規格', exact: true}).click();
    const specEditor = specs.getByRole('region', {name: '編輯 ETL 規格'});
    await specEditor.getByRole('button', {name: '讀取已確認欄位'}).click();
    await expect(specEditor.getByRole('region', {name: 'JSON 規格來源綁定'})).toBeVisible();
    await specEditor.getByLabel('篩選方式').selectOption('ALL');
    await specEditor.getByRole('checkbox', {name: 'customer_id', exact: true}).check();
    await specEditor.getByRole('checkbox', {name: 'amount', exact: true}).check();
    await specEditor.getByRole('checkbox', {name: '我已確認篩選、分組、聚合及輸出順序，保存為待核准規格。'}).check();
    await specEditor.getByRole('button', {name: '驗證並保存規格新版'}).click();
    await expect(specs).toContainText('已保存待核准規格');
    const base = `/api/tasks/${taskId}/runs/${child.run_id}`;
    const candidate = (await (await request.get(`${base}/specifications`)).json()).items[0];
    expect(candidate.spec_json.version).toBe(5);
    expect(candidate.spec_json.json_source.content_checksum).toBe(source.checksum);
    expect(candidate.approval_id).toBeNull();
    await specs.getByRole('checkbox', {name: '我已檢查來源、目標、篩選、分組與輸出，確認此規格；這不是執行授權。'}).check();
    await specs.getByRole('button', {name: '核准此版規格'}).click();
    await expect(specs).toContainText('規格核准已保存');
    await page.reload();
    // An approved specification completes the design stage, so its full record is folded and loads automatically.
    await page.getByText('查看此階段完整紀錄、操作歷史與技術詳情', {exact: true}).click();
    await expect(specs).toContainText('JSON SDM 可產生候選文件');
    await specs.getByRole('button', {name: '預覽 SDM 欄位對照'}).click();
    const sdm = specs.getByRole('region', {name: 'SDM 欄位對照預覽', exact: true});
    await expect(sdm).toContainText('SDM 候選內容（尚不可交付）');
    await expect(sdm.getByRole('region', {name: 'JSON 讀取契約摘要'})).toContainText('已確認');
    await sdm.getByText('JSON 來源與讀取指紋', {exact:true}).click();
    await expect(sdm).toContainText(source.checksum);
    await sdm.getByRole('button', {name:'產生／取得 SDM 候選 Excel'}).click();
    await expect(sdm).toContainText('候選 Excel 已保存');
    const downloaded = page.waitForEvent('download');
    await sdm.getByRole('button', {name:'下載 SDM 候選 Excel（非 Release）'}).click();
    expect((await downloaded).suggestedFilename()).toMatch(/^SDM-candidate-.*\.xlsx$/);
    await specs.getByRole('button', {name: '檢查 Hop 編譯預覽'}).click();
    await expect(specs).toContainText('source · 程式工具 JsonInput');
    await specs.getByText('查看參數範本與環境需求', {exact: true}).click();
    await expect(specs).toContainText('SOURCE_JSON');
    await expect(specs).not.toContainText('SOURCE_CSV');
    await specs.getByText('查看 JSON 版本指紋', {exact: true}).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
    await specs.screenshot({path: test.info().outputPath('json-specification-approved.png')});
    const finalRun = await (await request.get(`${base}`)).json();
    // CHECKED is the Gate result, not the durable Run state; review remains required.
    expect(finalRun.state).toBe('NEEDS_REVIEW'); expect(finalRun.write_started).toBe(false);
    expect((await (await request.get(`${base}/specifications`)).json()).items[0].approval_effective).toBe(true);
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
