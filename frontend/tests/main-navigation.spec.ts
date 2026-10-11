import {test,expect} from '@playwright/test';
// 真實隔離 API：只讀導覽，不建立或修改資料。
test('主導覽：管理群組展開／收合、鍵盤、目前位置與舊網址相容',async({page,request})=>{
 const projects=await(await request.get('/api/projects')).json();test.skip(!projects.length,'需要至少一個專案');
 const id=projects[0].project_id;
 await page.goto(`/#/projects/${id}`);
 const nav=page.getByRole('navigation',{name:'主要導覽'}),toggle=nav.getByRole('button',{name:'管理'}),group=nav.getByRole('group',{name:'管理'});
 await expect(toggle).toHaveAttribute('aria-expanded','false');await expect(group).toBeHidden();
 await toggle.focus();await page.keyboard.press('Enter');
 await expect(toggle).toHaveAttribute('aria-expanded','true');
 await expect(group.getByRole('button')).toHaveText(['專案設定','Pilot 評估','Pilot 成果','平台設定中心']);
 await page.keyboard.press('Tab');await expect(group.getByRole('button',{name:'專案設定'})).toBeFocused();
 await page.keyboard.press('Escape');await expect(group).toBeHidden();await expect(toggle).toBeFocused();
 await toggle.click();await group.getByRole('button',{name:'Pilot 評估'}).click();
 await expect(page).toHaveURL(new RegExp(`/projects/${id}/evaluation$`));
 await expect(group.getByRole('button',{name:'Pilot 評估'})).toHaveAttribute('aria-current','page');
 // Old URLs still open inside the management group.
 for(const [hash,label] of [[`/projects/${id}/settings`,'專案設定'],['/system','平台設定中心'],['/pilot','Pilot 成果'],['/usage','Pilot 成果']]){
  await page.goto('/#'+hash);await expect(nav.getByRole('button',{name:'管理'})).toHaveAttribute('aria-expanded','true');
  await expect(group.getByRole('button',{name:label})).toHaveAttribute('aria-current','page');
 }
 await page.goto('/#/guide');await expect(nav.getByRole('button',{name:'操作指南'})).toHaveAttribute('aria-current','page');
 for(const width of [390,768]){
  await page.setViewportSize({width,height:844});await page.goto(`/#/projects/${id}`);
  await nav.getByRole('button',{name:'管理'}).click();await expect(group).toBeVisible();
  const box=await group.boundingBox();expect(box&&box.x>=0&&box.x+box.width<=width+1).toBe(true);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
  await group.getByRole('button',{name:'平台設定中心'}).click();await expect(page).toHaveURL(/#\/system$/);
 }
});
