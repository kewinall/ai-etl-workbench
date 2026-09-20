import {test, expect} from '@playwright/test';

test('設定政策儲存重載與伺服器限制', async ({page, request}) => {
  const ready = await request.get('/api/ready');
  expect((await ready.json()).execution_enabled).toBe(false);
  const endpoint = '/api/settings/groups/validation_release_policy';
  const original = (await (await request.get('/api/settings/groups')).json()).values.validation_release_policy;
  try {
    await page.goto('/#/system');
    for (const [category, heading] of [
      ['資料連線與目標', '資料連線與目標'],
      ['機密與部署安全', '資料庫連線機密'],
    ]) {
      await page.getByRole('button', {name: category, exact: true}).click();
      await expect(page.getByRole('heading', {name: heading, exact: true})).toBeVisible();
    }
    await page.setViewportSize({width: 390, height: 844});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.setViewportSize({width: 1440, height: 1000});
    await page.getByRole('button', {name: '資料治理與命名', exact: true}).click();
    await expect(page.getByLabel('受控範例 Schema')).toHaveAttribute('readonly', '');
    await page.getByRole('button', {name: '驗證與交付', exact: true}).click();
    await expect(page.getByRole('heading', {name: '驗證與交付策略'})).toBeVisible();
    await expect(page.getByLabel('受控範例 Schema')).toHaveAttribute('readonly', '');
    await expect(page.getByLabel('Release 前必須確認 Naming Contract')).toBeDisabled();
    await page.getByLabel('範例資料筆數').fill('7');
    await page.getByRole('button', {name: '執行環境與路徑', exact: true}).click();
    await expect(page.getByRole('heading', {name: '執行環境與工具路徑', exact: true})).toBeVisible();
    await expect(page.getByRole('heading', {name: '驗證與交付策略'})).not.toBeVisible();
    await page.getByRole('button', {name: '驗證與交付', exact: true}).click();
    await expect(page.getByLabel('範例資料筆數')).toHaveValue('7');
    const saved = page.waitForResponse(r => r.url().endsWith(endpoint) && r.request().method() === 'PUT');
    await page.getByRole('button', {name: '儲存驗證策略'}).click();
    expect((await saved).status()).toBe(200);
    await page.reload();
    await page.getByRole('button', {name: '驗證與交付', exact: true}).click();
    await expect(page.getByLabel('範例資料筆數')).toHaveValue('7');
    for (const path of [endpoint, '/api/settings/validation_release_policy']) {
      const rejected = await request.put(path, {data: {sample_rows: 7, require_naming_contract: false}});
      expect(rejected.status()).toBe(422);
    }
    const stored = (await (await request.get('/api/settings/groups')).json()).values.validation_release_policy;
    expect(stored).toEqual({sample_rows: 7, require_naming_contract: true});
  } finally {
    const restored = await request.put(endpoint, {data: original});
    expect(restored.status()).toBe(200);
  }
});
