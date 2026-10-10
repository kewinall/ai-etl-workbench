import {test,expect} from '@playwright/test';

for(const exists of [false,true]) test(`準備失聯核對：目標${exists?'存在':'不存在'}、一次確認與重載（合成 API）`,async({page,request})=>{
 const task=process.env.WORKBENCH_BOUND_RESULT_TASK,run=process.env.WORKBENCH_BOUND_RESULT_RUN,project=process.env.WORKBENCH_BOUND_RESULT_PROJECT;
 test.skip(!task||!run||!project,'Requires readonly navigation reference');
 const origin='http://127.0.0.1:5183';
 // Only GET reference data; every mutation below is fulfilled in-browser.
 await page.route('**/api/**',async route=>{
   expect(route.request().method()).toBe('GET');
   const path=new URL(route.request().url());
   const response=await request.get(origin+path.pathname+path.search);
   await route.fulfill({response});
 });
 const base=`/api/tasks/${task}/runs/${run}`;
 let closed=false,posts=0;
 await page.route(`**${base}/hop-dispatch`,r=>r.fulfill({json:{request:{status:closed?'NEEDS_REVIEW':'CLAIMED',overdue:true},offer:null}}));
 await page.route(`**${base}/hop-preparation-reconciliation`,async route=>{
   if(route.request().method()==='POST'){
     posts++;
     expect(route.request().postDataJSON()).toEqual({binding_checksum:'a'.repeat(64),
       target_exists:exists,observed_row_count:exists?0:null,engine_stopped:true,target_checked:true,confirmed:true});
     closed=true;
   }
   await route.fulfill({json:closed?{status:'CLOSED_WITHOUT_RETRY',target_exists:exists,observed_row_count:exists?0:null,evidence_sha256:null}:
     {status:'AWAITING_RECONCILIATION',binding:{checksum:'a'.repeat(64)}}});
 });
 await page.goto(`/#/projects/${project}/tasks/${task}/requirements`);
 const panel=page.getByRole('region',{name:'Hop 準備失聯人工核對',exact:true});
 const save=panel.getByRole('button',{name:'確認結案，保留結果'});
 await expect(save).toBeDisabled();
 await panel.getByLabel('目標表是否存在').selectOption(exists?'yes':'no');
 if(exists){await expect(save).toBeDisabled();await panel.getByLabel('核對時目標筆數').fill('0')}
 else await expect(panel.getByLabel('核對時目標筆數')).toHaveCount(0);
 await expect(save).toBeDisabled();
 await panel.getByLabel('我已確認本次執行與 Worker停止，目標核對結果正確，同意結案並保留原結果').check();
 await expect(save).toBeEnabled();
 await page.setViewportSize({width:390,height:900});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await save.click();await expect(panel.getByRole('status')).toContainText('已人工結案');
 await page.reload();await expect(panel.getByRole('status')).toContainText('已人工結案');
 await expect(panel).toContainText(exists?'核對時目標筆數：0':'目標不存在（不是零筆）');
 expect(posts).toBe(1);
 await page.unrouteAll({behavior:'wait'});
});
