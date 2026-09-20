import {test,expect} from '@playwright/test';

test('指南符合 Pilot 限制、導覽正常且窄版無水平溢出',async({page})=>{
  await page.goto('/#/guide');
  const guide=page.getByRole('article',{name:'Pilot 操作指南'});
  await expect(guide).toContainText('PostgreSQL 保存平台控制資料');
  await expect(guide).toContainText('完整 Hop → Vertica → QA → Release 尚未驗收完成');
  await expect(guide).toContainText('CHECKED／PIPELINE_NOT_READY');
  await expect(guide).toContainText('HOP_RESULT_UNKNOWN');
  await expect(guide).not.toContainText('自行選擇 PostgreSQL 或 Vertica 作為寫入目標');
  await guide.getByRole('button',{name:'選擇專案開始操作'}).click();
  await expect(page).toHaveURL(/#\/projects$/);
  await page.goBack();await expect(guide).toBeVisible();
  await guide.getByRole('button',{name:'開啟平台設定中心'}).click();
  await expect(page).toHaveURL(/#\/system$/);
  await page.goBack();await expect(guide).toBeVisible();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+2)).toBe(true);
});
