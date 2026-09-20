import {test,expect} from '@playwright/test';

test('標準答案歷史：錯誤重讀、版本切換與窄版面（合成 UI，不是 QA 驗收）',async({page,request})=>{
  const project=await(await request.post('/api/projects',{data:{project_name:'答案查閱-'+Date.now()}})).json();
  const response=await request.post(`/api/projects/${project.project_id}/tasks`,{data:{name:'答案查閱 UI',requirement:'合成 UI 測試，不執行 ETL',source_config:{sources:[{type:'CSV',alias:'synthetic',has_actual_data:false,fields:[{name:'id',type:'BIGINT'}]}]},target_schema:'ai_sample',target_table:'ui_only'}});
  expect(response.status()).toBe(201);const task=await response.json();
  await page.route(`**/api/tasks/${task.id}/runs`,r=>r.fulfill({json:{runs:[{run_id:'run-ui',state:'NEEDS_REVIEW'}]}}));
  await page.route(`**/api/tasks/${task.id}/runs/run-ui/specifications`,r=>r.fulfill({json:{items:[{specification_id:'spec-new',version:2},{specification_id:'spec-old',version:1}]}}));
  let fail=true;
  let comparisonFail=false;
  await page.route(`**/api/tasks/${task.id}/runs/run-ui/comparisons`,route=>comparisonFail
    ?route.fulfill({status:503,json:{detail:'合成證據讀取失敗'}})
    :route.fulfill({json:{items:['MATCH','MISMATCH'].map((status,i)=>({comparison_id:`comparison-${i}`,checksum:'a'.repeat(64),created_at:'2026-09-13T00:00:00Z',evidence:{status,expected_count:2,actual_count:2,missing_count:i,unexpected_count:i,oracle_id:'oracle-ui',oracle_document_checksum:'b'.repeat(64),execution_binding_checksum:'c'.repeat(64),hop_event_id:1,hop_log_checksum:'d'.repeat(64),actual_provenance:'NOT_VERIFIED',qa_passed:false,release_ready:false}}))}}));
  await page.route('**/specifications/spec-new/oracles',r=>fail?r.fulfill({status:503,json:{detail:'合成讀取失敗'}}):r.fulfill({json:{items:[]}}));
  await page.route('**/specifications/spec-old/oracles',r=>r.fulfill({json:{items:[{oracle_id:'oracle-ui',version:1,approval_recorded:true,created_at:'2026-09-13T00:00:00Z',approved_at:'2026-09-13T00:01:00Z',document_checksum:'a'.repeat(64)}]}}));
  await page.goto(`/#/projects/${project.project_id}/tasks/${task.id}/execution`);
  const panel=page.getByRole('region',{name:'標準答案版本紀錄'});
  await expect(panel.getByRole('alert')).toBeVisible();
  await expect(panel.getByText('此規格尚未保存標準答案。')).toHaveCount(0);
  fail=false;await panel.getByRole('button',{name:'重新讀取標準答案'}).click();
  await expect(panel.getByText('此規格尚未保存標準答案。')).toBeVisible();
  await panel.getByLabel('標準答案規格版本').selectOption('spec-old');
  await expect(panel.getByText('曾人工核准；目前資格尚未評估')).toBeVisible();
  await panel.getByText('版本指紋').click();
  await page.setViewportSize({width:390,height:1000});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
  await panel.getByLabel('標準答案規格版本').selectOption('spec-new');
  await expect(panel.getByText('此規格尚未保存標準答案。')).toBeVisible();
  await expect(panel.getByText('曾人工核准；目前資格尚未評估')).toHaveCount(0);
  const comparisons=page.getByRole('region',{name:'結果比對證據'});
  await expect(comparisons.getByRole('heading',{name:'比對一致（非正式 QA）'})).toBeVisible();
  await expect(comparisons.getByRole('heading',{name:'發現結果差異'})).toBeVisible();
  await expect(comparisons).toContainText('比對一致不等於 QA 通過');
  await comparisons.getByText('追溯版本與指紋',{exact:true}).first().click();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2)).toBe(true);
  comparisonFail=true;
  await comparisons.getByRole('button',{name:'重新讀取比對證據'}).click();
  await expect(comparisons.getByRole('alert')).toBeVisible();
  await expect(comparisons.getByRole('heading',{name:'比對一致（非正式 QA）'})).toHaveCount(0);
  comparisonFail=false;
  await comparisons.getByRole('button',{name:'重新讀取比對證據'}).click();
  await expect(comparisons.getByRole('heading',{name:'發現結果差異'})).toBeVisible();
});
