# StreamHub 在线视频与直播平台

## 一、项目简介

StreamHub 是一个基于 React + FastAPI + PostgreSQL + Docker 的在线视频与直播平台项目。

本项目面向“在线视频与直播网站”场景，参考抖音、哔哩哔哩、YouTube 等真实视频平台的基础功能，设计并实现了一个集视频浏览、视频播放、搜索推荐、弹幕评论、用户登录注册、创作者中心、管理后台、直播互动等功能于一体的综合视频社区系统。

本系统的目标是模拟一个完整的视频平台业务流程，使普通用户可以浏览视频、搜索视频、观看视频、发表评论和弹幕；创作者可以进入创作者中心、上传和管理视频；管理员可以进入后台进行视频审核、用户管理、举报处理和敏感词管理。

项目采用前后端分离架构，前端负责页面展示与用户交互，后端负责接口服务、数据处理、用户认证、视频数据管理和数据库交互。数据库使用 PostgreSQL，并通过 Docker Compose 实现一键启动，方便其他用户 clone 项目后直接运行。

---

## 二、项目技术栈

### 1. 前端技术

- React
- TypeScript
- React Router
- Zustand 状态管理
- Tailwind CSS
- Framer Motion 动画
- Lucide React 图标库
- Webpack Dev Server

前端主要负责：

- 首页视频流展示
- 视频详情页播放
- 搜索页面
- 短视频页面
- 订阅页面
- 用户个人中心
- 登录注册弹窗
- 创作者中心
- 管理后台
- 直播页面
- 弹幕与评论交互

---

### 2. 后端技术

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Passlib + bcrypt 密码加密
- Uvicorn
- OpenCV 视频封面生成
- Docker

后端主要负责：

- 用户登录注册
- Token 认证
- 视频列表接口
- 视频详情接口
- 评论接口
- 弹幕接口
- 视频上传接口
- 创作者视频接口
- 管理员审核接口
- 直播间接口
- 本地视频自动扫描
- 视频封面自动生成
- 数据库初始化

---

### 3. 数据库

数据库使用 PostgreSQL，主要保存：

- 用户数据
- 视频数据
- 分类数据
- 评论数据
- 弹幕数据
- 直播间数据
- 关注收藏数据
- 审核状态数据

本项目已经提供数据库初始化 SQL 文件：

```text
backend/docker-init/01_streamhub_backup.sql
```

当第一次启动 Docker 数据库时，会自动导入该 SQL 文件，使项目拥有完整的初始数据。

---

### 4. Docker 部署

项目使用 Docker Compose 编排三个服务：

```text
postgres   PostgreSQL 数据库服务
backend    FastAPI 后端服务
frontend   React 前端服务
```

用户只需要安装 Docker Desktop，即可通过脚本一键启动整个项目。

---

## 三、项目功能介绍

### 1. 首页视频推荐

首页展示系统中的视频内容，支持按照分类筛选视频。

功能包括：

- 视频卡片展示
- 视频封面显示
- 视频标题显示
- 创作者头像显示
- 播放量显示
- 视频时长显示
- 点击进入视频详情页

系统中的视频数据来自数据库，数据库中的视频路径对应：

```text
public/demo-videos
```

视频封面来自：

```text
public/demo-covers
```

---

### 2. 视频播放功能

用户点击视频卡片后，可以进入视频详情页。

视频详情页包含：

- 视频播放器
- 视频标题
- 视频简介
- 视频标签
- 播放量
- 点赞数
- 收藏数
- 作者信息
- 相关推荐
- 弹幕输入框
- 评论区

视频播放使用浏览器原生 video 标签实现。

---

### 3. 弹幕功能

视频详情页支持弹幕功能。

用户可以：

- 查看已有弹幕
- 输入弹幕内容
- 选择弹幕颜色
- 发送弹幕
- 在视频区域看到滚动弹幕效果

如果后端接口正常，弹幕会写入数据库；如果接口异常，前端也会使用模拟数据保证页面展示效果。

---

### 4. 评论功能

视频详情页支持评论功能。

用户可以：

- 查看评论列表
- 发布新评论
- 查看评论用户头像
- 查看评论时间
- 查看评论点赞数

评论数据由后端接口提供，并存储在 PostgreSQL 数据库中。

---

