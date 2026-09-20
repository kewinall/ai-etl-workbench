import {test, expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test('六頁籤：合成舊產物顯示／下載契約、鍵盤、深連結與窄版面（非 Hop E2E）', async ({page, request}) => {
  expect((await (await request.get('/api/ready')).json()).execution_enabled).toBe(false);
  const project = await (await request.post('/api/projects', {data: {project_name: '六頁籤回歸-'+Date.now()}})).json();
  const response = await request.post(`/api/projects/${project.project_id}/tasks`, {data: {
    name: '六頁籤合成歷史', requirement: '只驗證畫面保留與下載，不呼叫模型或執行 ETL',
    source_config: {sources: [{type: 'CSV', alias: 'synthetic', has_actual_data: false, fields: [{name: 'customer_id', type: 'BIGINT'}]}]}, target_schema: 'ai_sample', target_table: 'ui_only',
  }});
  expect(response.status()).toBe(201);
  const task = await response.json();
  const xml = '<pipeline><name>synthetic_ui_only</name></pipeline>';
  // Browser-only fixtures: never mark a real database Task successful or register fake evidence.
  await page.route(`**/api/tasks/${task.id}`, route => route.fulfill({json: {...task, status: 'SUCCEEDED', progress: 100, rows: 2, nodes: [{key: 'compiler', label: '合成編譯節點', status: 'SUCCEEDED', detail: {source_columns: ['customer_id']}}], logs: [{node: 'compiler', level: 'INFO', time: '2026-09-13T00:00:00Z', message: '合成歷史事件', detail: {verified: 'UI_ONLY'}}]}}));
  await page.route(`**/api/tasks/${task.id}/history-assets`, route => route.fulfill({json: {
    jobs: [{artifact_id: 'ui-fixture', name: 'synthetic.hpl', artifact_type: 'HPL', version: 1, file_size: xml.length, content: xml, download_url: '/api/ui-fixture-download', transforms: [{name: 'Input', type: 'CsvInput'}], hops: [{from: 'Input', to: 'Output'}]}],
    sql: [{artifact: 'synthetic.hpl', node: 'Output', sql: 'SELECT customer_id FROM synthetic_ui_only'}], hop_logs: [{log_type: 'stdout', log_content: 'SYNTHETIC_HOP_LOG_NOT_EXECUTED'}],
  }}));
  await page.route('**/api/ui-fixture-download', route => route.fulfill({body: xml, headers: {'Content-Type': 'application/xml', 'Content-Disposition': 'attachment; filename="synthetic.hpl"'}}));
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  const base = `/#/projects/${project.project_id}/tasks/${task.id}`;
  await page.goto(base);
  await expect(page.getByRole('tab', {name: '概覽', exact: true})).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', {name: '概覽', exact: true}).focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.getByRole('tab', {name: '需求與規格', exact: true})).toBeFocused();
  await expect(page.getByRole('heading', {name: '建立 Task 的完整設定'})).toBeVisible();
  await page.getByRole('tab', {name: '產物與流程', exact: true}).click();
  await page.getByRole('button', {name: /合成編譯節點/}).click();
  await expect(page.getByRole('region', {name: '節點詳細資訊'})).toContainText('customer_id');
  await expect(page.getByRole('region', {name: '節點詳細資訊'})).toContainText('合成歷史事件');
  await page.getByText('XML／完整定義', {exact: true}).click();
  await expect(page.getByText(xml, {exact: true})).toBeVisible();
  await expect(page.getByText('SELECT customer_id FROM synthetic_ui_only', {exact: true})).toBeVisible();
  await page.getByRole('tab', {name: '執行與 QA', exact: true}).click();
  await expect(page.getByText('SYNTHETIC_HOP_LOG_NOT_EXECUTED', {exact: true})).toBeVisible();
  await page.getByRole('tab', {name: '交付', exact: true}).click();
  await expect(page.getByText('尚無經新版完整 QA 與人工核准的 Release', {exact: false})).toBeVisible();
  await expect(page.getByRole('link', {name: /Release ZIP/})).toHaveCount(0);
  // A legacy successful Task must not bypass the server-side Pilot release gate.
  const blockedBuild = await request.post(`/api/tasks/${task.id}/release`);
  expect(blockedBuild.status()).toBe(409);
  expect((await blockedBuild.json()).detail.code).toBe('RELEASE_PIPELINE_NOT_READY');
  const blockedDownload = await request.get(`/api/tasks/${task.id}/release/legacy/download`);
  expect(blockedDownload.status()).toBe(409);
  expect((await blockedDownload.json()).detail.code).toBe('RELEASE_PIPELINE_NOT_READY');
  const downloaded = page.waitForEvent('download');
  await page.getByRole('link', {name: /synthetic.hpl/}).click();
  const download = await downloaded;
  expect(download.suggestedFilename()).toBe('synthetic.hpl');
  expect(await readFile((await download.path())!, 'utf8')).toBe(xml);
  await page.reload();
  await expect(page.getByRole('tab', {name: '交付', exact: true})).toHaveAttribute('aria-selected', 'true');
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({width, height: 1000});
    for (const name of ['概覽','需求與規格','協作紀錄','產物與流程','執行與 QA','交付']) {
      await page.getByRole('tab', {name, exact: true}).click();
      await expect(page.getByRole('tabpanel')).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2), `${width}px ${name}`).toBe(true);
    }
  }
  await page.screenshot({path: test.info().outputPath('delivery-contract.png'), fullPage: true});
  expect(errors).toEqual([]);
  // Authoritative Task remains CREATED: these browser fixtures are not claimed as engine evidence.
  expect((await (await request.get(`/api/tasks/${task.id}`)).json()).status).toBe('CREATED');
});
