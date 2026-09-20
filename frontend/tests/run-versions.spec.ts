import {test, expect} from '@playwright/test';

test('準備版本、輸入確認、設定異動失效、取消與拒絕', async ({page, request}) => {
  page.setDefaultTimeout(10000);
  expect((await (await request.get('/api/ready')).json()).execution_enabled).toBe(false);
  const original = (await (await request.get('/api/settings/groups')).json()).values.data_connections_targets;
  const suffix = Date.now();
  const profileId = 'review-ui-'+suffix;
  const connectionId = 'review-qa-'+suffix;
  const profile = {display_name: '合成版本確認測試', provider_type: 'LITELLM_BEDROCK', region: 'us-east-1', model_routes: {requirement_gate: 'bedrock/synthetic', etl_specification: 'bedrock/synthetic', qa_review: 'bedrock/synthetic'}, enabled: true};
  let taskId: string | undefined;
  try {
    expect((await request.put('/api/settings/ai-profiles/'+profileId, {data: profile})).status()).toBe(200);
    expect((await request.put('/api/settings/groups/data_connections_targets', {data: {...original, etl_qa: {connection_id: connectionId, host: 'synthetic-no-connection', port: 5433, database: 'synthetic', user: 'synthetic'}}})).status()).toBe(200);
    const project = await (await request.post('/api/projects', {data: {project_name: '版本確認驗收-'+suffix, default_ai_profile: profileId, default_connection: connectionId}})).json();
    const created = await request.post(`/api/projects/${project.project_id}/tasks`, {data: {name: '版本確認流程', requirement: '合成資料版本確認，不執行 ETL', source_config: {sources: [{type: 'CSV', alias: 'synthetic', has_actual_data: false, fields: [{name: 'customer_id', type: 'BIGINT'}]}]}, target_schema: 'ai_sample', target_table: 'synthetic'}});
    expect(created.status()).toBe(201);
    taskId = (await created.json()).id;
    await page.goto(`/#/projects/${project.project_id}/tasks/${taskId}/requirements`);
    const panel = page.getByRole('region', {name: '執行準備版本', exact: true});
    await panel.getByRole('button', {name: '建立準備版本', exact: true}).click();
    await expect(panel.getByRole('status')).toContainText('沒有啟動 ETL');
    await expect(panel.getByRole('button', {name: '確認此版輸入', exact: true})).toBeDisabled();
    await panel.getByLabel('我已核對本次需求及設定版本').check();
    await panel.getByRole('button', {name: '確認此版輸入', exact: true}).click();
    await expect(panel.getByRole('status')).toContainText('尚未授權 Hop');
    const first = (await (await request.get(`/api/tasks/${taskId}/runs`)).json()).runs[0];
    const detail = await (await request.get(`/api/tasks/${taskId}/runs/${first.run_id}`)).json();
    expect(detail.approval.decision).toBe('APPROVE');
    expect(detail.write_started).toBe(false);
    expect(detail.lease_token).toBeUndefined();
    await page.getByRole('tab', {name: '協作紀錄', exact: true}).click();
    const timeline = page.getByRole('region', {name: '版本協作紀錄'});
    await expect(timeline.getByText('人工操作 · 輸入確認', {exact: true})).toBeVisible();
    await expect(timeline.getByText(/APPROVE；不等於 Hop/)).toBeVisible();
    await page.getByRole('tab', {name: '需求與規格', exact: true}).click();
    if (process.env.WORKBENCH_TEST_CONTROL_WORKER === '1') {
      await expect.poll(async () => (await (await request.get(`/api/tasks/${taskId}/runs/${first.run_id}`)).json()).outcome_code, {timeout: 20000}).toBe('REQUIREMENT_NEEDS_INPUT');
      await panel.getByRole('button', {name: '重新載入版本'}).click();
      await expect(panel.getByRole('region', {name: '初步需求檢查結果'})).toContainText('請明確選擇新增、覆寫或鍵值合併');
      await expect(panel.getByRole('region', {name: '初步需求檢查結果'})).toContainText('請確認 CSV 編碼');
      await expect(panel.getByText(/REQUIREMENT_GATE_STARTED/)).toBeVisible();
      const checked = await (await request.get(`/api/tasks/${taskId}/runs/${first.run_id}`)).json();
      expect(checked.state).toBe('NEEDS_REVIEW');
      expect(checked.write_started).toBe(false);
      await page.screenshot({path: test.info().outputPath('control-worker-result.png'), fullPage: true});
      await panel.getByRole('button', {name: '補正需求並建立新版', exact: true}).click();
      const form = panel.getByRole('form', {name: '需求補正'});
      await form.getByLabel('補正後需求').fill('合成資料補正需求：保存歷史版本，不執行 ETL');
      await form.getByLabel('目標 Table').fill('corrected_synthetic');
      await page.getByRole('tab', {name: '概覽', exact: true}).click();
      await page.getByRole('tab', {name: '需求與規格', exact: true}).click();
      await expect(form.getByLabel('目標 Table')).toHaveValue('corrected_synthetic');
      await form.getByRole('button', {name: '放棄補正'}).click();
      await expect(form).toHaveCount(0);
      await panel.getByRole('button', {name: '補正需求並建立新版', exact: true}).click();
      await expect(form.getByLabel('目標 Table')).toHaveValue('synthetic');
      await form.getByLabel('補正後需求').fill('合成資料補正需求：保存歷史版本，不執行 ETL');
      await form.getByLabel('目標 Table').fill('corrected_synthetic');
      await form.getByRole('combobox', {name: '寫入模式', exact: true}).selectOption('APPEND');
      await form.getByRole('combobox', {name: '資料期間', exact: true}).selectOption('ALL');
      await form.getByRole('button', {name: '設定 CSV 輸入契約', exact: true}).click();
      await form.getByRole('combobox', {name: 'CSV 編碼', exact: true}).selectOption('UTF-8');
      await form.getByRole('combobox', {name: 'CSV 分隔符號', exact: true}).selectOption(',');
      await form.getByRole('combobox', {name: 'CSV 標題列', exact: true}).selectOption('true');
      await form.getByRole('combobox', {name: 'CSV 額外欄位', exact: true}).selectOption('REJECT');
      await page.setViewportSize({width: 390, height: 1000});
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2)).toBe(true);
      await form.locator('fieldset').filter({has: page.getByText('CSV 輸入契約補正', {exact: true})}).screenshot({path: test.info().outputPath('csv-contract-form.png')});
      await page.setViewportSize({width: 1440, height: 1000});
      await form.getByRole('button', {name: '編輯來源欄位', exact: true}).click();
      await form.getByRole('button', {name: '新增來源欄位', exact: true}).click();
      await form.getByLabel('欄位 2 名稱', {exact: true}).fill('created_date');
      await form.getByRole('combobox', {name: '欄位 2 型別', exact: true}).selectOption('DATE');
      await form.getByRole('button', {name: '保存補正並建立新版'}).click();
      await expect(panel.getByText('目標：ai_sample.corrected_synthetic', {exact: true})).toBeVisible();
      await expect(panel.getByRole('button', {name: '確認此版輸入', exact: true})).toBeDisabled();
      const child = (await (await request.get(`/api/tasks/${taskId}/runs`)).json()).runs[0];
      expect(child.parent_run_id).toBe(first.run_id);
      expect(child.input_summary.source_fields).toContainEqual({name: 'created_date', type: 'DATE'});
      expect(child.input_summary.csv_input_contract_v1.extra_columns).toBe('REJECT');
      await expect(panel.getByRole('region', {name: 'CSV 輸入契約摘要'})).toContainText('額外欄位：拒收');
      await panel.getByRole('button', {name: '查看 SA 證據清單', exact: true}).click();
      const evidence = panel.getByRole('region', {name: 'SA 需求證據', exact: true});
      await expect(evidence.getByText(/此證據檢視不會呼叫模型/)).toBeVisible();
      await expect(panel.getByRole('region', {name: 'SA 呼叫狀態'})).toContainText('此版本尚無 SA 派發紀錄');
      await panel.getByRole('button', {name: '重新載入 SA 狀態'}).click();
      await expect(evidence.getByText('來源欄位 · source.0.field.1', {exact: true})).toBeVisible();
      const context = await (await request.get(`/api/tasks/${taskId}/runs/${child.run_id}/sa-context`)).json();
      expect(context.execution_authorized).toBe(false);
      expect(context.context.input_checksum).toBe(child.input_checksum);
      expect(JSON.stringify(context)).not.toContain('synthetic-no-connection');
      const old = await (await request.get(`/api/tasks/${taskId}/runs/${first.run_id}`)).json();
      expect(old.outcome_code).toBe('SUPERSEDED_BY_REVISION');
      expect(old.approval.decision).toBe('APPROVE');
      expect(old.input_summary.target_table).toBe('synthetic');
      expect(old.input_summary.source_fields).toHaveLength(1);
      expect((await (await request.get(`/api/tasks/${taskId}/runs/${child.run_id}`)).json()).approval).toBeNull();
      await panel.getByRole('button', {name: first.run_id, exact: true}).click();
      await expect(panel.getByText(/此版本已由補正版本取代/)).toBeVisible();
      await expect(panel.getByRole('region', {name: 'SA 需求證據'}).getByText('來源欄位 · source.0.field.1', {exact: true})).toHaveCount(0);
      await panel.locator('.run-version-list > button').first().click();
      await panel.getByLabel('我已核對本次需求及設定版本').check();
      await panel.getByRole('button', {name: '確認此版輸入', exact: true}).click();
      await expect.poll(async () => (await (await request.get(`/api/tasks/${taskId}/runs/${child.run_id}`)).json()).outcome_code, {timeout: 20000}).toBe('PIPELINE_NOT_READY');
      await panel.getByRole('button', {name: '重新載入版本'}).click();
      await panel.getByRole('button', {name: '重新載入 SA 狀態'}).click();
      if (process.env.WORKBENCH_TEST_SA_QUEUE_ONLY === '1') {
        // Dedicated run: API authorization enabled, SA worker intentionally stopped.
        // This verifies UI -> API -> PostgreSQL outbox, not a real provider response.
        const sa = panel.getByRole('region', {name: 'SA 呼叫狀態'});
        const enqueue = sa.getByRole('button', {name: '授權並排入 SA 工作'});
        await expect(enqueue).toBeDisabled();
        await sa.getByRole('checkbox', {name: '我同意此版本的 SA 模型呼叫及上述用量限制'}).check();
        const response = page.waitForResponse(r => r.url().endsWith('/sa-authorization') && r.request().method() === 'POST');
        await enqueue.click();
        expect((await response).status()).toBe(202);
        await expect(sa).toContainText('已授權並排隊，尚未由 Worker 領取');
        await sa.getByRole('button', {name: '重新載入 SA 狀態'}).click();
        await expect(sa).toContainText('已授權並排隊，尚未由 Worker 領取');
        await sa.getByRole('button', {name: '取消尚未領取的 SA 工作'}).click();
        await expect(sa).toContainText('已取消排隊，未呼叫模型');
        await expect(enqueue).toHaveCount(0);
      }
    }
    expect((await request.put('/api/settings/ai-profiles/'+profileId, {data: {...profile, region: 'us-west-2'}})).status()).toBe(200);
    await panel.getByRole('button', {name: '重新載入版本'}).click();
    await expect(panel.getByText(/內容已變更，舊版確認不可沿用/)).toBeVisible();
    await panel.getByRole('button', {name: '取消未執行版本'}).click();
    await expect(panel.getByRole('status')).toContainText('歷史紀錄仍保留');
    await panel.getByRole('button', {name: '建立準備版本', exact: true}).click();
    await expect(panel.getByRole('status')).toContainText('沒有啟動 ETL');
    await panel.getByRole('button', {name: '拒絕此版輸入', exact: true}).click();
    await expect(panel.getByRole('status')).toContainText('準備版本已取消');
    await page.reload();
    await expect(panel.locator('.run-version-list > button')).toHaveCount(process.env.WORKBENCH_TEST_CONTROL_WORKER === '1' ? 3 : 2);
    await expect(page.getByRole('heading', {name: '建立 Task 的完整設定'})).toBeVisible();
  } finally {
    if (taskId) {
      const runs = (await (await request.get(`/api/tasks/${taskId}/runs`)).json()).runs || [];
      for (const run of runs) {
        if (['QUEUED','NEEDS_REVIEW'].includes(run.state) && !run.write_started)
          expect((await request.post(`/api/tasks/${taskId}/runs/${run.run_id}/cancel`)).status()).toBe(200);
      }
    }
    expect((await request.put('/api/settings/groups/data_connections_targets', {data: original})).status()).toBe(200);
  }
});