### 5. 搜索功能

顶部导航栏提供搜索框。

用户可以搜索：

- 视频标题
- 视频关键词
- 直播内容

搜索结果页支持：

- 综合排序
- 最新排序
- 最热排序

---

### 6. 用户登录与注册

系统支持用户登录和注册。

测试账号如下：

```text
普通用户：
user / user123

创作者：
creator / creator123

管理员：
admin / admin123
```

用户登录后，前端会保存 token，并在后续请求中携带认证信息。

不同用户类型拥有不同权限：

```text
user_type = 0    普通用户
user_type = 1    创作者
user_type = 2    管理员
```

---

### 7. 创作者中心

创作者账号登录后，可以进入创作者中心。

创作者中心包含：

- 数据概览
- 内容管理
- 粉丝管理
- 评论管理

数据概览中展示：

- 总播放量
- 粉丝数
- 获赞数
- 近 7 天数据趋势

内容管理中展示创作者上传的视频，包括：

- 视频标题
- 播放量
- 点赞数
- 审核状态
- 上传时间

---

### 8. 视频上传功能

创作者账号可以进入上传页面。

上传页面模拟真实视频平台的上传流程：

- 选择视频文件
- 显示上传进度
- 填写标题
- 填写简介
- 选择分类
- 添加标签
- 发布视频

当前项目为了方便演示，上传视频会使用固定的视频地址作为演示资源。

---

### 9. 管理后台

管理员账号登录后，可以进入管理后台。

管理后台包括：

- 视频审核
- 用户管理
- 举报处理
- 敏感词管理

视频审核功能中，管理员可以查看待审核视频，并进行：

- 通过
- 驳回

用户管理页面展示用户状态。

举报处理页面展示模拟举报数据。

敏感词管理页面展示模拟敏感词数据。

---

### 10. 社区互动:关注 / 私聊 / 通知 / @提及

系统支持完整的社区互动功能,模拟主流视频平台的社交体验。

#### 关注 / 粉丝

- 用户主页和视频作者卡片均带"关注"按钮
- 关注后按钮变成"已关注",双向关注显示"互相关注"
- 用户主页实时显示**真实**粉丝数和关注数

#### 私聊(1 对 1 实时聊天)

- 任意用户主页右上角有"**发消息**"按钮,点击直接打开会话窗
- 导航栏右上角💬图标进入私信中心,左侧会话列表(带未读角标)+ 右侧聊天窗
- 消息基于 **WebSocket** 实时推送,无需刷新
- 支持**撤回**(2 分钟内 hover 自己消息即可撤回)
- **已读状态**显示
- 多端同步:同一账号在多个窗口登录,所有窗口都能实时收到消息

#### 通知中心

- 导航栏右上角🔔图标,有未读时显示红点 + 数字
- 通知页分 6 类 Tab:全部 / 点赞 / 评论 / 关注 / @提及 / 系统
- 触发场景:
  - 别人关注你
  - 别人在你的视频下评论
  - 别人回复你的评论
  - 别人在评论里 @你
- 点击通知可跳到对应视频或用户主页

#### @提及 + 评论二级回复

- 评论里输入 `@用户昵称` → 该用户收到 @提醒,评论里 @文本自动渲染为蓝色
- 任意评论下的"回复"按钮可用 → 输入框顶部显示 `回复 @xxx`
- 二级回复折叠为"查看 N 条回复",点击展开懒加载
- 回复显示 "xxx 回复 @yyy: ..." 嵌套样式

---

### 11. 直播功能

系统提供直播相关页面，包括：

- 直播间列表
- 直播详情页
- 开播页面
- 直播聊天
- 直播弹幕
- 在线人数显示

直播功能主要用于模拟在线视频平台中的直播互动场景。

---

### 12. 本地视频自动导入

后端启动时，会扫描：

```text
public/demo-videos
```

系统会自动读取该目录下的视频文件，并写入数据库。

同时，系统会自动为视频生成封面图，并保存到：

```text
public/demo-covers
```

如果后续添加新视频，只需要把视频文件放入：

```text
public/demo-videos
```

然后重新启动后端，系统就会自动同步视频数据。

---

## 四、项目目录结构

