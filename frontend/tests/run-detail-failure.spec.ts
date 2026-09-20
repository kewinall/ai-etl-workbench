import {test, expect} from '@playwright/test';

test('版本讀取失敗或識別不符不可留下舊核准內容（合成回應）', async ({page, request}) => {
  const project = await (await request.post('/api/projects', {data:{project_name:'版本讀取-'+Date.now()}})).json();
  const created = await request.post(`/api/projects/${project.project_id}/tasks`, {data:{name:'版本讀取',requirement:'只測版本畫面',source_config:{sources:[{type:'CSV',has_actual_data:false,fields:[{name:'id',type:'BIGINT'}]}]},target_schema:'ai_sample',target_table:'ui_only'}});
  expect(created.status()).toBe(201);
  const task = await created.json();
  const base = `**/api/tasks/${task.id}/runs`;
  const first = {run_id:'00000000-0000-4000-8000-000000000001',state:'QUEUED',created_at:'2026-09-13T00:00:00Z',input_summary:{requirement_text:'第一版本'},settings_summary:{},events:[],matches_current:true};
  const second = {...first,run_id:'00000000-0000-4000-8000-000000000002'};
  await page.route(base, r=>r.fulfill({json:{runs:[first,second]}}));
  await page.route(`${base}/${first.run_id}`, r=>r.fulfill({json:first}));
  let mode = 'failure';
  await page.route(`${base}/${second.run_id}`, r=>mode==='failure' ? r.fulfill({status:503,json:{detail:{message:'合成版本讀取失敗'}}}) : r.fulfill({json:first}));
  await page.goto(`/#/projects/${project.project_id}/tasks/${task.id}/requirements`);
  const panel = page.getByRole('region',{name:'執行準備版本',exact:true});
  await panel.getByLabel('我已核對本次需求及設定版本').check();
  await expect(panel.getByRole('button',{name:'確認此版輸入',exact:true})).toBeEnabled();
  await panel.getByRole('button').filter({hasText:second.run_id}).click();
  await expect(panel.getByRole('status')).toContainText('合成版本讀取失敗');
  await expect(panel.getByRole('button',{name:'確認此版輸入',exact:true})).toHaveCount(0);
  mode = 'mismatch';
  await panel.getByRole('button').filter({hasText:second.run_id}).click();
  await expect(panel.getByRole('status')).toContainText('版本回應不一致');
  await expect(panel.getByRole('region',{name:'版本內容'})).toHaveCount(0);
  await panel.getByRole('button').filter({hasText:first.run_id}).click();
  await expect(panel.getByRole('button',{name:'確認此版輸入',exact:true})).toBeDisabled();
  await expect(panel.getByLabel('我已核對本次需求及設定版本')).not.toBeChecked();
});
