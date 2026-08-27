import { expect, test, type Page } from '@playwright/test';

const e2eBackendUrl = process.env.E2E_BACKEND_URL || 'http://127.0.0.1:8001';

async function login(page: Page, account: string, password: string) {
  await page.goto('/#/');

  await page.getByRole('button', { name: '登录', exact: true }).click();
  await page.getByPlaceholder('请输入账号').fill(account);
  await page.getByPlaceholder('请输入密码').fill(password);
  await page.getByPlaceholder('请输入密码').press('Enter');

  await expect(page.getByPlaceholder('请输入账号')).toHaveCount(0);
}

async function clearLogin(page: Page) {
  await page.evaluate(() => localStorage.removeItem('auth-storage'));
  await page.goto('/#/');
  await page.reload();

  await expect(
    page.getByRole('button', { name: '登录', exact: true })
  ).toBeVisible();
}

test('E2E-TC01-02：用户搜索、播放视频并发表评论和弹幕', async ({ page }) => {
  await login(page, 'user', 'user123');

  const keyword = '视频';
  await page.getByPlaceholder('搜索视频、直播...').fill(keyword);
  await page.getByPlaceholder('搜索视频、直播...').press('Enter');

  await expect(page).toHaveURL(/#\/search/);

  const firstVideoTitle = page.locator('main h3').first();
  await expect(firstVideoTitle).toBeVisible();
  await firstVideoTitle.click();

  await expect(page).toHaveURL(/#\/video\//);
  await expect(page.locator('video')).toBeVisible();

  const comment = `E2E-评论-${Date.now()}`;
  const commentInput = page.getByPlaceholder('写下你的评论...');

  const commentResponse = page.waitForResponse(
    (response) =>
      response.url().includes('/comments') &&
      response.request().method() === 'POST'
  );

  await commentInput.fill(comment);
  await commentInput.press('Enter');

  expect((await commentResponse).ok()).toBeTruthy();
  await expect(page.getByText(comment, { exact: true })).toBeVisible();

  const danmaku = `E2E-弹幕-${Date.now()}`;
  const danmakuInput = page.getByPlaceholder('发弹幕...').first();

  const danmakuResponse = page.waitForResponse(
    (response) =>
      response.url().includes('/danmaku') &&
      response.request().method() === 'POST'
  );

  await danmakuInput.fill(danmaku);
  await danmakuInput.press('Enter');

  expect((await danmakuResponse).ok()).toBeTruthy();
  await expect(danmakuInput).toHaveValue('');
});

test('E2E-TC03-05：创作者投稿，管理员审核，创作者查看结果', async ({ page }) => {
  const title = `E2E-投稿-${Date.now()}`;

  await login(page, 'creator', 'creator123');
  await page.goto('/#/upload');

  await page.getByRole('button', { name: '不选择文件，直接使用演示视频' }).click();
  await page.getByPlaceholder('2-100字').fill(title);
  await page.getByRole('button', { name: '发布并等待审核' }).click();

  await expect(page.getByText('投稿成功，等待管理员审核')).toBeVisible();

  await page.getByRole('button', { name: '去创作者中心' }).click();
  await page.getByRole('button', { name: '内容管理', exact: true }).click();
  await expect(page.getByText(title, { exact: true })).toBeVisible();
  const pendingCreatorRow = page
  .getByText(title, { exact: true })
  .locator('xpath=ancestor::tr');

await expect(
  pendingCreatorRow.getByText('审核中', { exact: true })
).toBeVisible();

  await clearLogin(page);
  await login(page, 'admin', 'admin123');
  await page.goto('/#/admin');

  await expect(page.getByText(title, { exact: true })).toBeVisible();

  const pendingCard = page
    .locator('h3')
    .filter({ hasText: title })
    .locator('xpath=../../..');

  await pendingCard.getByTitle('通过').click();
  await expect(page.getByText('视频已通过审核。')).toBeVisible();

  await clearLogin(page);
  await login(page, 'creator', 'creator123');
await page.goto('/#/creator');
await page.getByRole('button', { name: '内容管理', exact: true }).click();

const creatorRow = page
    .getByText(title, { exact: true })
    .locator('xpath=ancestor::tr');

  await expect(creatorRow.getByText('已通过', { exact: true })).toBeVisible();
});

test('E2E-TC06-08：创建直播、观众发弹幕、接口结束直播', async ({ browser }) => {
  const creatorContext = await browser.newContext();
  const creator = await creatorContext.newPage();
  const title = `E2E-直播-${Date.now()}`;

  await login(creator, 'creator', 'creator123');
  await creator.goto('/#/live/start');

  await creator
    .getByPlaceholder('例如：软件工程项目答疑直播')
    .fill(title);

  await creator.getByRole('button', { name: '确认开播' }).click();

  await expect(creator).toHaveURL(/#\/live\//);
  await expect(creator.getByText(title, { exact: true })).toBeVisible();

  const liveUrl = creator.url();
  const roomId = liveUrl.match(/#\/live\/([^?]+)/)?.[1];
  expect(roomId).toBeTruthy();

  const viewerContext = await browser.newContext();
  const viewer = await viewerContext.newPage();

  await login(viewer, 'user', 'user123');
  await viewer.goto(liveUrl);

  await expect(viewer.getByText('直播间聊天', { exact: true })).toBeVisible();
  await expect(viewer.getByText('聊天已连接', { exact: true })).toBeVisible();

  const message = `E2E-直播弹幕-${Date.now()}`;
  const chatInput = viewer.getByPlaceholder('发弹幕...');

  await chatInput.fill(message);
  await chatInput.press('Enter');

  const chatPanel = viewer
  .getByRole('heading', { name: '直播间聊天', exact: true })
  .locator('xpath=../..');

await expect(
  chatPanel.getByText(message, { exact: true })
).toBeVisible();

  const token = await creator.evaluate(() => {
    const raw = localStorage.getItem('auth-storage');
    return raw ? JSON.parse(raw).state.token : '';
  });

  const endResponse = await creator.request.post(
    `${e2eBackendUrl}/api/live/rooms/${roomId}/end`,
    { headers: { Authorization: `Bearer ${token}` } }
  );

  expect(endResponse.ok()).toBeTruthy();

  await viewer.reload();
  await expect(viewer.getByText('已结束', { exact: true })).toBeVisible();

  await viewerContext.close();
  await creatorContext.close();
});
