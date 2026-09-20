import {test, expect} from '@playwright/test';

test('新增後延遲的專案讀取不可覆蓋使用者選擇平台繼承', async ({page, request}) => {
  const name = '專案載入競態-'+Date.now();
  await page.goto('/#/projects/new/settings');
  await page.getByLabel('專案名稱', {exact: false}).fill(name);
  // Wait for the initial new-project list to finish before isolating the post-create GET.
  await expect(page.getByText('讀取專案中…', {exact: true})).toHaveCount(0);
  let release!: () => void;
  let reached!: () => void;
  const held = new Promise<void>(resolve => {release = resolve});
  const pending = new Promise<void>(resolve => {reached = resolve});
  await page.route('**/api/projects', async route => {
    if (route.request().method() === 'GET') {reached(); await held}
    await route.continue();
  });
  try {
    await page.getByRole('button', {name: '建立專案', exact: true}).click();
    await pending;
    await expect(page).toHaveURL(/#\/projects\/[0-9a-f-]+\/settings$/);
    // A saved-looking but not-yet-hydrated form must not be editable.
    await expect(page.getByRole('combobox', {name: '預設 AI Profile', exact: true})).toHaveCount(0);
  } finally {release()}
  const projectId = page.url().split('/projects/')[1].split('/')[0];
  await page.getByRole('combobox', {name: '預設 AI Profile', exact: true}).selectOption('');
  await page.getByRole('combobox', {name: '預設資料連線', exact: true}).selectOption('');
  const savedRequest = page.waitForRequest(r => r.method() === 'PUT' && r.url().endsWith(`/api/projects/${projectId}`));
  await page.getByRole('button', {name: '儲存設定', exact: true}).click();
  const sent = (await savedRequest).postDataJSON();
  expect(sent.default_ai_profile).toBe('');
  expect(sent.default_connection).toBe('');
  await expect(page.getByRole('status').filter({hasText: '已儲存；重新載入後仍可保留設定'})).toBeVisible();
  const persisted = await (await request.get(`/api/projects/${projectId}`)).json();
  expect(persisted.default_ai_profile).toBe('');
  await page.reload();
  await expect(page.getByRole('combobox', {name: '預設 AI Profile', exact: true})).toHaveValue('');
});
