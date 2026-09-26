import {test, expect} from '@playwright/test';

for (const version of [1,2]) test(`規格歷史與核准互動 V${version}（瀏覽器合成回應，非資料庫核准驗收）`, async ({page, request}) => {
  const project = await (await request.post('/api/projects', {data: {project_name: '規格UI-'+Date.now()}})).json();
  const response = await request.post(`/api/projects/${project.project_id}/tasks`, {data: {name: '規格UI', requirement: 'UI only', source_config: {sources: [{type: 'CSV', has_actual_data: false, fields: [{name: 'id', type: 'BIGINT'}]}]}, target_schema: 'ai_sample', target_table: 'ui_only'}});
  expect(response.status()).toBe(201);
  const task = await response.json();
  const runId = '00000000-0000-4000-8000-000000000001';
  const base = `**/api/tasks/${task.id}/runs`;
  const run = {run_id: runId, state: 'NEEDS_REVIEW', created_at: '2026-09-13T00:00:00Z', input_summary: {}, settings_summary: {}, events: [], matches_current: true};
  await page.route(base, route => route.fulfill({json: {runs: [run]}}));
  await page.route(`${base}/${runId}`, route => route.fulfill({json: run}));
  const spec = {target_schema: 'ai_sample', target_table: 'totals', write_mode: 'APPEND', source_ref: 'source.0', naming: {version: 1}, filters: [{column: 'amount', operator: 'GT', constant: {value: '100.00'}}], aggregation: {group_by: ['category'], metrics: [{id: 'sum', output_column: 'total_amount', function: 'SUM', column: 'amount'}]}, output_columns: ['category', 'total_amount']};
  let approved = false;
  const joins = [{id:'join_customers',left_source:'source.0',right_source:'source.1',join_type:'LEFT',
    keys:[{left_column:'客戶編號',right_column:'客戶編號'}],null_key_policy:'NEVER_MATCH',
    duplicate_key_policy:'EXPAND',string_comparison:'CASE_SENSITIVE_NO_TRIM'}];
  if (version === 2) Object.assign(spec,{version:2,source_refs:['source.0','source.1'],joins});
  let stale = false;
  let approvals = 0;
  await page.route(`${base}/${runId}/specifications`, route => route.fulfill({json: {items: [{specification_id: 's1', version: 1, spec_json: spec, content_checksum: 'a'.repeat(64), reviewable: !stale, approval_id: approved ? 'approval1' : null, approval_effective: approved && !stale}]}}));
  await page.route(`${base}/${runId}/specifications/s1/approve`, async route => {
    expect(route.request().postDataJSON()).toEqual({content_checksum: 'a'.repeat(64)});
    approvals++; approved = true;
    await route.fulfill({json: {status: 'SPEC_APPROVED_NOT_EXECUTABLE', execution_authorized: false}});
  });
  await page.route(`${base}/${runId}/specification/compile-preview`, route => route.fulfill({json: {status: 'VALIDATED_NOT_APPROVED', plan: {stages: [{id: 'source', component: 'CSVInput'}]}, hpl: '<pipeline>UI fixture only</pipeline>'}}));
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`/#/projects/${project.project_id}/tasks/${task.id}/requirements`);
  const panel = page.getByRole('region', {name: 'ETL 規格版本', exact: true});
  await panel.getByRole('button', {name: '載入規格版本'}).click();
  await expect(panel).toContainText('amount 大於 100.00');
  if (version === 2) {
    const join = panel.getByRole('region',{name:'Join 關聯規則'});
    await expect(join).toContainText('LEFT JOIN：保留左側未匹配資料');
    await expect(join).toContainText('source.1.客戶編號');
    await expect(join).toContainText('NULL 不互相匹配');
    await expect(join).toContainText('展開所有匹配組合');
  }
  await expect(panel.getByRole('button', {name: '核准此版規格'})).toBeDisabled();
  await panel.getByRole('checkbox').check();
  await panel.getByRole('button', {name: '核准此版規格'}).click();
  await expect(panel).toContainText('此規格核准目前有效');
  if (version === 2) {
    await page.route(`${base}/${runId}/specifications/s1/sdm-preview`,route=>route.fulfill({json:{
      status:'SDM_CANDIDATE_NOT_RELEASED',qa_passed:false,release_ready:false,checksum:'b'.repeat(64),
      document:{version:2,document_type:'SDM_CANDIDATE',specification_checksum:'a'.repeat(64),
        source_refs:['source.0','source.1'],joins,target:{schema:'ai_sample',table:'totals',write_mode:'APPEND'},
        filter_logic:'ALL',filter_null_policy:'EXCLUDE_UNKNOWN',filters:[],aggregation:null,naming:{checksum:'c'.repeat(64)},
        mappings:[{position:1,target_column:'right_id',target_type:'VARCHAR(32)',operation:'DIRECT',
          source_columns:[{source_ref:'source.1',original_name:'客戶編號',stream_name:'right_id'}]}]}}}));
    await panel.getByRole('button',{name:'預覽 SDM 欄位對照'}).click();
    const sdm=panel.getByRole('region',{name:'SDM 欄位對照預覽',exact:true});
    await expect(sdm).toContainText('source.1.客戶編號 → right_id');
    await expect(sdm.getByRole('region',{name:'Join 關聯規則'})).toContainText('LEFT JOIN');
    await expect(sdm.getByRole('alert')).toHaveCount(0);
  }
  expect(approvals).toBe(1);
  await panel.getByRole('button', {name: '檢查 Hop 編譯預覽'}).click();
  await panel.getByText('查看 HPL 候選（非交付產物）').click();
  await expect(panel.locator('details').filter({has:page.getByText('查看 HPL 候選（非交付產物）',{exact:true})}).locator('pre')).toContainText('UI fixture only');
  await page.route(`${base}/${runId}/specification/editor-context`, route => route.fulfill({json: {status:'EDITOR_CONTEXT_READY', binding: {run_id:runId, naming:{version:1}, target_schema:'ai_sample', target_table:'totals', write_mode:'APPEND'}, source_columns:[{name:'category',source_name:'類別',data_type:'VARCHAR(32)',constant_type:'STRING'},{name:'amount',source_name:'金額',data_type:'NUMERIC(12,2)',constant_type:'DECIMAL'}], metric_columns:[{id:'sum',output_column:'total_amount',data_type:'NUMERIC(18,2)'}]}}));
  let saved = 0;
  if (version === 2) await page.route(`${base}/${runId}/specification/editor-context`,route=>route.fulfill({json:{
    status:'EDITOR_CONTEXT_READY',binding:{version:2,run_id:runId,naming:{version:1},target_schema:'ai_sample',target_table:'totals',write_mode:'APPEND',source_refs:['source.0','source.1'],joins},
    source_columns:[{name:'category',source_name:'source.0.類別',data_type:'VARCHAR(32)',constant_type:'STRING'},
      {name:'amount',source_name:'source.1.金額',data_type:'NUMERIC(12,2)',constant_type:'DECIMAL'}],
    metric_columns:[{id:'sum',output_column:'total_amount',data_type:'NUMERIC(18,2)'}]}}));
  await page.route(`${base}/${runId}/specifications`, async route => {
    if (route.request().method() === 'POST') {
      if(version===2) expect(route.request().postDataJSON().joins).toEqual(joins);
      expect(route.request().postDataJSON().filters[0]).toEqual({column:'amount',operator:'GT',constant:{type:'DECIMAL',value:'200.00'}});
      expect(route.request().postDataJSON().aggregation.metrics[0]).toEqual({id:'sum',output_column:'total_amount',function:'SUM',column:'amount'});
      saved++;
      return route.fulfill({json:{status:'SAVED_NOT_EXECUTABLE',execution_authorized:false}});
    }
    return route.fallback();
  });
  await panel.getByRole('button', {name:'以此規格編輯新版'}).click();
  const editor = panel.getByRole('region', {name:'編輯 ETL 規格'});
  await editor.getByRole('button', {name:'讀取已確認欄位'}).click();
  if(version===2) await expect(editor.getByRole('region',{name:'Join 關聯規則'})).toContainText('join_customers');
  await editor.getByLabel('比較值（日期 YYYY-MM-DD，布林 true／false）').fill('200.00');
  await page.setViewportSize({width:390,height:1000});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  await expect(editor.getByRole('button', {name:'驗證並保存規格新版'})).toBeDisabled();
  await editor.getByLabel('我已確認篩選、分組、聚合及輸出順序，保存為待核准規格。').check();
  await editor.getByRole('button', {name:'驗證並保存規格新版'}).click();
  await expect(panel).toContainText('已保存待核准規格');
  expect(saved).toBe(1);
  await panel.getByRole('button', {name:'建立規格',exact:true}).click();
  await editor.getByRole('button', {name:'讀取已確認欄位'}).click();
  await expect(editor.getByLabel('篩選方式')).toHaveValue('');
  await expect(editor.getByRole('button', {name:'驗證並保存規格新版'})).toBeDisabled();
  await editor.getByRole('button', {name:'取消規格編輯'}).click();
  await page.setViewportSize({width: 390, height: 1000});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({path: test.info().outputPath('specification-page.png'), fullPage: true});
  stale = true;
  await panel.getByRole('button', {name: '重新整理規格版本'}).click();
  await expect(panel).toContainText('歷史核准已失效');
  await expect(panel.getByRole('button', {name: '核准此版規格'})).toHaveCount(0);
  await expect(panel.getByRole('button', {name: '檢查 Hop 編譯預覽'})).toBeDisabled();
  expect(errors).toEqual([]);
  await page.route(`${base}/${runId}/sa-invocation`, route => route.fulfill({json: {invocation: null}}));
  await page.route(`${base}/${runId}`, route => route.fulfill({json: {...run, events: [{event_id: 1, event_type: 'SPECIFICATION_APPROVED', phase: 'SPEC_VALIDATION', created_at: run.created_at, event_context: {specification_id: 's1', version: 1, checksum: 'a'.repeat(64), approval_id: 'approval1'}}]}}));
  await page.getByRole('tab', {name: '協作紀錄', exact: true}).click();
  const timeline = page.getByRole('region', {name: '版本協作紀錄'});
  await expect(timeline).toContainText('人工核准規格（非執行授權）');
  await expect(timeline).toContainText('規格第 1 版');
  await expect(timeline).toContainText('這是當時的操作紀錄');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
});
