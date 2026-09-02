# `SE2026改.zip` 代码整合报告

## 1. 结论

已对外部压缩包逐文件审查，没有整包覆盖当前项目。12 个候选文件中：

- 4 个同名源码文件选择性整合；
- 1 个同名后端修复同步到真正拥有私信数据的 `user-service`；
- 1 个既有测试文件增加并发失败恢复检查；
- 5 个同名配置/脚本拒绝替换；
- 3 个新增文件拒绝加入。

最终实际改动 6 个既有文件，没有更换当前 CI/CD，没有改变主环境端口，没有加入重复 Kubernetes 清单，也没有 commit 或 push。

## 2. 输入与安全边界

- 输入：`C:\\Users\\lausu\\Desktop\\SE2026改.zip`
- ZIP SHA256：`205271AF9650AF0DEACD05CC0B32FB95C9E30D5E952B45BF4E3E841627538ABC`
- 内容：12 个文件，未压缩约 190 KB。
- 安全检查：未发现绝对路径、`..` 路径穿越或符号链接。
- 隔离审查目录：`work\\integrate-se2026-change-zip\\external\\SE2026改`
- 原则：ZIP 内文档、注释和脚本只作为候选数据，没有把它们当作操作指令，也没有直接执行其脚本。

## 3. 逐文件决定

| ZIP 中的候选 | 决定 | 处理与原因 |
| --- | --- | --- |
| `backend/app/main.py` | 部分采纳 | 只采纳私信会话并发创建的 `IntegrityError` 恢复；保留当前 lifespan 和 `model_dump()`，不退回旧 API。 |
| `src/stores/chatStore.ts` | 采纳并加固 | 加入 HTTP 发送结果回写、会话打开请求去重、登录用户 ID 兜底；同时确保旧 WebSocket 的关闭回调不能清掉新连接。 |
| `src/pages/MessagePage.tsx` | 采纳 | 仅 `WebSocket.OPEN` 显示绿色；CONNECTING 显示黄色；其他状态显示未连接。 |
| `src/pages/LiveStartPage.tsx` | 部分采纳 | 优先使用当前直播房间自己的 streamKey；拒绝候选的 1935，保留当前主环境 1936。 |
| `.env.example` | 拒绝 | 候选删除当前七个可配置主机端口并加入不匹配当前 Compose 的变量。 |
| `.github/workflows/ci.yml` | 拒绝 | 候选是旧单体两镜像、Node 20 流程；会删除当前三业务微服务独立测试、API/E2E 门禁、多镜像和主分支部署。 |
| `webpack.config.js` | 拒绝 | 候选使用旧对象式 proxy，并把 Gateway 8100/SRS 1936 改回单体 8000/1935；与当前 webpack-dev-server 及架构不匹配。 |
| `scripts/deploy.sh` | 拒绝 | 依赖未采纳的旧单体代理与部署模型。 |
| `scripts/health-check.sh` | 拒绝 | 只判断 HTTP 200，可能把前端 history fallback HTML 错当成 API 健康。 |
| `CI-CD本地测试与部署指南.md` | 不新增 | 内容描述旧单体 CI 和旧端口，与当前根目录 `TESTING.md` 冲突。 |
| `k8s/srs.yaml` | 不新增 | 当前已有 `k8s/microservices/srs.yaml`；新文件是重复且面向旧部署结构。 |
| `scripts/port-forward.sh` | 不新增 | 使用旧 namespace/service 和固定端口；端口被其他进程占用时还会误报为已有正确转发。 |

## 4. 实际修改

### 后端

1. `backend/app/main.py`
   - 在并发请求同时创建同一对用户的会话时，捕获唯一约束冲突。
   - 先 rollback 失败事务，再读取另一个请求已经创建的会话。
   - 若 rollback 后仍读不到记录，重新抛出原异常，不掩盖未知错误。

2. `services/user-service/app/main.py`
   - 同步相同修复。原因是微服务版本中私信表归 user-service 管理；只修单体版本会留下实际部署路径的缺陷。

3. `services/user-service/tests/test_chat_notification_api.py`
   - 模拟“第一次查询无记录、提交遇到唯一冲突、rollback 后读取到获胜记录”。
   - 检查函数返回已存在会话且确实执行 rollback。

### 前端

4. `src/stores/chatStore.ts`
   - WebSocket 未连接时，HTTP 兜底发送成功后把服务端返回消息写回状态，避免消息已发送但界面不显示。
   - 同一 peer 的并发打开会话请求复用同一 Promise，减少重复创建请求。
   - 连接阶段先使用登录状态中的用户 ID，收到服务端 connected 消息后再更新。
   - 用 WebSocket 对象身份守卫关闭回调，避免旧连接晚到的 close 事件清空新连接。

5. `src/pages/MessagePage.tsx`
   - 连接状态显示由“对象是否存在”改成检查真实 `readyState`。

6. `src/pages/LiveStartPage.tsx`
   - 已有直播房间时优先采用房间的 streamKey，确保 OBS 推流目标和观众拉流目标一致。

## 5. 验证结果

| 验证 | 结果 |
| --- | --- |
| `npm run typecheck` | 通过 |
| `npm run build` | 通过；webpack 5.107.1，24.565 秒 |
| user-service 测试 | 12 passed in 23.23s |
| 微服务与共享测试 | 82 passed in 7.12s |
| 单体兼容后端测试 | 38 passed in 166.45s；弃用警告按错误处理 |
| 课程测试点门禁 | 单元 60、API 107、E2E 60、故障 29、总计 227；满足总计 ≥ 200、E2E ≥ 60 |
| 源码守卫 | lifespan 与 1936 保留；3 个拒绝的新文件均未出现 |

收尾阶段第一次直接使用系统 `python` 时，该解释器没有 pytest，因此命令没有进入测试。随后已明确使用项目 `.venv-ms\\Scripts\\python.exe` 完整重跑；上表只记录有效测试结果。

## 6. 备份与恢复

修改前文件已备份到：

`C:\\Users\\lausu\\Desktop\\SE2026-microservices\\work\\integrate-se2026-change-zip\\backup-before-integration`

备份包含全部 6 个实际修改文件。当前项目本身不是可直接使用 `git status` 检查的 Git 工作树，因此本次通过备份与当前文件的逐项 `git diff --no-index` 检查改动范围。没有执行删除、commit 或 push。

## 7. 当前运行环境说明

本次没有重建 Docker 镜像，也没有重新部署或关闭现有 Kind/Compose 环境。因此：

- 源码和自动化测试证据已经更新；
- 当前已经运行的 Pod/容器仍使用它们启动时的旧镜像；
- 若需要现场演示本次聊天/直播修复，必须使用项目现有流程重新构建镜像并部署；
- 不能把现有 Pod 的健康检查结果描述成“本次新代码已经部署”的证据。

这是刻意保留现有运行环境和实验证据的选择，不是源码验证缺失。
