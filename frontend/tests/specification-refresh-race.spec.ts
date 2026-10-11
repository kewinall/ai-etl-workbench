import {test, expect, type Page, type APIRequestContext} from '@playwright/test';
import {routeWorkflow} from './fixtures/workflow';

// Deterministic ordering of the specification panel's background re-reads versus user operations.
// Responses are held with explicit gates (no fixed sleeps); every response is synthetic browser data, not a
// database approval or execution acceptance.
type Gate = {wait: Promise<void>; open: () => void};
const gate = (): Gate => {let open!: () => void; const wait = new Promise<void>(resolve => {open = resolve}); return {wait, open}};
const RUN_A = '00000000-0000-4000-8000-0000000000a1';
const RUN_B = '00000000-0000-4000-8000-0000000000b2';
const baseSpec = {target_schema: 'ai_sample', target_table: 'totals', write_mode: 'APPEND', source_ref: 'source.0', naming: {version: 1},
  filters: [{column: 'amount', operator: 'GT', constant: {value: '100.00'}}],
  aggregation: {group_by: ['category'], metrics: [{id: 'sum', output_column: 'total_amount', function: 'SUM', column: 'amount'}]},
  output_columns: ['category', 'total_amount']};
const item = (id: string, version: number, checksum: string, extra: Record<string, unknown> = {}) =>
  ({specification_id: id, version, spec_json: baseSpec, content_checksum: checksum, reviewable: true, approval_id: null, approval_effective: false, ...extra});

async function setup(page: Page, request: APIRequestContext, runs = [RUN_A]) {
  const project = await (await request.post('/api/projects', {data: {project_name: '規格刷新時序-' + Date.now()}})).json();
  const response = await request.post(`/api/projects/${project.project_id}/tasks`, {data: {name: '規格刷新時序', requirement: 'UI only',
    source_config: {sources: [{type: 'CSV', has_actual_data: false, fields: [{name: 'id', type: 'BIGINT'}]}]}, target_schema: 'ai_sample', target_table: 'ui_only'}});
  expect(response.status()).toBe(201);
  const task = await response.json();
  const base = `**/api/tasks/${task.id}/runs`;
  const run = (id: string) => ({run_id: id, state: 'NEEDS_REVIEW', created_at: '2026-10-11T00:00:00Z', input_summary: {}, settings_summary: {}, events: [], matches_current: true});
  await page.route(base, route => route.fulfill({json: {runs: runs.map(run)}}));
  for (const id of runs) {
    await page.route(`${base}/${id}`, route => route.fulfill({json: run(id)}));
    await page.route(`${base}/${id}/developer`, route => route.fulfill({json: {invocation: null, eligible: false, dispatch_enabled: false}}));
  }
  await routeWorkflow(page, task.id, {stage: 'design'});
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  return {project, task, base, errors, url: (id: string) => `/#/projects/${project.project_id}/tasks/${task.id}/design/${id}`};
}

// Routes the specification list for one Run. Each GET captures the list at request time. `control` may return a
// gate to hold that response (answered later with the captured list) or 'fail' for a synthetic read failure.
type Control = (snapshot: any[], n: number) => Gate | 'fail' | undefined;
async function routeList(page: Page, base: string, runId: string, list: () => any[], control: Control = () => undefined) {
  const seen = {count: 0, answered: 0};
  await page.route(`${base}/${runId}/specifications`, async route => {
    if (route.request().method() !== 'GET') return route.fallback();
    const n = ++seen.count, snapshot = list(), decision = control(snapshot, n);
    if (decision && decision !== 'fail') await decision.wait;
    await (decision === 'fail' ? route.fulfill({status: 500, json: {detail: '合成讀取失敗'}}) : route.fulfill({json: {items: snapshot}}));
    seen.answered++;
  });
  return seen;
}

async function saveNewVersion(page: Page, base: string, runId: string, panel: ReturnType<Page['getByRole']>) {
  await page.route(`${base}/${runId}/specification/editor-context`, route => route.fulfill({json: {status: 'EDITOR_CONTEXT_READY',
    binding: {run_id: runId, naming: {version: 1}, target_schema: 'ai_sample', target_table: 'totals', write_mode: 'APPEND'},
    source_columns: [{name: 'category', source_name: '類別', data_type: 'VARCHAR(32)', constant_type: 'STRING'}, {name: 'amount', source_name: '金額', data_type: 'NUMERIC(12,2)', constant_type: 'DECIMAL'}],
    metric_columns: [{id: 'sum', output_column: 'total_amount', data_type: 'NUMERIC(18,2)'}]}}));
  await panel.getByRole('button', {name: '以此規格編輯新版'}).click();
  const editor = panel.getByRole('region', {name: '編輯 ETL 規格'});
  await editor.getByRole('button', {name: '讀取已確認欄位'}).click();
  await editor.getByLabel('比較值（日期 YYYY-MM-DD，布林 true／false）').fill('200.00');
  await editor.getByLabel('我已確認篩選、分組、聚合及輸出順序，保存為待核准規格。').check();
  await editor.getByRole('button', {name: '驗證並保存規格新版'}).click();
}

