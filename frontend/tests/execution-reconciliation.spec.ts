import {test,expect} from '@playwright/test';
import {createHash} from 'node:crypto';

test('人工核對表單：明確確認、檔案只取指紋、重載與衝突（合成 API）',async({page,request})=>{
 const task=process.env.WORKBENCH_BOUND_RESULT_TASK,run=process.env.WORKBENCH_BOUND_RESULT_RUN,project=process.env.WORKBENCH_BOUND_RESULT_PROJECT;
 test.skip(!task||!run||!project,'Requires existing navigation');
 const base=`/api/tasks/${task}/runs/${run}`;
 const original=await (await request.get(base)).json();
 let closed=false,conflict=false,posts=0;
 const bytes=Buffer.from('Synthetic inspection evidence; no database query performed');
 const hash=createHash('sha256').update(bytes).digest('hex');
 await page.route(`**${base}`,r=>r.fulfill({json:{...original,state:'NEEDS_REVIEW',outcome_code:'HOP_RESULT_UNKNOWN'}}));
 await page.route(`**${base}/reconciliation`,async r=>{
   if(r.request().method()==='POST'){
     posts++;
     expect(r.request().postDataJSON()).toEqual({binding_checksum:'a'.repeat(64),evidence_sha256:hash,observed_row_count:1,engine_stopped:true,target_checked:true,confirmed:true});
     if(conflict)return r.fulfill({status:409,json:{detail:{message:'版本已變更'}}});
     closed=true;
   }
   return r.fulfill({json:closed?{status:'CLOSED_WITHOUT_RETRY',observed_row_count:1,evidence_sha256:hash,created_at:'2026-09-17T00:00:00Z',original_outcome:'HOP_RESULT_UNKNOWN'}:{status:'AWAITING_RECONCILIATION',binding:{checksum:'a'.repeat(64)}}});
 });
 await page.goto(`/#/projects/${project}/tasks/${task}/requirements`);
 const panel=page.getByRole('region',{name:'執行結果人工核對',exact:true});
 const save=panel.getByRole('button',{name:'保存人工核對並結案（不重跑）'});
 await expect(save).toBeDisabled();
 const fill=async()=>{
   await panel.getByLabel('我已確認本次 Hop 程序停止').check();
   await panel.getByLabel('我已核對本次目標與寫入範圍，並保留查詢證據').check();
   await panel.getByLabel('核對時目標筆數').fill('1');
   await panel.getByLabel('選擇核對證據檔案').setInputFiles({name:'inspection.txt',mimeType:'text/plain',buffer:bytes});
   await expect(save).toBeDisabled();
   await panel.getByLabel('我確認只結束此次失敗／未知版本，不重跑，也不宣告成功').check();
   await expect(save).toBeEnabled();
 };
 await fill();await save.click();
 await expect(panel.getByRole('status')).toContainText('已人工結案，未重跑');
 await page.reload();await expect(panel.getByRole('status')).toContainText('已人工結案');
 expect(posts).toBe(1);
 closed=false;conflict=true;await page.reload();await fill();await save.click();
 await expect(panel.getByRole('alert')).toContainText('版本已變更');
 await expect(save).toHaveCount(0);
 closed=false;conflict=false;await page.reload();
 await page.setViewportSize({width:390,height:900});
 await expect(panel).toBeVisible();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
});
