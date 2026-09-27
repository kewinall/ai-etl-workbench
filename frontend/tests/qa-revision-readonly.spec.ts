import {test,expect} from '@playwright/test';

test('真實 QA 待複核版本可開啟補正表單但不提交、不重跑',async({page,request})=>{
  const task=process.env.WORKBENCH_QA_REVISION_TASK,run=process.env.WORKBENCH_QA_REVISION_RUN;
  test.skip(!task||!run,'Requires real persisted QA NEEDS_REVIEW execution');
  const base=`/api/tasks/${task}/runs/${run}`;
  const response=await request.get(base);expect(response.ok()).toBe(true);
  const before=await response.json();
  expect(before.qa_revision?.checksum).toMatch(/^[a-f0-9]{64}$/);
  expect(before.outcome_code).toBe('HOP_EXECUTED_QA_REQUIRED');
  const errors:string[]=[],mutations:string[]=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(!['GET','HEAD','OPTIONS'].includes(r.method()))mutations.push(r.url())});
  const taskResponse=await (await request.get(`/api/tasks/${task}`)).json();
  await page.goto(`/#/projects/${taskResponse.project_id}/tasks/${task}/requirements`);
  await page.getByRole('button').filter({hasText:run!}).click();
  await expect(page.getByText('QA 尚未通過。保存補正會結束此版本的待審流程', {exact:false})).toBeVisible();
  await page.getByRole('button',{name:'補正需求並建立新版',exact:true}).click();
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:1000});
    await expect(page.getByRole('form',{name:'需求補正'})).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  }
  const after=await (await request.get(base)).json();
  expect(after.events).toEqual(before.events);
  expect(after.qa_revision).toEqual(before.qa_revision);
  expect(mutations).toEqual([]);expect(errors).toEqual([]);
});