```text
StreamHub
├── backend
│   ├── app
│   │   ├── main.py              后端主程序
│   │   ├── database.py          数据库连接配置
│   │   ├── models.py            数据库模型
│   │   ├── schemas.py           数据校验模型
│   │   └── security.py          登录认证与密码加密
│   │
│   ├── docker-init
│   │   └── 01_streamhub_backup.sql
│   │
│   ├── Dockerfile               后端 Docker 构建文件
│   ├── requirements.txt         Python 依赖
│   ├── .env.example             后端环境变量模板
│   └── schema.sql               数据库结构参考文件
│
├── public
│   ├── demo-videos              本地演示视频文件
│   └── demo-covers              视频封面文件
│
├── src
│   ├── api.ts                   前端请求封装
│   ├── App.tsx                  前端路由入口
│   ├── index.tsx                React 入口
│   │
│   ├── components               前端组件
│   │   ├── auth                 登录注册组件
│   │   ├── layout               导航栏和侧边栏
│   │   └── video                视频卡片和分类组件
│   │
│   ├── pages                    页面组件
│   │   ├── HomePage.tsx         首页
│   │   ├── VideoPage.tsx        视频详情页
│   │   ├── SearchPage.tsx       搜索页
│   │   ├── UploadPage.tsx       上传页
│   │   ├── CreatorPage.tsx      创作者中心
│   │   ├── AdminPage.tsx        管理后台
│   │   ├── LivePage.tsx         直播页
│   │   └── LiveStartPage.tsx    开播页
│   │
│   ├── stores                   Zustand 状态管理
│   │   ├── authStore.ts         用户登录状态
│   │   ├── videoStore.ts        视频数据状态
│   │   └── liveStore.ts         直播状态
│   │
│   └── styles
│       └── index.css            全局样式
│
├── docker-compose.yml           Docker Compose 编排文件
├── Dockerfile.frontend          前端 Docker 构建文件
├── webpack.config.js            Webpack 配置
├── package.json                 前端依赖配置
├── package-lock.json            前端依赖锁定文件
├── start.bat                    Windows 一键启动脚本
├── stop.bat                     Windows 停止脚本
├── reset.bat                    Windows 重置数据库脚本
├── .dockerignore                Docker 构建忽略文件
├── .gitignore                   Git 忽略文件
└── README.md                    项目说明文档
```

---

## 五、运行环境要求

运行本项目前，需要安装：

### 1. Docker Desktop

必须安装 Docker Desktop，并确保 Docker Desktop 已经启动。

Docker 用于运行：

- PostgreSQL 数据库
- FastAPI 后端
- React 前端

### 2. Git

用于克隆项目代码。

### 3. 浏览器

推荐使用：

- Microsoft Edge
- Google Chrome

---

## 六、快速启动方式

### 1. 克隆项目

```powershell
git clone 项目仓库地址
```

进入项目目录：

```powershell
cd StreamHub
```

---

### 2. 启动 Docker Desktop

在 Windows 开始菜单中搜索：

```text
Docker Desktop
```

打开后等待 Docker Desktop 完全启动。

可以在 PowerShell 中执行：

```powershell
docker ps
```

如果没有报错，说明 Docker 已经正常运行。

---

### 3. 一键启动项目

在项目根目录执行：

```powershell
.\start.bat
```

或者手动执行：

```powershell
docker compose up -d
```

第一次启动时，Docker 会初始化数据库、启动后端和前端，可能需要等待 1 到 2 分钟。

---

### 4. 访问系统

前端访问地址：

```text
http://localhost:5173
```

后端 API 地址：

```text
http://localhost:8000
```

视频接口测试地址：

```text
http://localhost:8000/api/videos
```

---

## 七、测试账号

### 1. 普通用户账号

```text
账号：user
密码：user123
```

普通用户可以：

- 浏览视频
- 搜索视频
- 播放视频
- 发送评论
- 发送弹幕
- 查看个人页面

---

### 2. 创作者账号

```text
账号：creator
密码：creator123
```

创作者可以：

- 使用普通用户功能
- 进入创作者中心
- 查看创作数据
- 管理视频内容
- 上传视频

---

### 3. 管理员账号

```text
账号：admin
密码：admin123
```

管理员可以：

- 使用普通用户功能
- 进入管理后台
- 审核视频
- 查看用户管理
- 处理举报
- 管理敏感词

---

## 八、常用操作命令

