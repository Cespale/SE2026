# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: streamhub.spec.ts >> E2E-TC06-08：创建直播、观众发弹幕、接口结束直播
- Location: e2e\streamhub.spec.ts:120:5

# Error details

```
Test timeout of 30000ms exceeded.
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - navigation [ref=e4]:
    - generic [ref=e5]:
      - link "StreamHub" [ref=e6] [cursor=pointer]:
        - /url: "#/"
      - textbox "搜索视频、直播..." [ref=e14]
      - generic [ref=e18]:
        - button "投稿" [ref=e19] [cursor=pointer]
        - button "创作者小明 创作者小明" [ref=e24] [cursor=pointer]:
          - img "创作者小明" [ref=e25]
          - generic [ref=e26]: 创作者小明
  - complementary [ref=e27]:
    - navigation [ref=e28]:
      - link "首页" [ref=e29] [cursor=pointer]:
        - /url: "#/"
      - link "发现/直播" [ref=e34] [cursor=pointer]:
        - /url: "#/discover"
      - link "短视频" [ref=e39] [cursor=pointer]:
        - /url: "#/shorts"
      - link "订阅" [ref=e44] [cursor=pointer]:
        - /url: "#/subscriptions"
      - link "我的" [ref=e48] [cursor=pointer]:
        - /url: "#/profile"
      - link "上传视频" [ref=e53] [cursor=pointer]:
        - /url: "#/upload"
      - link "创作者中心" [ref=e58] [cursor=pointer]:
        - /url: "#/creator"
      - link "开始直播" [ref=e65] [cursor=pointer]:
        - /url: "#/live/start"
  - main [ref=e73]:
    - generic [ref=e74]:
      - button "返回" [ref=e75] [cursor=pointer]
      - generic [ref=e78]:
        - generic [ref=e79]:
          - generic [ref=e80]:
            - generic [ref=e82]:
              - generic [ref=e83]: LIVE
              - generic [ref=e84]: "0"
              - generic [ref=e90]: 聊天已连接
            - generic [ref=e91]:
              - button [ref=e92] [cursor=pointer]
              - button "弹幕" [ref=e97] [cursor=pointer]
              - button [ref=e98] [cursor=pointer]
          - generic [ref=e105]:
            - generic [ref=e106]:
              - img "创作者小明" [ref=e107]
              - generic [ref=e108]:
                - heading "E2E-直播-1787642687677" [level=1] [ref=e109]
                - generic [ref=e110]:
                  - generic [ref=e111]: 创作者小明
                  - generic [ref=e112]: 直播
                - paragraph [ref=e113]: 当前为课程作业演示直播。真实推流可后续接入 SRS / WebRTC / OBS。
            - generic [ref=e114]:
              - button "关注" [ref=e115] [cursor=pointer]
              - button [ref=e118] [cursor=pointer]
        - generic [ref=e125]:
          - generic [ref=e126]:
            - heading "直播间聊天" [level=3] [ref=e127]
            - generic [ref=e128]: "0"
          - paragraph [ref=e136]: 创作者小明 进入直播间
          - generic [ref=e138]:
            - generic [ref=e139]:
              - button [ref=e140] [cursor=pointer]
              - button [ref=e141] [cursor=pointer]
              - button [ref=e142] [cursor=pointer]
              - button [ref=e143] [cursor=pointer]
              - button [ref=e144] [cursor=pointer]
            - generic [ref=e145]:
              - textbox "发弹幕..." [ref=e146]
              - button [disabled] [ref=e147]
```