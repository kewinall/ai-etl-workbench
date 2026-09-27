import {test,expect} from '@playwright/test';
import {createHash} from 'node:crypto';

for(const exists of [false,true]) test(`準備失聯核對：目標${exists?'存在':'不存在'}、指紋與重載（合成 API）`,async({page,request})=>{
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
 const bytes=Buffer.from('Synthetic evidence; no real target inspection');
 const hash=createHash('sha256').update(bytes).digest('hex');
 await page.route(`**${base}/hop-dispatch`,r=>r.fulfill({json:{request:{status:closed?'NEEDS_REVIEW':'CLAIMED',overdue:true},offer:null}}));
 await page.route(`**${base}/hop-preparation-reconciliation`,async route=>{
   if(route.request().method()==='POST'){
     posts++;
     expect(route.request().postDataJSON()).toEqual({binding_checksum:'a'.repeat(64),evidence_sha256:hash,
       target_exists:exists,observed_row_count:exists?0:null,engine_stopped:true,target_checked:true,confirmed:true});
     closed=true;
   }
   await route.fulfill({json:closed?{status:'CLOSED_WITHOUT_RETRY',target_exists:exists,observed_row_count:exists?0:null,evidence_sha256:hash}:
     {status:'AWAITING_RECONCILIATION',binding:{checksum:'a'.repeat(64)}}});
 });
 await page.goto(`/#/projects/${project}/tasks/${task}/requirements`);
 const panel=page.getByRole('region',{name:'Hop 準備失聯人工核對',exact:true});
 const save=panel.getByRole('button',{name:'保存人工核對並結案（不重跑）'});
 await expect(save).toBeDisabled();
 await panel.getByLabel('查核時目標表是否存在').selectOption(exists?'yes':'no');
 if(exists){await expect(save).toBeDisabled();await panel.getByLabel('核對時目標筆數').fill('0')}
 else await expect(panel.getByLabel('核對時目標筆數')).toHaveCount(0);
 await panel.getByLabel('我已確認本次 Hop 程序停止').check();
 await panel.getByLabel('我已核對本次目標與寫入範圍，並保留查詢證據').check();
 await panel.getByLabel('選擇核對證據檔案').setInputFiles({name:'synthetic.txt',mimeType:'text/plain',buffer:bytes});
 await expect(save).toBeDisabled();
 await panel.getByLabel('我確認只結束此次失敗／未知版本，不重跑，也不宣告成功').check();
 await expect(save).toBeEnabled();
 await page.setViewportSize({width:390,height:900});
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
 await save.click();await expect(panel.getByRole('status')).toContainText('已人工結案');
 await page.reload();await expect(panel.getByRole('status')).toContainText('已人工結案');
 await expect(panel).toContainText(exists?'核對時目標筆數：0':'目標不存在（不是零筆）');
 expect(posts).toBe(1);
 await page.unrouteAll({behavior:'wait'});
});
