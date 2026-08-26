# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: streamhub.spec.ts >> E2E-TC01-02：用户搜索、播放视频并发表评论和弹幕
- Location: e2e\streamhub.spec.ts:26:5

# Error details

```
Error: expect(locator).toHaveCount(expected) failed

Locator:  getByPlaceholder('请输入账号')
Expected: 0
Received: 1
Timeout:  10000ms

Call log:
  - Expect "toHaveCount" with timeout 10000ms
  - waiting for getByPlaceholder('请输入账号')
    23 × locator resolved to 1 element
       - unexpected value "1"

```

# Page snapshot

```yaml
- generic [ref=e3]:
  - navigation [ref=e4]:
    - generic [ref=e5]:
      - link "StreamHub" [ref=e6] [cursor=pointer]:
        - /url: "#/"
      - textbox "搜索视频、直播..." [ref=e14]
      - generic [ref=e19]:
        - button "登录" [ref=e20] [cursor=pointer]
        - button "注册" [ref=e21] [cursor=pointer]
  - complementary [ref=e22]:
    - navigation [ref=e23]:
      - link "首页" [ref=e24] [cursor=pointer]:
        - /url: "#/"
      - link "发现/直播" [ref=e30] [cursor=pointer]:
        - /url: "#/discover"
      - link "短视频" [ref=e35] [cursor=pointer]:
        - /url: "#/shorts"
      - link "订阅" [ref=e40] [cursor=pointer]:
        - /url: "#/subscriptions"
      - link "我的" [ref=e44] [cursor=pointer]:
        - /url: "#/profile"
  - main [ref=e49]:
    - generic [ref=e50]:
      - generic [ref=e53]:
        - button "推荐" [ref=e54] [cursor=pointer]
        - button "游戏" [ref=e55] [cursor=pointer]
        - button "音乐" [ref=e56] [cursor=pointer]
        - button "影视" [ref=e57] [cursor=pointer]
        - button "科技" [ref=e58] [cursor=pointer]
        - button "生活" [ref=e59] [cursor=pointer]
      - generic [ref=e60]:
        - generic [ref=e63] [cursor=pointer]:
          - generic [ref=e64]:
            - img "Big Buck Bunny 动画短片" [ref=e65]
            - generic [ref=e67]: 9:56
          - generic [ref=e72]:
            - img "创作者小明" [ref=e73]
            - generic [ref=e74]:
              - heading "Big Buck Bunny 动画短片" [level=3] [ref=e75]
              - generic [ref=e76]:
                - generic [ref=e77]: 创作者小明
                - generic [ref=e78]: 1.3万
        - paragraph [ref=e82]: 没有更多内容了
  - generic [ref=e84]:
    - generic [ref=e85]:
      - heading "登录" [level=2] [ref=e86]
      - button [ref=e87] [cursor=pointer]
    - generic [ref=e91]:
      - generic [ref=e92]:
        - generic [ref=e93]: 账号
        - textbox "请输入账号" [ref=e94]: user
      - generic [ref=e95]:
        - generic [ref=e96]: 密码
        - generic [ref=e97]:
          - textbox "请输入密码" [active] [ref=e98]: user123
          - button [ref=e99] [cursor=pointer]
      - paragraph [ref=e103]: 账号或密码错误
      - button "登录" [ref=e104] [cursor=pointer]
    - paragraph [ref=e106]:
      - text: 还没有账号？
      - button "立即注册" [ref=e107] [cursor=pointer]
    - generic [ref=e108]: 测试账号：admin/admin123, creator/creator123, user/user123
```

# Test source

