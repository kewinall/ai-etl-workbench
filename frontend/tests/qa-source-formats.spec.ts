import {test, expect} from '@playwright/test';

for (const format of ['CSV', 'JOIN', 'XLSX', 'JSON', 'UNKNOWN']) test(`QA 來源 ${format} 合成歷史呈現，不是模型或資料庫驗收`, async ({page, request}) => {
  expect(process.env.WORKBENCH_TEST_URL).toBe('http://127.0.0.1:5195');
  const project = await (await request.post('/api/projects', {data: {project_name: `QA格式-${format}-${Date.now()}`}})).json();
  const response = await request.post(`/api/projects/${project.project_id}/tasks`, {data: {name: 'QA格式呈現', requirement: 'Synthetic UI only',
    source_config: {sources: [{type: 'CSV', has_actual_data: false, fields: [{name: 'id', type: 'BIGINT'}]}]}, target_schema: 'ai_sample', target_table: 'ui_only'}});
  expect(response.status()).toBe(201);
  const task = await response.json(), runId = '00000000-0000-4000-8000-000000000001';
  const base = `**/api/tasks/${task.id}/runs`, run = {run_id: runId, state: 'NEEDS_REVIEW', created_at: '2026-09-13T00:00:00Z', input_summary: {}, settings_summary: {}, events: [], matches_current: true};
  await page.route(base, route => route.fulfill({json: {runs: [run]}}));
  await page.route(`${base}/${runId}`, route => route.fulfill({json: run}));
  const csv = {encoding: 'UTF-8', header: true, extra_columns: 'REJECT'};
  const details: any = {output_types: {id: 'BIGINT'}, compiler_plan: {stages: [{id: 'source', component: format === 'JSON' ? 'JsonInput' : format === 'XLSX' ? 'ExcelInput' : 'CSVInput'}]}};
  if (format === 'CSV') Object.assign(details, {csv_input_contract: csv, csv_structure_validation: {records_checked: 3}});
  if (format === 'JOIN') Object.assign(details, {csv_input_contracts: {'source.0': csv, 'source.1': csv}, csv_structure_validations: {'source.0': {records_checked: 3}, 'source.1': {records_checked: 2}}});
  if (format === 'XLSX') Object.assign(details, {source_format: 'XLSX', excel_input_contract: {worksheet: '明細', header_row: 2, blank_rows: 'PRESERVE'}, excel_structure_validation: {records_expected: 3}});
  if (format === 'JSON') Object.assign(details, {source_format: 'JSON', json_input_contract: {root_shape: 'ARRAY'}, json_structure_validation: {records_expected: 3},
    source_checksum: 'a'.repeat(64), json_reader: {normalization: 'UTF8_BOM_REMOVED', reader_checksum: 'b'.repeat(64)}, json_runtime_receipt: {HOP_JSON_INPUT_INCLUDE_NULLS: 'Y', log_checksum: 'c'.repeat(64)}});
  const item = {invocation_id: 'synthetic-ui', status: 'VALIDATED_NOT_APPROVED', model: 'synthetic-not-called', prompt_version: format === 'JSON' ? 12 : 11,
    created_at: '2026-09-13T00:00:00Z', context_checksum: 'd'.repeat(64), duration_ms: null, usage: null,
    context: {specification_checksum: 'e'.repeat(64), evidence: [{id: 'result_source', status: 'MISSING', summary: 'Synthetic UI only'}],
      semantics: {requirement: '合成畫面測試', specification: {write_mode: 'APPEND', output_columns: ['id'], filters: [], aggregation: null},
        nodes: [{id: 'source', component: details.compiler_plan.stages[0].component}], execution_details: details}},
    review: {status: 'NEEDS_REVIEW', summary: '缺少真實結果來源', issues: [{message: '合成回應不作驗收證據', evidence_ids: ['result_source']}]}};
  await page.route(`${base}/${runId}/qa-review`, route => route.fulfill({json: {run_id: runId, invocation: item, history: [item], matches_current: true, qa_approved: false, release_ready: false}}));
  const errors: string[] = []; page.on('pageerror', e => errors.push(e.message));
  await page.goto(`/#/projects/${project.project_id}/tasks/${task.id}/execution`);
  const qa = page.getByRole('region', {name: 'QA 審查紀錄', exact: true});
  await qa.getByText('當時的語意審查依據', {exact: true}).click();
  const panel = qa.getByRole('region', {name: 'QA 來源證據', exact: true});
  await expect(panel).toBeVisible();
  if (format === 'JSON') {await expect(panel).toContainText('僅移除開頭 UTF-8 BOM'); await expect(panel).toContainText('已保存；仍須配合執行及結果比對證據'); await expect(panel).not.toContainText('CSV 來源')}
  else if (format === 'XLSX') {await expect(panel).toContainText('工作表：明細；標頭：第 2 列'); await expect(panel).not.toContainText('CSV 來源')}
  else if (format === 'JOIN') {await expect(panel.getByRole('region', {name: 'CSV 來源 source.0'})).toContainText('3 筆'); await expect(panel.getByRole('region', {name: 'CSV 來源 source.1'})).toContainText('2 筆')}
  else if (format === 'CSV') await expect(panel).toContainText('來源完整掃描：3 筆');
  else await expect(panel).toContainText('沒有可辨識的來源讀取證據');
  await expect(qa).toContainText('QA 建議：NEEDS_REVIEW');
  await page.setViewportSize({width: 390, height: 1000});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
  await panel.screenshot({path: test.info().outputPath(`qa-source-${format}.png`)});
  await qa.getByRole('button', {name: '重新讀取 QA 審查'}).click();
  await expect(qa).toContainText('QA 建議：NEEDS_REVIEW');
  expect(errors).toEqual([]);
});