### 1. 启动项目

```powershell
.\start.bat
```

或者：

```powershell
docker compose up -d
```

---

### 2. 停止项目

```powershell
.\stop.bat
```

或者：

```powershell
docker compose down
```

---

### 3. 重置数据库

如果想恢复初始数据，可以执行：

```powershell
.\reset.bat
```

或者手动执行：

```powershell
docker compose down -v
docker compose up -d
```

重置后，系统会重新导入：

```text
backend/docker-init/01_streamhub_backup.sql
```

---

### 4. 查看运行中的容器

```powershell
docker ps
```

正常情况下应该看到三个容器：

```text
streamhub-postgres
streamhub-backend
streamhub-frontend
```

---

### 5. 查看后端日志

```powershell
docker logs streamhub-backend --tail 100
```

---

### 6. 查看前端日志

```powershell
docker logs streamhub-frontend --tail 100
```

---

### 7. 查看数据库数据

查看视频数量：

```powershell
docker exec streamhub-postgres psql -U postgres -d streamhub -c "select count(*) from videos;"
```

查看用户：

```powershell
docker exec streamhub-postgres psql -U postgres -d streamhub -c "select account, nickname, user_type from users;"
```

---

## 九、Docker 服务说明

### 1. PostgreSQL 服务

服务名：

```text
postgres
```

容器名：

```text
streamhub-postgres
```

端口映射：

```text
本机 5433 -> 容器 5432
```

数据库信息：

```text
数据库名：streamhub
用户名：postgres
密码：123456
```

---

### 2. 后端服务

服务名：

```text
backend
```

容器名：

```text
streamhub-backend
```

端口映射：

```text
本机 8000 -> 容器 8000
```

后端启动命令：