```ts
  1   | import { expect, test, type Page } from '@playwright/test';
  2   | 
  3   | const e2eBackendUrl = process.env.E2E_BACKEND_URL || 'http://127.0.0.1:8001';
  4   | 
  5   | async function login(page: Page, account: string, password: string) {
  6   |   await page.goto('/#/');
  7   | 
  8   |   await page.getByRole('button', { name: '登录', exact: true }).click();
  9   |   await page.getByPlaceholder('请输入账号').fill(account);
  10  |   await page.getByPlaceholder('请输入密码').fill(password);
  11  |   await page.getByPlaceholder('请输入密码').press('Enter');
  12  | 
> 13  |   await expect(page.getByPlaceholder('请输入账号')).toHaveCount(0);
      |                                                ^ Error: expect(locator).toHaveCount(expected) failed
  14  | }
  15  | 
  16  | async function clearLogin(page: Page) {
  17  |   await page.evaluate(() => localStorage.removeItem('auth-storage'));
  18  |   await page.goto('/#/');
  19  |   await page.reload();
  20  | 
  21  |   await expect(
  22  |     page.getByRole('button', { name: '登录', exact: true })
  23  |   ).toBeVisible();
  24  | }
  25  | 
  26  | test('E2E-TC01-02：用户搜索、播放视频并发表评论和弹幕', async ({ page }) => {
  27  |   await login(page, 'user', 'user123');
  28  | 
  29  |   const keyword = '视频';
  30  |   await page.getByPlaceholder('搜索视频、直播...').fill(keyword);
  31  |   await page.getByPlaceholder('搜索视频、直播...').press('Enter');
  32  | 
  33  |   await expect(page).toHaveURL(/#\/search/);
  34  | 
  35  |   const firstVideoTitle = page.locator('main h3').first();
  36  |   await expect(firstVideoTitle).toBeVisible();
  37  |   await firstVideoTitle.click();
  38  | 
  39  |   await expect(page).toHaveURL(/#\/video\//);
  40  |   await expect(page.locator('video')).toBeVisible();
  41  | 
  42  |   const comment = `E2E-评论-${Date.now()}`;
  43  |   const commentInput = page.getByPlaceholder('写下你的评论...');
  44  | 
  45  |   const commentResponse = page.waitForResponse(
  46  |     (response) =>
  47  |       response.url().includes('/comments') &&
  48  |       response.request().method() === 'POST'
  49  |   );
  50  | 
  51  |   await commentInput.fill(comment);
  52  |   await commentInput.press('Enter');
  53  | 
  54  |   expect((await commentResponse).ok()).toBeTruthy();
  55  |   await expect(page.getByText(comment, { exact: true })).toBeVisible();
  56  | 
  57  |   const danmaku = `E2E-弹幕-${Date.now()}`;
  58  |   const danmakuInput = page.getByPlaceholder('发弹幕...').first();
  59  | 
  60  |   const danmakuResponse = page.waitForResponse(
  61  |     (response) =>
  62  |       response.url().includes('/danmaku') &&
  63  |       response.request().method() === 'POST'
  64  |   );
  65  | 
  66  |   await danmakuInput.fill(danmaku);
  67  |   await danmakuInput.press('Enter');
  68  | 
  69  |   expect((await danmakuResponse).ok()).toBeTruthy();
  70  |   await expect(danmakuInput).toHaveValue('');
  71  | });
  72  | 
  73  | test('E2E-TC03-05：创作者投稿，管理员审核，创作者查看结果', async ({ page }) => {
  74  |   const title = `E2E-投稿-${Date.now()}`;
  75  | 
  76  |   await login(page, 'creator', 'creator123');
  77  |   await page.goto('/#/upload');
  78  | 
  79  |   await page.getByRole('button', { name: '不选择文件，直接使用演示视频' }).click();
  80  |   await page.getByPlaceholder('2-100字').fill(title);
  81  |   await page.getByRole('button', { name: '发布并等待审核' }).click();
  82  | 
  83  |   await expect(page.getByText('投稿成功，等待管理员审核')).toBeVisible();
  84  | 
  85  |   await page.getByRole('button', { name: '去创作者中心' }).click();
  86  |   await page.getByRole('button', { name: '内容管理', exact: true }).click();
  87  |   await expect(page.getByText(title, { exact: true })).toBeVisible();
  88  |   const pendingCreatorRow = page
  89  |   .getByText(title, { exact: true })
  90  |   .locator('xpath=ancestor::tr');
  91  | 
  92  | await expect(
  93  |   pendingCreatorRow.getByText('审核中', { exact: true })
  94  | ).toBeVisible();
  95  | 
  96  |   await clearLogin(page);
  97  |   await login(page, 'admin', 'admin123');
  98  |   await page.goto('/#/admin');
  99  | 
  100 |   await expect(page.getByText(title, { exact: true })).toBeVisible();
  101 | 
  102 |   const pendingCard = page
  103 |     .locator('h3')
  104 |     .filter({ hasText: title })
  105 |     .locator('xpath=../../..');
  106 | 
  107 |   await pendingCard.getByTitle('通过').click();
  108 |   await expect(page.getByText('视频已通过审核。')).toBeVisible();
  109 | 
  110 |   await clearLogin(page);
  111 |   await login(page, 'creator', 'creator123');
  112 | await page.goto('/#/creator');
  113 | await page.getByRole('button', { name: '内容管理', exact: true }).click();
```