for (const order of ['background-after-onSaved', 'background-before-onSaved'] as const) {
  test(`保存成功訊息不被背景重讀清除（${order}）`, async ({page, request}) => {
    const {base, errors, url} = await setup(page, request);
    let saved = false;
    const statusGate = gate();
    const list = () => saved ? [item('s2', 2, 'b'.repeat(64)), item('s1', 1, 'a'.repeat(64))] : [item('s1', 1, 'a'.repeat(64))];
    let holdNextRead = false, heldOnSaved = 0;
    const gets = await routeList(page, base, RUN_A, list, () => {
      if (!holdNextRead) return undefined;
      holdNextRead = false; heldOnSaved++;
      return statusGate;
    });
    // Hold the workspace re-read that the save triggers (workflow-status), to choose when the background read runs.
    let holdStatus = false;
    await page.route(`${base}/${RUN_A}/workflow-status`, async route => {
      if (holdStatus) await statusGate.wait;
      return route.fallback();
    });
    await page.route(`${base}/${RUN_A}/specifications`, async route => {
      if (route.request().method() !== 'POST') return route.fallback();
      saved = true; holdStatus = order === 'background-after-onSaved';
      if (order === 'background-before-onSaved') holdNextRead = true;  // keep onSaved's own (first) read open
      return route.fulfill({json: {status: 'SAVED_NOT_EXECUTABLE', execution_authorized: false}});
    });
    await page.goto(url(RUN_A));
    const panel = page.getByRole('region', {name: 'ETL 規格版本', exact: true});
    await expect(panel).toContainText('amount 大於 100.00');
    await saveNewVersion(page, base, RUN_A, panel);
    if (order === 'background-after-onSaved') {
      await expect(panel.getByRole('status')).toHaveText('已保存待核准規格，沒有執行 ETL。');
      const before = gets.count;
      statusGate.open();
      await expect.poll(() => gets.count).toBeGreaterThan(before);   // the background re-read happened after onSaved
    } else {
      // The workspace re-read completes while the editor is still open (and onSaved's read is held).
      await expect.poll(() => heldOnSaved).toBe(1);
      await expect(page.getByRole('button', {name: '重新核對狀態'})).toBeEnabled();
      statusGate.open();
    }
    await expect(panel.getByRole('option', {name: /第 2 版/})).toHaveCount(1);
    await expect(panel.getByRole('status')).toHaveText('已保存待核准規格，沒有執行 ETL。');
    // A later shared refresh still keeps the confirmation.
    const before = gets.count;
    await page.getByRole('button', {name: '重新核對狀態'}).click();
    await expect.poll(() => gets.count).toBeGreaterThan(before);
    await expect(page.getByRole('button', {name: '重新核對狀態'})).toBeEnabled();
    await expect(panel.getByRole('status')).toHaveText('已保存待核准規格，沒有執行 ETL。');
    expect(errors).toEqual([]);
  });
}

