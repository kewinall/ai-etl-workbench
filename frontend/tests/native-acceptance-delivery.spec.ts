import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const proofPath=path.resolve(process.env.WORKBENCH_NATIVE_ACCEPTANCE_PROOF||'../docs/verification/ui-accept-auto-delivery-2026-10-10.json');
const enabled=process.env.WORKBENCH_NATIVE_ACCEPTANCE==='1';
const proof=enabled?JSON.parse(fs.readFileSync(proofPath,'utf8')):{cases:[]};
for(const c of proof.cases)for(const width of [390,768,1440])test(`${c.key} ${width}px 真實正式交付七階段、鍵盤與下載`,async({page,request})=>{
  test.setTimeout(60000);
  const base='/api/tasks/'+c.task_id+'/runs/'+c.run_id;
  const before=await(await request.get(base)).json();
  const releaseBefore=await(await request.get(base+'/release')).json();
  expect(releaseBefore.release.release_id).toBe(c.release.release_id);
  const writes:string[]=[],errors:string[]=[];
  await page.route('**/api/**',route=>['GET','HEAD','OPTIONS'].includes(route.request().method())?route.continue():route.abort());
  page.on('request',r=>{if(r.url().includes('/api/')&&r.method()!=='GET')writes.push(r.method())});
  page.on('pageerror',e=>errors.push(e.message));
  await page.setViewportSize({width,height:1000});
  const url=`/#/projects/346e9419-4b0e-4ba7-ad29-1756ca7da833/tasks/${c.task_id}`;
  for(const stage of ['requirements','review','design','confirm','results','quality','delivery']){
    await page.goto(`${url}/${stage}/${c.run_id}`);
    await expect(page.locator('.workflow-status-line')).toContainText('已正式交付');
    await expect(page.getByRole('combobox',{name:'共用 Run 版本'})).toHaveValue(c.run_id);
    await expect.poll(()=>page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1)).toBe(true);
    await page.keyboard.press('Tab');
    expect(await page.evaluate(()=>document.activeElement?.tagName)).not.toBe('BODY');
  }
  const formal=page.getByRole('region',{name:'正式交付成果',exact:true});
  const download=formal.getByRole('link',{name:'下載正式 Release ZIP',exact:true});
  await expect(download).toBeVisible();
  await download.focus();
  const pending=page.waitForEvent('download');await page.keyboard.press('Enter');
  const saved=await pending;const file=await saved.path();expect(file).toBeTruthy();
  const bytes=fs.readFileSync(file!);expect(bytes.length).toBe(c.release.file_size);
  expect(crypto.createHash('sha256').update(bytes).digest('hex')).toBe(c.release.checksum);
  // A refresh must preserve the selected immutable release Run and visible SDM list.
  await page.reload();await expect(page.getByRole('combobox',{name:'共用 Run 版本'})).toHaveValue(c.run_id);
  await page.getByText('候選文件、可攜驗證與交付歷史',{exact:true}).click();
  await expect(page.getByRole('button',{name:'下載歷史候選 Excel（非 Release）',exact:true}).first()).toBeVisible();
  expect(await(await request.get(base)).json()).toEqual(before);
  expect(await(await request.get(base+'/release')).json()).toEqual(releaseBefore);
  expect(before.events.filter((e:any)=>e.event_type==='WRITE_STARTED')).toHaveLength(1);
  expect(writes).toEqual([]);expect(errors).toEqual([]);
});
test('native acceptance proof opt-in',()=>test.skip(!enabled,'Requires three saved formal real-case releases; no synthetic substitute.'));