```text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

### 3. 前端服务

服务名：

```text
frontend
```

容器名：

```text
streamhub-frontend
```

端口映射：

```text
本机 5173 -> 容器 3266
```

前端启动命令：

```text
npm run dev -- --host 0.0.0.0
```

---

## 十、数据库初始化说明

本项目提供了完整的数据库初始化文件：

```text
backend/docker-init/01_streamhub_backup.sql
```

Docker Compose 中 PostgreSQL 服务会将：

```text
backend/docker-init
```

挂载到容器内部：

```text
/docker-entrypoint-initdb.d
```

PostgreSQL 容器第一次创建数据库时，会自动执行该目录下的 SQL 文件。

因此，当别人第一次 clone 项目并运行：

```powershell
.\start.bat
```

数据库会自动生成完整初始数据。

初始数据包括：

- 用户账号
- 视频分类
- 视频信息
- 评论信息
- 弹幕信息
- 直播间信息
- 审核状态信息

---

## 十一、视频资源说明

本项目的视频资源存放在：

```text
public/demo-videos
```

视频封面资源存放在：

```text
public/demo-covers
```

数据库中保存的是相对路径，例如：

```text
/demo-videos/video1.mp4
/demo-covers/video1.jpg
```

因此，提交项目时必须保留：

```text
public/demo-videos
public/demo-covers
```

否则别人 clone 后会出现视频无法播放或封面无法显示的问题。

---

## 十二、如何添加新视频

如果需要添加新的视频资源，可以按照下面步骤操作。

### 1. 放入视频文件

将 mp4 视频放入：

```text
public/demo-videos
```

例如：

```text
public/demo-videos/new-video.mp4
```

---

### 2. 重启后端

执行：

```powershell
docker compose restart backend
```

后端启动时会自动扫描该目录，并将新视频写入数据库。

---

### 3. 查看首页

重新打开：

```text
http://localhost:5173
```

新视频会出现在首页视频列表中。

---

## 十三、前后端接口说明

### 1. 用户接口

登录：

```text
POST /api/auth/login
```

注册：

```text
POST /api/auth/register
```

获取当前用户：

```text
GET /api/auth/me
```

更新用户资料：

```text
PATCH /api/auth/me
```

---

### 2. 视频接口

获取视频列表：

```text
GET /api/videos
```

获取视频详情：

```text
GET /api/videos/{video_id}
```

发布视频：

```text
POST /api/videos
```

点赞视频：

```text
POST /api/videos/{video_id}/like
```

收藏视频：

```text
POST /api/videos/{video_id}/favorite
```

获取相关推荐：

```text
GET /api/videos/{video_id}/related
```

---

### 3. 评论接口

获取评论：

```text
GET /api/videos/{video_id}/comments
```

发表评论：

```text
POST /api/videos/{video_id}/comments
```

---

### 4. 弹幕接口

获取弹幕：

```text
GET /api/videos/{video_id}/danmaku
```

发送弹幕：

```text
POST /api/videos/{video_id}/danmaku
```

---

### 5. 分类接口

获取分类：

```text
GET /api/categories
```

---

### 6. 创作者接口

获取创作者视频：

```text
GET /api/creator/videos
```

---

### 7. 管理员接口

获取待审核视频：

```text
GET /api/admin/videos/pending
```

审核视频：

```text
PATCH /api/admin/videos/{video_id}/audit
```

---

### 8. 直播接口

获取直播间列表：

```text
GET /api/live/rooms
```

获取直播间详情：

```text
GET /api/live/rooms/{room_id}
```

创建直播间：

```text
POST /api/live/rooms
```

结束直播间：

```text
POST /api/live/rooms/{room_id}/end
```

直播 WebSocket：

```text
/ws/live/{room_id}
```

---

### 9. 社区互动接口

#### 关注 / 粉丝

```text
POST   /api/users/{user_id}/follow         关注
DELETE /api/users/{user_id}/follow         取关
GET    /api/users/{user_id}/relation       获取关系 + 粉丝/关注数
GET    /api/users/{user_id}/followers      粉丝列表
GET    /api/users/{user_id}/following      关注列表
GET    /api/users/{user_id}                用户主页资料
```

#### 通知中心

```text
GET  /api/notifications                  通知列表(?notif_type=&only_unread=&offset=&limit=)
GET  /api/notifications/unread-count     未读数(通知 + 私聊)
POST /api/notifications/{id}/read        标记单条已读
POST /api/notifications/read-all         全部已读
```

#### 私聊

```text
GET    /api/chat/conversations                   我的会话列表
POST   /api/chat/conversations                   创建/获取与某人的会话
GET    /api/chat/conversations/{id}/messages    历史消息(分页)
POST   /api/chat/conversations/{id}/messages    HTTP 发消息(WS 兜底)
POST   /api/chat/messages/{id}/recall            撤回(2分钟内)
POST   /api/chat/conversations/{id}/read         标记会话已读
```

私聊 WebSocket:

```text
/ws/chat?token=xxx
```

WS 消息协议:

```text
send / message / recall / read / typing / ping-pong
```

#### 评论二级回复

```text
GET  /api/comments/{id}/replies           获取某条评论的回复列表
```

`POST /api/videos/{id}/comments` 升级支持参数 `parentId`、`replyToUserId`,自动解析评论正文中的 `@用户名` 并触发通知。

---

## 十四、系统角色与权限设计

系统中用户分为三种角色。

### 1. 普通用户

权限等级：

```text
user_type = 0
```

普通用户可以：

- 浏览首页
- 搜索视频
- 观看视频
- 发送评论
- 发送弹幕
- 查看个人中心

---

### 2. 创作者

权限等级：

```text
user_type = 1
```

创作者可以：

- 拥有普通用户全部功能
- 进入创作者中心
- 上传视频
- 管理自己的视频
- 查看创作数据

---

### 3. 管理员

权限等级：

```text
user_type = 2
```

管理员可以：

- 拥有普通用户全部功能
- 进入管理后台
- 审核视频
- 管理用户
- 处理举报
- 管理敏感词

---

## 十五、项目亮点

### 1. 前后端分离

前端和后端通过 REST API 通信，结构清晰，便于维护和扩展。

---

### 2. Docker 一键启动

项目使用 Docker Compose 管理前端、后端和数据库，降低运行复杂度。

别人 clone 项目后，只需要执行：

```powershell
.\start.bat
```

即可启动完整系统。

---

### 3. 数据库自动初始化

系统提供 SQL 备份文件，PostgreSQL 第一次启动时会自动导入数据。

这保证了不同电脑运行项目时，可以看到一致的初始数据。

---

### 4. 本地视频自动扫描

后端会自动扫描本地视频目录，将视频写入数据库，减少手动配置工作。

---

### 5. 支持多角色权限

系统区分普通用户、创作者、管理员，使平台业务流程更加完整。

---

### 6. 功能模块完整

项目包含视频平台常见功能：

- 视频推荐
- 视频搜索
- 视频播放
- 弹幕
- 评论
- 登录注册
- 创作者中心
- 管理后台
- 直播间
- 视频审核

---

## 十六、常见问题

### 1. 页面打不开怎么办？

先确认 Docker 是否启动：

```powershell
docker ps
```

如果没有看到三个容器，执行：

```powershell
docker compose up -d
```

---

### 2. localhost:5173 打不开怎么办？

查看前端日志：

```powershell
docker logs streamhub-frontend --tail 100
```

确认前端是否运行在 3266 端口。

本项目端口映射为：

```text
5173 -> 3266
```

---

### 3. 登录很慢怎么办？

第一次启动时，后端和数据库需要初始化，可能会慢一些。

等待 1 到 2 分钟后再尝试登录。

---

### 4. 视频无法播放怎么办？

确认视频文件是否存在：

```text
public/demo-videos
```

如果视频文件没有提交到项目中，页面会显示视频数据但无法播放。

---

### 5. 封面不显示怎么办？

确认封面文件是否存在：

```text
public/demo-covers
```

也可以重启后端，让后端重新生成封面：

```powershell
docker compose restart backend
```

---

### 6. 数据库数据不对怎么办？

执行：

```powershell
.\reset.bat
```

该命令会删除当前数据库，并重新导入初始化 SQL 文件。

---

### 7. Docker 构建很慢怎么办？

第一次构建会下载 Python、Node 和依赖库，速度较慢是正常的。

之后再次运行可以直接执行：

```powershell
docker compose up -d
```

不需要每次都重新 build。

---

## 十七、开发模式运行方式

如果不想使用 Docker 启动前端和后端，也可以只使用 Docker 启动数据库。

### 1. 启动数据库

```powershell
docker compose up -d postgres
```

---

### 2. 启动后端

进入后端目录：

```powershell
cd backend
```

创建虚拟环境：

```powershell
python -m venv .venv
```

激活虚拟环境：

```powershell
.\.venv\Scripts\activate
```

安装依赖：

```powershell
pip install -r requirements.txt
```

启动后端：

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

---

### 3. 启动前端

回到项目根目录：

```powershell
cd ..
```

安装依赖：

```powershell
npm install
```

启动前端：

```powershell
npm run dev
```

---

## 十八、项目提交说明

提交到 GitHub 或 Gitee 时，必须提交：

```text
src
backend/app
backend/docker-init/01_streamhub_backup.sql
public/demo-videos
public/demo-covers
docker-compose.yml
Dockerfile.frontend
backend/Dockerfile
package.json
package-lock.json
webpack.config.js
start.bat
stop.bat
reset.bat
README.md
```

不要提交：

```text
node_modules
backend/.venv
backend/.env
dist
build
__pycache__
```

建议 `.gitignore` 包含：

```gitignore
node_modules/
dist/
build/

backend/.venv/
backend/.env

__pycache__/
*.pyc
*.pyo

.DS_Store
.vscode/
.idea/
```

---

## 十九、启动流程总结

完整启动流程如下：

```text
1. 打开 Docker Desktop
2. 进入项目根目录
3. 执行 .\start.bat
4. 等待 1 到 2 分钟
5. 打开 http://localhost:5173
6. 使用测试账号登录
```

如果需要停止：

```text
执行 .\stop.bat
```

如果需要恢复初始数据库：

```text
执行 .\reset.bat
```

---

## 二十、项目总结

StreamHub 是一个较完整的在线视频与直播平台原型系统。项目实现了视频平台的核心业务流程，包括用户登录、视频展示、视频播放、评论弹幕、搜索、创作者管理、后台审核和直播互动等功能。

项目使用 React 构建前端页面，使用 FastAPI 构建后端接口，使用 PostgreSQL 保存数据，并通过 Docker Compose 实现一键部署。通过数据库初始化脚本和本地视频资源目录，项目可以在其他电脑上快速复现相同的运行环境和初始数据。

本项目适合作为软件工程基础课程的大作业项目，能够体现前后端分离、数据库设计、权限控制、接口设计、容器化部署和系统集成等软件工程实践内容。