import {test, expect} from '@playwright/test';
import {execFile} from 'node:child_process';
import {promisify} from 'node:util';
import path from 'node:path';

// Explicit operator consent is required before enabling this test.
// One CLI session; no model mocks, no automatic retry and no ETL execution.
test('單次真實 Copilot：網站授權 → Windows Worker → 結構驗證 → PostgreSQL → 網站', async ({page, request}) => {
  test.skip(process.env.WORKBENCH_REAL_COPILOT_SINGLE_CALL !== '1', 'Requires explicit operator authorization for one real Copilot session');
  test.setTimeout(240000);
  const original = (await (await request.get('/api/settings/groups')).json()).values.data_connections_targets;
  const suffix = Date.now();
  const profileId = 'copilot-pilot-'+suffix;
  const connectionId = 'sa-only-'+suffix;
  let taskId: string | undefined;
  let runId: string | undefined;
  try {
    expect((await request.put('/api/settings/ai-profiles/'+profileId, {data: {
      display_name: '本機 Copilot 單次 Pilot 驗收', provider_type: 'LOCAL_COPILOT',
      model_routes: {requirement_gate: 'gpt-5.4', etl_specification: 'gpt-5.4', qa_review: 'gpt-5.4'}, enabled: true,
    }})).status()).toBe(200);
    // Synthetic metadata only: this test must never connect to or claim to validate Vertica.
    expect((await request.put('/api/settings/groups/data_connections_targets', {data: {...original, etl_qa: {
      connection_id: connectionId, host: 'synthetic-sa-only.invalid', port: 5433, database: 'no_database_connection', user: 'synthetic',
    }}})).status()).toBe(200);
    const project = await (await request.post('/api/projects', {data: {
      project_name: 'Copilot 真實 SA 驗收-'+suffix, default_ai_profile: profileId, default_connection: connectionId,
    }})).json();
    const created = await request.post(`/api/projects/${project.project_id}/tasks`, {data: {
      name: '合成需求：單次 Copilot 審查',
      requirement: '從單一 CSV 讀取全部資料，不做日期篩選、不做 Join、不做聚合。customer_id 是 BIGINT、amount 是 NUMERIC(12,2)，兩欄不可為 null。原樣新增至 ai_sample.copilot_sa_review，不更新既有資料、不去除重複資料；遇到空值或型別轉換錯誤整批失敗。僅審查此需求，不執行 ETL。',
      source_config: {sources: [{type: 'CSV', alias: 'synthetic', has_actual_data: false, fields: [
        {name: 'customer_id', type: 'BIGINT', nullable: false}, {name: 'amount', type: 'NUMERIC', precision: 12, scale: 2, nullable: false},
      ]}], csv_input_contract_v1: {version: 1, encoding: 'UTF-8', delimiter: ',', header: true, extra_columns: 'REJECT'}}, target_schema: 'ai_sample', target_table: 'copilot_sa_review',
      target_config: {requirements_v1: {version: 1, write_mode: 'APPEND', date_scope: 'ALL'}},
    }});
    expect(created.status()).toBe(201);
    taskId = (await created.json()).id;
    await page.goto(`/#/projects/${project.project_id}/tasks/${taskId}/requirements`);
    const panel = page.getByRole('region', {name: '執行準備版本', exact: true});
    await panel.getByRole('button', {name: '建立準備版本', exact: true}).click();
    await panel.getByLabel('我已核對本次需求及設定版本').check();
    await panel.getByRole('button', {name: '確認此版輸入', exact: true}).click();
    runId = (await (await request.get(`/api/tasks/${taskId}/runs`)).json()).runs[0].run_id;
    await expect.poll(async () => (await (await request.get(`/api/tasks/${taskId}/runs/${runId}`)).json()).gate_result?.status, {timeout: 20000}).toBe('CHECKED');
    await panel.getByRole('button', {name: '重新載入版本', exact: true}).click();
    const sa = panel.getByRole('region', {name: 'SA 呼叫狀態'});
    await sa.getByRole('button', {name: '重新載入 SA 狀態'}).click();
    await expect(sa).toContainText('只啟動 1 次 CLI');
    const authorize = sa.getByRole('button', {name: '授權並排入 SA 工作'});
    await expect(authorize).toBeDisabled();
    await sa.getByRole('checkbox', {name: '我同意此版本的 SA 模型呼叫及上述用量限制'}).check();
    await authorize.click();
    await expect(sa).toContainText('已授權並排隊');
    const root = path.resolve('..');
    const worker = await promisify(execFile)(path.join(root, '.venv', 'Scripts', 'python.exe'),
      ['-m', 'app.local_sa_worker', '--task-id', taskId!, '--run-id', runId!],
      {cwd: path.join(root, 'backend'), timeout: 210000, windowsHide: true});
    const outcome = JSON.parse(worker.stdout.trim());
    await test.info().attach('worker-result', {body: JSON.stringify(outcome, null, 2), contentType: 'application/json'});
    expect(outcome.status).toBe('VALIDATED_NOT_APPROVED');
    await sa.getByRole('button', {name: '重新載入 SA 狀態'}).click();
    await expect(sa).toContainText('結構驗證通過，尚未人工核准');
    const record = await (await request.get(`/api/tasks/${taskId}/runs/${runId}/sa-invocation`)).json();
    expect(record.invocation.provider).toBe('LOCAL_COPILOT');
    expect(record.invocation.model).toBe('copilot/gpt-5.4');
    expect(record.invocation.usage.cli_sessions).toBe(1);
    expect(record.invocation.usage.automatic_retries).toBe(0);
    expect(record.invocation.usage.tool_execution_count).toBe(0);
    expect(record.execution_authorized).toBe(false);
    const run = await (await request.get(`/api/tasks/${taskId}/runs/${runId}`)).json();
    expect(run.write_started).toBe(false);
    await test.info().attach('real-sa-evidence', {body: JSON.stringify({project_id: project.project_id, task_id: taskId, run_id: runId, record}, null, 2), contentType: 'application/json'});
    await page.screenshot({path: test.info().outputPath('copilot-real-sa.png'), fullPage: true});
    console.log(JSON.stringify({project_id: project.project_id, task_id: taskId, run_id: runId, status: record.invocation.status, usage: record.invocation.usage}));
  } finally {
    if (taskId && runId) {
      await request.post(`/api/tasks/${taskId}/runs/${runId}/sa-invocation/cancel`);
      await request.post(`/api/tasks/${taskId}/runs/${runId}/cancel`);
    }
    expect((await request.put('/api/settings/groups/data_connections_targets', {data: original})).status()).toBe(200);
  }
});
