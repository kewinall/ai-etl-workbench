import {test, expect} from '@playwright/test';

test('未驗收來源保留設定入口但不承諾或觸發執行', async ({page, request}) => {
  expect((await (await request.get('/api/ready')).json()).execution_enabled).toBe(false);
  const projectResponse = await request.post('/api/projects', {data: {project_name: `來源範圍-${Date.now()}`}});
  expect(projectResponse.status()).toBe(201);
  const project = await projectResponse.json();
  const mutations: string[] = [], errors: string[] = [];
  page.on('request', r => {if (!['GET', 'HEAD', 'OPTIONS'].includes(r.method())) mutations.push(r.url())});
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(`/#/projects/${project.project_id}/tasks/new`);
  await expect(page.getByRole('region', {name: '來源支援範圍'})).toContainText('尚未完成新版真實執行驗收');
  for (const mode of ['External Table', 'Flex Table']) {
    await page.getByRole('button', {name: new RegExp(`^${mode}`)}).click();
    await expect(page.getByText('僅保存 Server 來源需求，尚未接通新版執行', {exact: true})).toBeVisible();
    await expect(page.getByText(/此入口不會轉送檔案、建立 External／Flex Table/)).toBeVisible();
    await page.getByRole('button', {name: /^產生範例檔案/}).click();
    await expect(page.getByText('僅保存範例檔案需求；尚未接通新版產生流程', {exact: true})).toBeVisible();
    await page.getByRole('button', {name: /^上傳實際檔案/}).click();
  }
  await page.getByRole('button', {name: /^ODS/}).click();
  await page.getByRole('button', {name: /^建立範例資料表/}).click();
  await expect(page.getByText('僅保存範例表需求；不會在此建立或重建資料表', {exact: true})).toBeVisible();
  await expect(page.getByRole('textbox', {name: '預計資料表名稱（可留空）'})).toBeVisible();
  await page.setViewportSize({width: 390, height: 1000});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  await page.screenshot({path: test.info().outputPath('sample-source-scope.png'), fullPage: true});
  expect(mutations).toEqual([]);
  expect(errors).toEqual([]);
  const tasks = await request.get(`/api/projects/${project.project_id}/tasks`);
  expect(tasks.status()).toBe(200);
  expect(await tasks.json()).toEqual([]);
});
