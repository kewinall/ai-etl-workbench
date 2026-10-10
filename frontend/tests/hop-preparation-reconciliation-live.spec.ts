import {test,expect} from '@playwright/test';

test('專用程序死亡 DB：網站結案與持久化，不重派（無 Vertica）',async({page,request,baseURL})=>{
 test.skip(process.env.WORKBENCH_CLAIM_REVIEW_TEST!=='dedicated-disposable-database','Explicit retained synthetic DB required');
 expect(baseURL).toBe('http://127.0.0.1:5196');
 expect((await (await request.get('/api/ready')).json()).execution_enabled).toBe(false);
 const tasks=await (await request.get('/api/tasks')).json();expect(tasks).toHaveLength(1);
 const task=tasks[0];expect(task.id).toMatch(/^queue-test-[a-f0-9]{32}$/);
 const runs=(await (await request.get(`/api/tasks/${task.id}/runs`)).json()).runs;
 expect(runs).toHaveLength(1);const run=runs[0];
 const base=`/api/tasks/${task.id}/runs/${run.run_id}`;
 const dispatch=await (await request.get(base+'/hop-dispatch')).json();
 expect(dispatch.request.status).toBe('CLAIMED');
 const original=await (await request.get(base)).json();
 expect(original.write_started).toBe(false);
 const proof=Buffer.from(JSON.stringify({scope:'SYNTHETIC_CONTROL_ONLY_NO_VERTICA',
   reason:'Dedicated owner-death fixture stopped before target preparation; no engine or external DB was invoked',
   request_id:dispatch.request.request_id,run_id:run.run_id,write_started:false}));
 const mutations:string[]=[];page.on('request',r=>{if(!['GET','HEAD','OPTIONS'].includes(r.method()))mutations.push(new URL(r.url()).pathname)});
 await page.goto(`/#/projects/${task.project_id}/tasks/${task.id}/requirements`);
 const panel=page.getByRole('region',{name:'Hop 準備失聯人工核對',exact:true});
 await panel.getByLabel('目標表是否存在').selectOption('no');
 await panel.getByLabel('我已確認本次執行與 Worker停止，目標核對結果正確，同意結案並保留原結果').check();
 await panel.getByRole('button',{name:'確認結案，保留結果'}).click();
 await expect(panel.getByRole('status')).toContainText('已人工結案');
 await page.reload();await expect(panel.getByRole('status')).toContainText('已人工結案');
 await expect(panel).toContainText('目標不存在（不是零筆）');
 expect(mutations).toEqual([base+'/hop-preparation-reconciliation']);
 const saved=await (await request.get(base+'/hop-preparation-reconciliation')).json();
 expect(saved.evidence_sha256).toBe(hash);expect(saved.observed_row_count).toBeNull();
 expect(saved.automatic_retry_allowed).toBe(false);expect(saved.release_ready).toBe(false);
 const after=await (await request.get(base)).json();expect(after.state).toBe('FAILED');
 expect(after.write_started).toBe(false);
 expect(after.events.filter((e:any)=>e.event_type==='HOP_PREPARATION_RECONCILED_WITHOUT_RETRY')).toHaveLength(1);
 expect((await (await request.get(base+'/hop-dispatch')).json()).request.status).toBe('NEEDS_REVIEW');
});
