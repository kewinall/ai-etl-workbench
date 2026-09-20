import {test, expect} from '@playwright/test';

test('來源證據失敗分支（合成 API 回應，只驗證 UI）', async ({page, request}) => {
  const project = await (await request.post('/api/projects',{data:{project_name:`來源失敗UI-${Date.now()}`}})).json();
  const task = await (await request.post(`/api/projects/${project.project_id}/tasks`,{data:{name:'來源失敗顯示',requirement:'合成 UI 分支驗證，不執行模型或 ETL',source_config:{sources:[{type:'CSV',has_actual_data:false,fields:[{name:'id',type:'BIGINT'}]}]},target_schema:'ai_sample',target_table:'ui_only'}})).json();
  const runId = '00000000-0000-4000-8000-000000000001';
  const run:any = {run_id:runId,state:'CANCELLED',created_at:'2026-09-13T00:00:00Z',input_summary:{},settings_summary:{},events:[],matches_current:false,gate_result:{status:'NEEDS_INPUT',issues:[],source_evidence:[]}};
  const base = `**/api/tasks/${task.id}/runs`;
  await page.route(base, route=>route.fulfill({json:{runs:[run]}}));
  await page.route(`${base}/${runId}`, route=>route.fulfill({json:run}));
  const errors:string[]=[];
  page.on('pageerror', error=>errors.push(error.message));
  await page.goto(`/#/projects/${project.project_id}/tasks/${task.id}/requirements`);
  const evidence = page.getByRole('region',{name:'來源檔案驗證證據'});
  await expect(evidence).toContainText('沒有實體來源檔案檢查證據');
  run.outcome_code = 'HOP_RESULT_UNKNOWN';
  run.write_started = true;
  run.state = 'NEEDS_REVIEW';
  await page.getByRole('button',{name:'重新載入版本'}).click();
  await expect(page.getByRole('alert',{name:'執行結果待核對'})).toContainText('禁止直接重跑');
  await expect(page.getByRole('button',{name:'補正需求並建立新版',exact:true})).toHaveCount(0);
  for(const [code,text] of [
    ['HOP_PREPARATION_INVALID','尚未啟動 Hop'],
    ['HOP_EXECUTED_QA_REQUIRED','不代表可交付'],
    ['HOP_EXECUTION_FAILED','失敗不代表所有寫入已回復'],
    ['HOP_RESULT_UNKNOWN','執行器異常或回報無法驗證'],
  ]) {
    run.outcome_code=code;
    await page.getByRole('button',{name:'重新載入版本'}).click();
    await expect(page.getByRole('alert',{name:'執行結果待核對'})).toContainText(text);
  }
  for(const [status,message] of [
    ['UPLOAD_UNAVAILABLE','找不到檔案或無法讀取'],
    ['UPLOAD_CONTENT_CHANGED','不能沿用原確認'],
    ['UPLOAD_BINDING_INVALID','檔案版本資訊不完整'],
    ['UPLOAD_PATH_INVALID','不是允許的受控檔案'],
    ['UNKNOWN_STATUS','不可視為通過'],
  ]){
    run.gate_result.source_evidence=[{source_ref:'source.0',status}];
    await page.getByRole('button',{name:'重新載入版本'}).click();
    await expect(evidence).toContainText(message);
    await expect(evidence).not.toContainText('符合此版本的大小與 checksum');
  }
  run.gate_result.source_evidence=[{source_ref:'source.0',status:'CSV_CONTENT_INVALID',csv:{status:'INVALID',complete:false,records_checked:4,issues:[{code:'CSV_HEADER_MISMATCH',record:0},{code:'CSV_MISSING_COLUMNS',record:4}]}}];
  await page.getByRole('button',{name:'重新載入版本'}).click();
  await expect(evidence).toContainText('未通過或尚未完整掃描');
  await expect(evidence).toContainText('標題名稱或順序與確認欄位不同（標題列）');
  await expect(evidence).toContainText('資料記錄 4，非文字行號');
  await expect(evidence).not.toContainText('檢查通過（');
  await page.setViewportSize({width:390,height:1000});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await evidence.screenshot({path:test.info().outputPath('source-failures.png')});
  expect(errors).toEqual([]);
});
