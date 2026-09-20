import {test, expect} from '@playwright/test';

test('AI Profile 欄位編輯、取消、保存重載，不觸發付費呼叫', async ({page, request}) => {
  page.setDefaultTimeout(10000);
  expect((await (await request.get('/api/ready')).json()).execution_enabled).toBe(false);
  const profiles = await (await request.get('/api/settings/ai-profiles')).json();
  const original = profiles.find((p: any) => p.profile_id === 'nova-default');
  const {display_name, provider_type, endpoint, region, model_routes, enabled} = original;
  const restore = {display_name, provider_type, endpoint, region, model_routes, enabled};
  const calls: string[] = [];
  page.on('request', request => {if (request.url().includes('/test?role=')) calls.push(request.url())});
  try {
    await page.goto('/#/system');
    const editor = page.getByRole('region', {name: 'AI Profile nova-default', exact: true});
    await editor.getByLabel('AWS Region', {exact: true}).fill('unsaved-region');
    await expect(page.getByText('有 1 個 AI Profile 尚未儲存')).toBeVisible();
    page.once('dialog',dialog=>dialog.dismiss());
    await page.locator('.shell > aside nav').getByRole('button',{name:'專案工作區',exact:true}).click();
    await expect(editor.getByLabel('AWS Region',{exact:true})).toHaveValue('unsaved-region');
    await editor.getByRole('button', {name: '取消 AI 變更'}).click();
    await expect(editor.getByLabel('AWS Region', {exact: true})).toHaveValue(region || '');
    await editor.getByLabel('AWS Region', {exact: true}).fill('us-east-1');
    await editor.getByLabel('QA／證據審查模型', {exact: true}).fill('bedrock/amazon.nova-pro-v1:0');
    await expect(editor.getByRole('button', {name: '執行模型連線測試'})).toBeDisabled();
    await editor.getByRole('button', {name: '儲存 AI Profile'}).click();
    await expect(editor.getByRole('status')).toContainText('已儲存');
    await page.reload();
    await expect(editor.getByLabel('AWS Region', {exact: true})).toHaveValue('us-east-1');
    await expect(editor.getByLabel('QA／證據審查模型', {exact: true})).toHaveValue('bedrock/amazon.nova-pro-v1:0');
    await expect(editor.getByRole('button', {name: '執行模型連線測試'})).toBeDisabled();
    expect(calls).toEqual([]);
    await page.setViewportSize({width: 900, height: 1000});
    const iconSize = await page.locator('.shell > aside nav button svg').first().boundingBox();
    expect(iconSize?.height).toBeGreaterThanOrEqual(18);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
    await page.screenshot({path: test.info().outputPath('ai-settings.png'), fullPage: true});
  } finally {
    expect((await request.put('/api/settings/ai-profiles/nova-default', {data: restore})).status()).toBe(200);
  }
});
