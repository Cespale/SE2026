# StreamHub 单体/微服务性能对比设计

## 前提审计

课程要求不是“证明微服务更快”，而是控制变量后实测。现有日常单体和微服务 Compose 使用不同持久卷、端口和数据状态，直接比较会违反“同一批数据”；两套同时压测也会互相争抢 CPU。因此不复用日常容器或业务卷。

## 方案比较

1. **隔离基准 Compose（采用）**：新项目 `streamhub-perf`，同一 PostgreSQL 内保留单体 `public` 表和微服务三个 Schema；顺序启动两版应用。数据、机器和脚本可控，且不改现有业务卷。
2. 直接压现有 8000/8100：代码最少，但数据量、热缓存和后台活动不同，结论无效。
3. 单元级 TestClient 基准：稳定但绕过 Docker、Nginx、网络和真实 PostgreSQL，不符合系统性能对比。

## 接口

- `GET /api/categories`：轻量只读；单体直达应用，微服务经过 Gateway→content。
- `GET /api/videos?sort=latest&page=1&page_size=20`：主要列表；微服务还会调用 user-service 批量补充上传者，能体现跨服务成本。
- `POST /api/auth/login`：主要认证路径；两版都执行同一份 bcrypt 哈希校验，微服务额外经过 Gateway。

不选择视频详情：该接口会递增播放量，每轮数据状态不同。也不选择点赞/评论：写操作需要每轮可靠回滚，否则不再是同一数据。

## 控制变量

- 同一 Windows/Docker Desktop 主机、同一时间段、相同镜像基础环境。
- 单体和微服务顺序运行；同一时刻只压一个版本。
- 同一 PostgreSQL 容器；`public` 数据只读迁移到三个服务 Schema，并比较行数与内容摘要。
- 每个应用进程 CPU 上限 0.5 核、内存 512 MiB；Gateway 0.25 核/128 MiB。活动业务服务与单体拥有相同 0.5 核上限；微服务额外进程成本如实计入总内存。
- 同一 Python 压测器、请求体、并发、持续时间、超时和预热。
- 每个接口、每个版本 3 轮；轮次交替顺序，降低先后和热缓存偏差。
- 读取请求：并发 16、20 秒、预热 5 秒。登录：并发 4、30 秒、预热 5 秒。
- 记录吞吐量、平均/P95、错误率；每轮用 `docker stats` 保存逐容器 CPU/内存原始采样并聚合应用总量。

## 环境和生命周期

- `docker-compose.performance.yml` 只创建 `streamhub-perf-*` 容器；数据库/MinIO 使用容器 tmpfs，不创建或删除用户数据卷。
- 初始化顺序：Postgres/MinIO → 单体备份 SQL → 服务角色/Schema/表 → `migrate_monolith_data.py` → 数据摘要校验。
- 测量顺序：R1 monolith→microservices；R2 microservices→monolith；R3 monolith→microservices。
- 失败时保留该运行的日志、Compose 状态、部分结果；最终停止基准容器，但不删除 Kind、日常 Compose 容器或任何命名卷。

## 结果解释边界

- 比较的是此硬件、此数据量、此并发和单实例配置，不代表生产极限。
- Docker CPU% 是采样值；报告平均与峰值并保留原始 CSV，不把它当精密能耗测量。
- 数据库和 MinIO 是共同基础设施；报告应用容器总 CPU/内存，并单独保留 PostgreSQL采样。
- 只有三轮原始结果支持时才使用“更快/更慢”；不写“性能提升”除非指标方向一致且说明代价。
