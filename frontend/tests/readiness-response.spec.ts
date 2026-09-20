import {test, expect} from '@playwright/test';

test('設定準備提示拒絕不明回應並可恢復（合成檢查回應，無模型或 ETL）', async ({page, request}) => {
  const project = await (await request.post('/api/projects', {data: {project_name: '準備提示-'+Date.now()}})).json();
  const created = await request.post(`/api/projects/${project.project_id}/tasks`, {data: {name: '準備提示', requirement: '只測設定提示', source_config: {sources: [{type: 'CSV', has_actual_data: false, fields: [{name: 'id', type: 'BIGINT'}]}]}, target_schema: 'ai_sample', target_table: 'readiness_only'}});
  expect(created.status()).toBe(201);
  const task = await created.json();
  let response: any = {status: 'BLOCKED', issues: [{code: 'SETTINGS_GROUP_INVALID', group: 'data_connections_targets'}], execution_enabled: false};
  await page.route(`**/api/tasks/${task.id}/execution-settings`, r => r.fulfill({json: response}));
  await page.goto(`/#/projects/${project.project_id}/tasks/${task.id}/overview`);
  const panel = page.getByRole('region', {name: 'Pilot 執行準備'});
  await expect(panel).toContainText('平台設定格式不合法');
  await expect(panel).toContainText('資料連線與目標');
  for (const invalid of [{}, {status: 'UNKNOWN', issues: []}, {status: 'CONFIGURED_NOT_TESTED'}, {status: 'CONFIGURED_NOT_TESTED', issues: [{code: 'CONNECTION_NOT_CONFIGURED'}]}]) {
    response = invalid;
    await panel.getByRole('button', {name: '重新檢查設定'}).click();
    await expect(panel.getByRole('alert')).toContainText('設定檢查回應不完整');
    await expect(panel.getByText('設定完整，尚未測試連線', {exact: true})).toHaveCount(0);
  }
  response = {status: 'CONFIGURED_NOT_TESTED', issues: [], execution_enabled: false};
  await panel.getByRole('button', {name: '重新檢查設定'}).click();
  await expect(panel).toContainText('設定完整，尚未測試連線');
  await expect(panel.getByRole('alert')).toHaveCount(0);
  await page.setViewportSize({width: 390, height: 1000});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+2)).toBe(true);
});
