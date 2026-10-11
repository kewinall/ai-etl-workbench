import {test,expect} from '@playwright/test';

for(const outcome of ['saved','failed','other-draft'])test(`AI Profile 離開保護：${outcome}（合成 API）`,async({page})=>{
  let profiles=['unload-a','unload-b'].map(profile_id=>({profile_id,display_name:profile_id,provider_type:'LOCAL_COPILOT',region:null,endpoint:null,enabled:true,updated_at:'2026-10-11T00:00:00Z',model_routes:{qa_review:'synthetic',requirement_gate:'synthetic'}}));
  await page.route('**/api/settings/ai-profiles',route=>route.fulfill({json:profiles}));
  let release!:()=>void;
  const pending=new Promise<void>(resolve=>release=resolve);
  let puts=0;
  await page.route('**/api/settings/ai-profiles/unload-a',async route=>{
    expect(route.request().method()).toBe('PUT');puts++;
    expect(route.request().headers()['x-settings-version']).toBe(profiles[0].updated_at);
    await pending;
    if(outcome==='failed'){await route.fulfill({status:409,json:{detail:'synthetic conflict'}});return}
    profiles=profiles.map(p=>p.profile_id==='unload-a'?{...p,...route.request().postDataJSON(),updated_at:'2026-10-11T00:00:01Z'}:p);
    await route.fulfill({json:profiles[0]});
  });
  await page.goto('/#/system');
  const a=page.getByRole('region',{name:'AI Profile unload-a',exact:true});
  await a.getByLabel('AWS Region',{exact:true}).fill('new-region');
  if(outcome==='other-draft')await page.getByRole('region',{name:'AI Profile unload-b',exact:true}).getByLabel('AWS Region',{exact:true}).fill('keep-other');
  const blocked=()=>page.evaluate(()=>{const event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);return event.defaultPrevented});
  expect(await blocked()).toBe(true);
  await page.evaluate(()=>{
    (window as any).unloadAtStatus=null;
    const observer=new MutationObserver(()=>{
      const status=[...document.querySelectorAll('[role="status"]')].some(el=>el.textContent?.includes('AI Profile 已儲存；')||el.textContent?.includes('儲存失敗：'));
      if(!status)return;
      const event=new Event('beforeunload',{cancelable:true});window.dispatchEvent(event);
      (window as any).unloadAtStatus=event.defaultPrevented;observer.disconnect();
    });observer.observe(document.body,{subtree:true,childList:true,characterData:true});
  });
  await a.getByRole('button',{name:'儲存 AI Profile'}).click();
  await expect(a.getByLabel('AWS Region',{exact:true})).toBeDisabled();
  expect(await blocked()).toBe(true);
  release();
  await expect.poll(()=>page.evaluate(()=>(window as any).unloadAtStatus)).toBe(outcome!=='saved');
  expect(await blocked()).toBe(outcome!=='saved');
  await expect(a.getByLabel('AWS Region',{exact:true})).toHaveValue('new-region');
  expect(puts).toBe(1);
});
