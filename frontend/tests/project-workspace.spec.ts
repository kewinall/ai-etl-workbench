import {test, expect} from '@playwright/test';

test('專案新增、編輯、取消、重載與 Task 導覽', async ({page, request}) => {
  const readiness = await request.get('/api/ready');
  expect(readiness.ok()).toBeTruthy();
  expect((await readiness.json()).execution_enabled).toBe(false);
  const errors: string[] = [];
  page.on('pageerror', e => errors.push(e.message));
  const name = 'UI驗收-' + Date.now();
  await page.goto('/#/projects');
  await page.getByRole('button', {name: '新增專案', exact: true}).click();
  await page.getByLabel('專案名稱', {exact: false}).fill(name);
  await page.getByLabel('專案說明').fill('合成資料：專案互動驗收');
  await page.getByRole('button', {name: '新增對照', exact: true}).click();
  await page.getByLabel('原始名稱 1', {exact: true}).fill('客戶編號');
  await page.getByLabel('英文名稱 1', {exact: true}).fill('customer_id');
  await page.getByRole('button', {name: '建立專案', exact: true}).click();
  await expect(page).toHaveURL(/#\/projects\/[0-9a-f-]+\/settings$/);
  const projectId = page.url().split('/projects/')[1].split('/')[0];
  await page.getByRole('combobox', {name: '預設 AI Profile', exact: true}).selectOption('');
  await page.getByRole('combobox', {name: '預設資料連線', exact: true}).selectOption('');
  await page.getByRole('button', {name: '儲存設定', exact: true}).click();
  await expect(page.getByRole('status').filter({hasText: '已儲存；重新載入後仍可保留設定'})).toBeVisible();
  await page.reload();
  await expect(page.getByRole('combobox', {name: '預設 AI Profile', exact: true})).toHaveValue('');
  await expect(page.getByRole('combobox', {name: '預設資料連線', exact: true})).toHaveValue('');
  await expect(page.getByLabel('專案名稱', {exact: false})).toHaveValue(name);
  await page.getByLabel('專案名稱', {exact: false}).fill('未儲存修改');
  await page.getByRole('button', {name: '取消變更', exact: true}).click();
  await expect(page.getByLabel('專案名稱', {exact: false})).toHaveValue(name);
  await page.getByLabel('專案說明').fill('已儲存的驗收說明');
  await page.getByRole('button', {name: '儲存設定', exact: true}).click();
  await expect(page.getByRole('status').filter({hasText: '已儲存'})).toBeVisible();
  await page.reload();
  await expect(page.getByLabel('專案說明')).toHaveValue('已儲存的驗收說明');
  await expect(page.getByLabel('英文名稱 1', {exact: true})).toHaveValue('customer_id');
  const saved = await request.get('/api/projects/'+projectId);
  expect((await saved.json()).naming_rules.column_aliases['客戶編號']).toBe('customer_id');
  await page.getByRole('button', {name: '新增專案', exact: true}).click();
  await page.getByRole('button', {name: '取消變更', exact: true}).click();
  await expect(page).not.toHaveURL(/\/new\/settings$/);
  await page.goto(`/#/projects/${projectId}/history`);
  await expect(page.getByRole('tab', {name: '歷史 Task'})).toHaveAttribute('aria-selected','true');
  await page.getByRole('button', {name: '建立 Task', exact: true}).click();
  await expect(page).toHaveURL(new RegExp(projectId+'/tasks/new$'));
  await expect(page.getByLabel('所屬專案', {exact: true})).toHaveValue(name);
  await page.getByRole('button', {name: '← 返回專案設定', exact: true}).click();
  await expect(page.getByLabel('專案名稱', {exact: false})).toHaveValue(name);
  await page.setViewportSize({width: 900, height: 900});
  await expect(page.getByRole('button', {name: '儲存設定', exact: true})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
  await page.screenshot({path: test.info().outputPath('project-settings.png'), fullPage: true});
  expect(errors).toEqual([]);
  await page.getByRole('button', {name: '建立 Task', exact: true}).click();
  await page.getByLabel('Task 名稱', {exact: true}).fill('UI實際建立 Task');
  await page.getByLabel('需求描述', {exact: true}).fill('這是合成 CSV 上傳與專案歸屬驗收，不執行資料庫寫入');
  await Promise.all([
    page.waitForResponse(r => r.url().endsWith('/api/task-sources/upload') && r.request().method() === 'POST'),
    page.locator('input[type="file"]').setInputFiles({name: 'synthetic.csv', mimeType: 'text/csv', buffer: Buffer.from('customer_id,amount\n001,12.50\n')})
  ]);
  const created = page.waitForResponse(r => r.url().endsWith('/api/tasks') && r.request().method() === 'POST');
  await page.getByRole('button', {name: '建立 Task', exact: true}).click();
  const result = await created;
  expect(result.status()).toBe(201);
  expect((await result.json()).project_id).toBe(projectId);
  await page.getByRole('tab', {name: '需求與規格', exact: true}).click();
  await expect(page.getByRole('heading', {name: '建立 Task 的完整設定'})).toBeVisible();
});

test('歷史 Task 保留建立內容、節點、Job 頁面及返回路徑', async ({page, request}) => {
  expect((await (await request.get('/api/ready')).json()).execution_enabled).toBe(false);
  const project = await (await request.post('/api/projects', {data: {project_name: '歷史驗收-'+Date.now()}})).json();
  const response = await request.post(`/api/projects/${project.project_id}/tasks`, {data: {
    name: '歷史節點驗收', requirement: '保留原始建立需求與客戶編號欄位，這筆合成 Task 不執行 ETL',
    source_config: {sources: [{type: 'CSV', path: '/app/runtime-temp/synthetic-ui.csv', alias: 'synthetic', has_actual_data: true}]},
    target_schema: 'ai_qa', target_table: 'ui_test', model: 'nova-default',
  }});
  expect(response.status()).toBe(201);
  const task = await response.json();
  await page.goto(`/#/projects/${project.project_id}/history`);
  await page.getByRole('button', {name: /歷史節點驗收/}).click();
  await expect(page).toHaveURL(new RegExp('/tasks/'+task.id+'$'));
  const readiness = page.getByRole('region', {name: 'Pilot 執行準備'});
  await expect(readiness.getByText('設定尚未完整', {exact: true})).toBeVisible();
  await expect(readiness.getByText(/此角色尚未指定模型/)).toBeVisible();
  const checked = page.waitForResponse(r => r.url().endsWith('/execution-settings'));
  await readiness.getByRole('button', {name: '重新檢查設定'}).click();
  expect((await checked).status()).toBe(200);
  await page.getByRole('tab', {name: '需求與規格', exact: true}).click();
  await expect(page.getByRole('heading', {name: '建立 Task 的完整設定'})).toBeVisible();
  await expect(page.getByText('保留原始建立需求與客戶編號欄位，這筆合成 Task 不執行 ETL', {exact: true})).toBeVisible();
  await page.reload();
  await expect(page.getByRole('tab', {name: '需求與規格', exact: true})).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('tab', {name: '產物與流程', exact: true}).click();
  await expect(page.getByRole('heading', {name: '節點狀態', exact: true})).toBeVisible();
  await expect(page.locator('button.nodebutton')).toHaveCount(8);
  await page.getByRole('button', {name: /Rule Router/}).click();
  await expect(page.getByRole('heading', {name: 'Rule Router 詳細資訊', exact: true})).toBeVisible();
  await page.screenshot({path: test.info().outputPath('node-details.png'), fullPage: true});
  await page.getByRole('button', {name: '關閉節點詳情', exact: true}).click();
  await expect(page.getByRole('heading', {name: '所有 SQL', exact: true})).toBeVisible();
  await page.getByRole('tab', {name: '執行與 QA', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Apache Hop Log', exact: true})).toBeVisible();
  await page.getByRole('tab', {name: '交付', exact: true}).click();
  await expect(page.getByText(/尚無經新版完整 QA 與人工核准的 Release/)).toBeVisible();
  await expect(page.getByRole('link', {name: /Release ZIP/})).toHaveCount(0);
  await page.goBack();
  await expect(page.getByRole('tab', {name: '執行與 QA', exact: true})).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('button', {name: '← 返回此專案歷史 Task', exact: true}).click();
  await expect(page).toHaveURL(new RegExp(project.project_id+'/history$'));
  await expect(page.getByRole('button', {name: /歷史節點驗收/})).toBeVisible();
});