test('較早的規格讀取晚到時被忽略，不覆蓋較新的內容', async ({page, request}) => {
  const {base, errors, url} = await setup(page, request);
  const older = [item('s1', 1, 'a'.repeat(64))], newer = [item('s2', 2, 'b'.repeat(64)), ...older];
  let current = older, holdOld = false, held = 0;
  const late = gate();
  // While holdOld is set, every read that captured the old list is held until `late` opens.
  const gets = await routeList(page, base, RUN_A, () => current, snapshot => holdOld && snapshot === older ? (held++, late) : undefined);
  await page.goto(url(RUN_A));
  const panel = page.getByRole('region', {name: 'ETL 規格版本', exact: true});
  await expect(panel.getByRole('option')).toHaveCount(1);
  holdOld = true;
  await page.getByRole('button', {name: '重新核對狀態'}).click();
  await expect.poll(() => held).toBeGreaterThan(0);          // an older read is in flight
  current = newer; holdOld = false;
  await expect(page.getByRole('button', {name: '重新核對狀態'})).toBeEnabled();
  await page.getByRole('button', {name: '重新核對狀態'}).click();     // a newer read answers immediately
  await expect(panel.getByRole('option')).toHaveCount(2);
  late.open();                                               // the stale one-version answers arrive last
  await expect.poll(() => gets.answered).toBe(gets.count);
  await page.evaluate(() => new Promise(requestAnimationFrame));
  await expect(panel.getByRole('option')).toHaveCount(2);
  await expect(panel.getByRole('option', {name: /第 2 版/})).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('編譯預覽：同一 Run、規格與指紋保留；內容改變才清除', async ({page, request}) => {
  const {base, errors, url} = await setup(page, request);
  let checksum = 'a'.repeat(64);
  const gets = await routeList(page, base, RUN_A, () => [item('s1', 1, checksum)]);
  await page.route(`${base}/${RUN_A}/specification/compile-preview`, route => route.fulfill({json: {status: 'VALIDATED_NOT_APPROVED',
    plan: {stages: [{id: 'source', component: 'CSVInput'}]}, hpl: '<pipeline>race fixture</pipeline>', hwf: '', ddl: '', parameters: ''}}));
  await page.goto(url(RUN_A));
  const panel = page.getByRole('region', {name: 'ETL 規格版本', exact: true});
  await panel.getByRole('button', {name: '檢查 Hop 編譯預覽'}).click();
  await expect(panel).toContainText('已產生編譯候選，尚未執行');
  let before = gets.count;
  await page.getByRole('button', {name: '重新核對狀態'}).click();
  await expect.poll(() => gets.count).toBeGreaterThan(before);
  await expect(page.getByRole('button', {name: '重新核對狀態'})).toBeEnabled();
  await expect(panel).toContainText('已產生編譯候選，尚未執行');   // same Run/spec/fingerprint: kept
  checksum = 'c'.repeat(64);
  before = gets.count;
  await page.getByRole('button', {name: '重新核對狀態'}).click();
  await expect.poll(() => gets.count).toBeGreaterThan(before);
  await expect(panel).not.toContainText('已產生編譯候選，尚未執行');   // content changed: cleared
  await expect(panel).toContainText('c'.repeat(64));
  expect(errors).toEqual([]);
});

test('切換 Run：上一個 Run 晚到的規格回應不會顯示在新 Run', async ({page, request}) => {
  const {base, errors, url} = await setup(page, request, [RUN_B, RUN_A]);
  const lateA = gate();
  const getsA = await routeList(page, base, RUN_A, () => [item('sa', 1, 'a'.repeat(64), {spec_json: {...baseSpec, target_table: 'run_a_table'}})], () => lateA);
  await routeList(page, base, RUN_B, () => [item('sb', 3, 'b'.repeat(64), {spec_json: {...baseSpec, target_table: 'run_b_table'}})]);
  await page.goto(url(RUN_A));
  const panel = page.getByRole('region', {name: 'ETL 規格版本', exact: true});
  await expect(panel).toBeVisible();
  await page.goto(url(RUN_B));
  await expect(panel).toContainText('ai_sample.run_b_table');
  expect(getsA.count).toBeGreaterThan(0);
  lateA.open();
  await expect.poll(() => getsA.answered).toBe(getsA.count);
  await page.evaluate(() => new Promise(requestAnimationFrame));
  await expect(panel).toContainText('ai_sample.run_b_table');
  await expect(panel).not.toContainText('run_a_table');
  expect(errors).toEqual([]);
});

test('背景讀取失敗保留上次內容與操作訊息，只提供重試', async ({page, request}) => {
  const {base, errors, url} = await setup(page, request);
  let failing = false;
  const gets = await routeList(page, base, RUN_A, () => [item('s1', 1, 'a'.repeat(64))], () => failing ? 'fail' : undefined);
  await page.route(`${base}/${RUN_A}/specifications/s1/approve`, route => route.fulfill({json: {status: 'SPEC_APPROVED_NOT_EXECUTABLE', execution_authorized: false}}));
  await page.goto(url(RUN_A));
  const panel = page.getByRole('region', {name: 'ETL 規格版本', exact: true});
  await panel.getByRole('checkbox').check();
  await panel.getByRole('button', {name: '核准此版規格'}).click();
  await expect(panel.getByRole('status')).toHaveText('規格核准已保存；未啟動 Hop 或產生 Release。');
  await expect(page.getByRole('button', {name: '重新核對狀態'})).toBeEnabled();
  failing = true;
  const before = gets.count;
  await page.getByRole('button', {name: '重新核對狀態'}).click();
  await expect.poll(() => gets.count).toBeGreaterThan(before);
  await expect(panel.getByRole('alert')).toContainText('合成讀取失敗');
  await expect(panel.getByRole('status')).toHaveText('規格核准已保存；未啟動 Hop 或產生 Release。');
  await expect(panel).toContainText('ai_sample.totals');
  failing = false;
  await panel.getByRole('button', {name: '重試讀取規格版本'}).click();
  await expect(panel.getByRole('alert')).toHaveCount(0);
  await expect(panel.getByRole('button', {name: '重試讀取規格版本'})).toHaveCount(0);
  expect(errors).toEqual([]);
});
