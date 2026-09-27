import {test, expect} from '@playwright/test';

test('轉換意圖逐欄位補正、保存重載與歷史隔離（真實隔離 API，無模型或 ETL）', async ({page, request}) => {
  page.setDefaultTimeout(10000);
  const ready = await (await request.get('/api/ready')).json();
  expect(ready.execution_enabled).toBe(false);
  const suffix = Date.now(), profile = 'intent-ui-' + suffix, connection = 'intent-conn-' + suffix;
  const settings = (await (await request.get('/api/settings/groups')).json()).values.data_connections_targets;
  try {
    expect((await request.put('/api/settings/ai-profiles/' + profile, {data: {display_name: 'Synthetic intent UI', provider_type: 'LITELLM_BEDROCK', region: 'us-east-1', enabled: true, model_routes: {requirement_gate: 'bedrock/synthetic', etl_specification: 'bedrock/synthetic', qa_review: 'bedrock/synthetic'}}})).ok()).toBe(true);
    expect((await request.put('/api/settings/groups/data_connections_targets', {data: {...settings, etl_qa: {connection_id: connection, host: 'synthetic-no-connection', port: 5433, database: 'synthetic', user: 'synthetic'}}})).ok()).toBe(true);
    const project = await (await request.post('/api/projects', {data: {project_name: 'Intent UI ' + suffix, default_ai_profile: profile, default_connection: connection}})).json();
    const response = await request.post(`/api/projects/${project.project_id}/tasks`, {data: {name: 'Intent UI', requirement: '金額大於 100，依類別分組計數；只測試需求保存。', source_config: {sources: [{type: 'CSV', alias: 'synthetic', has_actual_data: false, fields: [{name: 'category', type: 'VARCHAR(32)'}, {name: 'amount', type: 'BIGINT'}]}], csv_input_contract_v1: {version: 1, encoding: 'UTF-8', delimiter: ',', header: true, extra_columns: 'REJECT'}}, target_schema: 'ai_sample', target_table: 'synthetic_intent'}});
    expect(response.status()).toBe(201);
    const task = (await response.json()).id;
    await page.goto(`/#/projects/${project.project_id}/tasks/${task}/requirements`);
    const panel = page.getByRole('region', {name: '執行準備版本', exact: true});
    await panel.getByRole('button', {name: '建立準備版本', exact: true}).click();
    await panel.getByLabel('我已核對本次需求及設定版本').check();
    await panel.getByRole('button', {name: '確認此版輸入', exact: true}).click();
    const parent = (await (await request.get(`/api/tasks/${task}/runs`)).json()).runs[0];
    await expect.poll(async () => (await (await request.get(`/api/tasks/${task}/runs/${parent.run_id}`)).json()).state, {timeout: 20000}).toBe('NEEDS_REVIEW');
    await panel.getByRole('button', {name: '重新載入版本', exact: true}).click();
    await panel.getByRole('button', {name: '補正需求並建立新版', exact: true}).click();
    const form = panel.getByRole('form', {name: '需求補正'});
    await form.getByRole('button', {name: '新增轉換意圖', exact: true}).click();
    await form.getByRole('button', {name: '新增篩選', exact: true}).click();
    await form.getByLabel('篩選欄位 1', {exact: true}).selectOption('source.0.amount');
    await form.getByLabel('比較方式 1', {exact: true}).selectOption('GT');
    await form.getByLabel('常數型別 1', {exact: true}).selectOption('INTEGER');
    await form.getByLabel('常數值 1', {exact: true}).fill('100');
    await form.getByRole('combobox', {name: '聚合方式', exact: true}).selectOption('GROUP');
    await form.getByLabel('source.0.category', {exact: true}).check();
    await form.getByRole('button', {name: '新增聚合指標', exact: true}).click();
    await form.getByLabel('指標識別 1', {exact: true}).fill('row_count');
    await form.getByLabel('聚合函數 1', {exact: true}).selectOption('COUNT_ROWS');
    await expect(form.getByLabel('聚合來源 1', {exact: true})).toHaveCount(0);
    await form.getByRole('button', {name: '新增輸出欄位', exact: true}).click();
    await form.getByLabel('輸出欄位 1', {exact: true}).selectOption('source.0.category');
    await form.getByRole('button', {name: '新增輸出欄位', exact: true}).click();
    await form.getByLabel('輸出欄位 2', {exact: true}).selectOption('$metric.row_count');
    await form.getByRole('combobox', {name: '寫入模式', exact: true}).selectOption('APPEND');
    await form.getByRole('combobox', {name: '資料期間', exact: true}).selectOption('ALL');
    await page.setViewportSize({width: 390, height: 900});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
    const saved = page.waitForResponse(r => r.url().endsWith('/revisions') && r.request().method() === 'POST');
    await form.getByRole('button', {name: '保存補正並建立新版', exact: true}).click();
    const result = await saved; expect(result.status()).toBe(201);
    // The application reloads after save; verify persisted state through the
    // API instead of reading a browser response body discarded by navigation.
    const childId = (await (await request.get(`/api/tasks/${task}/runs`)).json()).runs[0].run_id;
    const child = await (await request.get(`/api/tasks/${task}/runs/${childId}`)).json();
    const wanted = child.input_summary.transformation_contract_v1;
    expect(wanted.filters[0].constant).toEqual({type: 'INTEGER', value: 100});
    expect(wanted.aggregation.metrics).toEqual([{id: 'row_count', function: 'COUNT_ROWS', column: null}]);
    expect(wanted.output_columns).toEqual(['source.0.category', '$metric.row_count']);
    await expect(page.getByRole('region', {name: '已保存轉換意圖'})).toContainText('COUNT_ROWS');
    await page.reload();
    await expect(page.getByRole('region', {name: '已保存轉換意圖'})).toContainText('INTEGER 100');
    const persisted = await (await request.get(`/api/tasks/${task}/runs/${child.run_id}`)).json();
    expect(persisted.input_summary.transformation_contract_v1).toEqual(wanted);
    expect(persisted.approval).toBeNull(); expect(persisted.write_started).toBe(false);
    const old = await (await request.get(`/api/tasks/${task}/runs/${parent.run_id}`)).json();
    expect(old.input_summary.transformation_contract_v1).toBeNull(); expect(old.state).toBe('CANCELLED');
    expect((await (await request.get(`/api/tasks/${task}/runs/${child.run_id}/developer`)).json()).invocation).toBeNull();
  } finally {
    expect((await request.put('/api/settings/groups/data_connections_targets', {data: settings})).ok()).toBe(true);
  }
});
