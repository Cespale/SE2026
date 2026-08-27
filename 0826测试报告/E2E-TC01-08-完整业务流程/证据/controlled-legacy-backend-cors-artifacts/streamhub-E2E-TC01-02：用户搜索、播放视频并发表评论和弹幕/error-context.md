# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: streamhub.spec.ts >> E2E-TC01-02：用户搜索、播放视频并发表评论和弹幕
- Location: e2e\streamhub.spec.ts:24:5

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
  3   | async function login(page: Page, account: string, password: string) {
  4   |   await page.goto('/#/');
  5   | 
  6   |   await page.getByRole('button', { name: '登录', exact: true }).click();
  7   |   await page.getByPlaceholder('请输入账号').fill(account);
  8   |   await page.getByPlaceholder('请输入密码').fill(password);
  9   |   await page.getByPlaceholder('请输入密码').press('Enter');
  10  | 
> 11  |   await expect(page.getByPlaceholder('请输入账号')).toHaveCount(0);
      |                                                ^ Error: expect(locator).toHaveCount(expected) failed
  12  | }
  13  | 
  14  | async function clearLogin(page: Page) {
  15  |   await page.evaluate(() => localStorage.removeItem('auth-storage'));
  16  |   await page.goto('/#/');
  17  |   await page.reload();
  18  | 
  19  |   await expect(
  20  |     page.getByRole('button', { name: '登录', exact: true })
  21  |   ).toBeVisible();
  22  | }
  23  | 
  24  | test('E2E-TC01-02：用户搜索、播放视频并发表评论和弹幕', async ({ page }) => {
  25  |   await login(page, 'user', 'user123');
  26  | 
  27  |   const keyword = '视频';
  28  |   await page.getByPlaceholder('搜索视频、直播...').fill(keyword);
  29  |   await page.getByPlaceholder('搜索视频、直播...').press('Enter');
  30  | 
  31  |   await expect(page).toHaveURL(/#\/search/);
  32  | 
  33  |   const firstVideoTitle = page.locator('main h3').first();
  34  |   await expect(firstVideoTitle).toBeVisible();
  35  |   await firstVideoTitle.click();
  36  | 
  37  |   await expect(page).toHaveURL(/#\/video\//);
  38  |   await expect(page.locator('video')).toBeVisible();
  39  | 
  40  |   const comment = `E2E-评论-${Date.now()}`;
  41  |   const commentInput = page.getByPlaceholder('写下你的评论...');
  42  | 
  43  |   const commentResponse = page.waitForResponse(
  44  |     (response) =>
  45  |       response.url().includes('/comments') &&
  46  |       response.request().method() === 'POST'
  47  |   );
  48  | 
  49  |   await commentInput.fill(comment);
  50  |   await commentInput.press('Enter');
  51  | 
  52  |   expect((await commentResponse).ok()).toBeTruthy();
  53  |   await expect(page.getByText(comment, { exact: true })).toBeVisible();
  54  | 
  55  |   const danmaku = `E2E-弹幕-${Date.now()}`;
  56  |   const danmakuInput = page.getByPlaceholder('发弹幕...').first();
  57  | 
  58  |   const danmakuResponse = page.waitForResponse(
  59  |     (response) =>
  60  |       response.url().includes('/danmaku') &&
  61  |       response.request().method() === 'POST'
  62  |   );
  63  | 
  64  |   await danmakuInput.fill(danmaku);
  65  |   await danmakuInput.press('Enter');
  66  | 
  67  |   expect((await danmakuResponse).ok()).toBeTruthy();
  68  |   await expect(danmakuInput).toHaveValue('');
  69  | });
  70  | 
  71  | test('E2E-TC03-05：创作者投稿，管理员审核，创作者查看结果', async ({ page }) => {
  72  |   const title = `E2E-投稿-${Date.now()}`;
  73  | 
  74  |   await login(page, 'creator', 'creator123');
  75  |   await page.goto('/#/upload');
  76  | 
  77  |   await page.getByRole('button', { name: '不选择文件，直接使用演示视频' }).click();
  78  |   await page.getByPlaceholder('2-100字').fill(title);
  79  |   await page.getByRole('button', { name: '发布并等待审核' }).click();
  80  | 
  81  |   await expect(page.getByText('投稿成功，等待管理员审核')).toBeVisible();
  82  | 
  83  |   await page.getByRole('button', { name: '去创作者中心' }).click();
  84  |   await page.getByRole('button', { name: '内容管理', exact: true }).click();
  85  |   await expect(page.getByText(title, { exact: true })).toBeVisible();
  86  |   const pendingCreatorRow = page
  87  |   .getByText(title, { exact: true })
  88  |   .locator('xpath=ancestor::tr');
  89  | 
  90  | await expect(
  91  |   pendingCreatorRow.getByText('审核中', { exact: true })
  92  | ).toBeVisible();
  93  | 
  94  |   await clearLogin(page);
  95  |   await login(page, 'admin', 'admin123');
  96  |   await page.goto('/#/admin');
  97  | 
  98  |   await expect(page.getByText(title, { exact: true })).toBeVisible();
  99  | 
  100 |   const pendingCard = page
  101 |     .locator('h3')
  102 |     .filter({ hasText: title })
  103 |     .locator('xpath=../../..');
  104 | 
  105 |   await pendingCard.getByTitle('通过').click();
  106 |   await expect(page.getByText('视频已通过审核。')).toBeVisible();
  107 | 
  108 |   await clearLogin(page);
  109 |   await login(page, 'creator', 'creator123');
  110 | await page.goto('/#/creator');
  111 | await page.getByRole('button', { name: '内容管理', exact: true }).click();
```