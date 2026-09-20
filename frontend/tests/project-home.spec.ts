import {test, expect} from '@playwright/test';

test('P0 專案首頁、搜尋、舊入口與返回', async ({page, request}) => {
  const response = await request.get('/api/projects');
  const projects = await response.json();
  expect(projects.length).toBeGreaterThan(0);
  await page.goto('/#/dashboard');
  const home = page.getByRole('region', {name: '專案工作區首頁'});
  await expect(home).toBeVisible();
  await expect(page.locator('aside nav button')).toHaveText(['專案工作區','Pilot 成果','平台設定中心','操作指南']);
  await home.getByLabel('搜尋專案').fill('no-project-match-unique-849872');
  await expect(home.getByText('沒有符合搜尋條件的專案。')).toBeVisible();
  await home.getByLabel('搜尋專案').fill(projects[0].project_name);
  await home.getByRole('button', {name: `進入專案 ${projects[0].project_name}`, exact: true}).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${projects[0].project_id}/settings$`));
  await expect(page.getByRole('tab', {name: '設定', exact: true})).toHaveAttribute('aria-selected', 'true');
  await page.goBack();
  await expect(home).toBeVisible();
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.goto('/#/usage');
  await expect(page.getByRole('region', {name: 'Pilot 成果', exact: true})).toBeVisible();
  await expect(page.getByText('查看模型用量紀錄（不是 Pilot 成效）')).toBeVisible();
});
