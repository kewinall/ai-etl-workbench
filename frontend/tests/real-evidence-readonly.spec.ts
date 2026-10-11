import {test,expect} from '@playwright/test';
import {createHash} from 'node:crypto';

const cases=[
 {name:'CSV',project:'8d423121-2125-422c-830f-2d882e973b4b',task:'TASK-20260917-0007',run:'d8abcc97-e5d7-4f83-9d47-b244e03730e7',release:'a76bae7f-3b13-4dda-ac3f-68f8b41081de',bytes:10452,sha:'f32b964c8071d37dd854f653320eb4ce41041ae01e92220a026aa27d9bb8da2d'},
 {name:'Excel',project:'7974a406-4f6b-4fa7-801b-7204dbf3b4d7',task:'TASK-20260928-0001',run:'df438c72-a408-4eef-8a6e-10f2a8445b02',release:'de606bda-412a-4ffd-8d28-2a6e8dc0cbf4',bytes:11208,sha:'603b9e974338cfe9cd25b13d1a7ef680b7b12bd96ff2ba63992ddcb46eef1c2a'}
];
for(const item of cases)test(`既有真實 ${item.name} 七階段只讀，原 ZIP 指紋不變`,async({page,request})=>{
 test.skip(process.env.WORKBENCH_EVIDENCE_TEST!=='1','Explicit fixed original GET-only regression required');
 const base=`/api/evidence/pilot/tasks/${item.task}/runs/${item.run}`;
 const before=await (await request.get(base)).json();
 const workflow=await(await request.get(base+'/workflow-status')).json();
 expect(workflow.read_only_source).toBe(true);expect(workflow.matches_current).toBe(false);
 expect(workflow.stages.every((stage:any)=>stage.can_operate===false)).toBe(true);
 expect(Object.values(workflow.operation_qualifications).filter((op:any)=>op.type!=='DOWNLOAD').every((op:any)=>op.enabled===false&&!!op.blocked_reason)).toBe(true);
 expect(workflow.operation_qualifications.release_download.enabled).toBe(true);
 const beforeWrites=before.events.filter((e:any)=>e.event_type==='WRITE_STARTED').length;
 let writes=0;
 await page.route('**/api/**',async route=>{if(route.request().method()!=='GET'){writes++;return route.abort()}return route.continue()});
 await page.goto(`/?evidence=pilot#/projects/${item.project}/tasks/${item.task}/delivery/${item.run}`);
 await expect(page.getByText('既有真實案例，來源只讀',{exact:false})).toBeVisible();
 await expect(page.getByRole('link',{name:'下載正式 Release ZIP'})).toHaveAttribute('href',`${base}/release/${item.release}/download`);
 for(const key of ['requirements','review','design','confirm','results','quality','delivery']){
  await page.getByRole('tab',{name:new RegExp(({requirements:'需求與資料規格',review:'需求審查',design:'流程設計審查',confirm:'執行確認',results:'執行與結果',quality:'品質審查',delivery:'成果交付'} as any)[key])}).click();
  await expect(page.getByLabel('共用 Run 版本')).toHaveValue(item.run);
  await expect(page).toHaveURL(new RegExp('evidence=pilot.*'+key+'/'+item.run));
  await expect(page.locator('input[type="checkbox"]:visible:enabled')).toHaveCount(0);
 }
 const zip=await request.get(`${base}/release/${item.release}/download`);expect(zip.ok()).toBeTruthy();
 const bytes=await zip.body();expect(bytes.length).toBe(item.bytes);expect(createHash('sha256').update(bytes).digest('hex')).toBe(item.sha);
 const after=await (await request.get(base)).json();
 expect(after).toEqual(before);
 expect(after.updated_at).toBe(before.updated_at);
 expect(after.events.filter((e:any)=>e.event_type==='WRITE_STARTED').length).toBe(beforeWrites);
 expect(writes).toBe(0);
 expect((await request.post(`${base}/hop-dispatch`,{data:{confirmed:true}})).status()).toBe(405);
});
