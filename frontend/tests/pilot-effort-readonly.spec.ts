import {test,expect} from '@playwright/test';

test('計時檢視：空值、逾時、案例錯配與讀取失敗不可假裝零工時',async({page,request})=>{
  const project=process.env.WORKBENCH_MEASUREMENT_PROJECT;
  test.skip(!project,'Requires explicit existing project for read-only navigation');
  const backend='http://127.0.0.1:5183';
  const response=await request.get(`${backend}/api/projects/${project}/pilot-cohorts`);
  expect(response.ok()).toBe(true);
  const inventory=await response.json(),cohort=inventory.cohorts[0],item=cohort.cases[0];
  let mode='empty';const mutations:string[]=[];
  const path=`/api/projects/${project}/pilot-cohorts/${cohort.cohort_id}/cases/${item.case_key}/effort`;
  await page.route('**/api/**',async route=>{
    const url=new URL(route.request().url());
    if(route.request().method()!=='GET'){mutations.push(url.pathname);return route.fulfill({status:409,json:{detail:'Test write blocked'}})}
    if(url.pathname===path){
      if(mode==='error')return route.fulfill({status:503,json:{detail:'計時證據暫時無法讀取；不代表零工時'}});
      return route.fulfill({json:{project_id:mode==='wrong'?'wrong-project':project,cohort_id:cohort.cohort_id,case_key:item.case_key,
        comparison_ready:false,human_recording_enabled:false,events:[],other_case_open:false,
        recovery:mode==='expired'?{status:'EXPIRED_REQUIRES_ABANDON'}:null,
        summary:{totals:{WORKBENCH:{recorded_human_seconds:null},MANUAL_BASELINE:{recorded_human_seconds:null}},
          excluded_nonhuman_sessions:0,abandoned_sessions:0}}});
    }
    return route.fulfill({response:await route.fetch({url:backend+url.pathname+url.search})});
  });
  await page.goto(`/#/projects/${project}/evaluation`);
  await page.locator('summary').filter({hasText:`${item.ordinal}. ${item.definition.title}`}).click();
  const region=page.getByRole('region',{name:`案例 ${item.case_key} 操作時間`,exact:true});
  const load=region.getByRole('button',{name:'查看／重新讀取計時紀錄',exact:true});
  await load.click();await expect(region).toContainText('尚無計時事件；不代表零工時。');
  await expect(region).toContainText('工作台真人操作：尚未量測');
  mode='expired';await load.click();await expect(region).toContainText('未結束區間已逾時，必須明確放棄');
  for(const width of [390,768,1440]){
    await page.setViewportSize({width,height:1000});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  }
  mode='wrong';await load.click();await expect(region.getByRole('alert')).toContainText('案例不符');
  await expect(region).not.toContainText('尚無計時事件');
  mode='error';await load.click();await expect(region.getByRole('alert')).toContainText('暫時無法讀取');
  mode='empty';await load.click();await expect(region).toContainText('尚無計時事件');
  expect(mutations).toEqual([]);
});
