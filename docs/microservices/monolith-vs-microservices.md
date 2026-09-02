# StreamHub 单体版与微服务版代码证据

## 两个本地版本

- 改造前（复制时冻结基线）：`C:\Users\lausu\Desktop\SE2026`
- 改造后（工作副本）：`C:\Users\lausu\Desktop\SE2026-microservices`
- 本工作流只写副本、未提交、未推送；副本没有新增 Git 元数据。

## 哈希摘要

- 改造前树 SHA-256：`5f37c423ebad88b0bdc702ad425c4def8129af4e2fd2694f3f8304e8bfcc9902`
- 改造后树 SHA-256：`c48cf95aa715d0729daa31fbba130679d86e214b51bea95f025d7268c54c108c`
- 当前源目录观察值：`220c670da6a1a781e37d60568ad3b4ba5cfef18b4a4bde9e10e64746c9e5f609`。
- 纳入哈希：前 144 个文件，后 335 个文件。
- 差异：新增 192，修改 8，删除 1，未变 135。

哈希排除了 Git、依赖、虚拟环境、缓存、`.env`、媒体二进制、数据库/MinIO 数据和测试产物，避免把密钥或大文件当作代码证据。完整逐文件结果见 `version-manifest.json`。该哈希是本地证据，不等同于 Git commit。

源目录的 `README.md` 在复制后被其他进程改写；其当前哈希与冻结值不同。清单使用副本中经 SHA-256 验证的复制时 README 重建基线，且重建树哈希精确等于原基线；源目录未被回滚。

## 结构差异

| 改造前 | 改造后 |
|---|---|
| 一个 `backend/app/main.py` 承担全部业务 | user/content/social 三个独立 FastAPI 应用 |
| 一个数据库账号直接访问单体表 | 三个受限账号、三个 Schema、禁止跨服务联表 |
| 公开端口直接进入单体 8000 | Gateway 8100 按业务路由，服务端口不公开 |
| 跨模块调用是进程内 ORM/函数 | 内部 HTTP；跨服务写使用 Outbox + 幂等接收 |
| 单体 Dockerfile/Deployment | 三个 Dockerfile、三个 Deployment、独立探针/资源 |
| 无收藏明细和历史计数残差边界 | 新增 favorites 与 interaction baseline，防止历史计数回退 |

性能快慢不能从架构或哈希推断。三接口已按同机、同数据、同脚本各实测 3 次；本机结果中微服务吞吐均未提升，且内存成本更高。完整条件、全部轮次和原始结果见 `performance-comparison.md`。

## 新增文件样例

- `.microservices-workspace.json`
- `database/init/01-service-schemas.sh`
- `database/migrations/001-service-tables.sql`
- `docker-compose.microservices.yml`
- `docker-compose.performance.yml`
- `docs/getting-started/README-Docker-Compose.md`
- `docs/getting-started/README-Kind-CICD.md`
- `docs/getting-started/README-Testing-Troubleshooting.md`
- `docs/getting-started/README.md`
- `docs/microservices/ci-cd-and-operations.md`
- `docs/microservices/cloud-native-experiments.md`
- `docs/microservices/cross-service-calls.md`
- `docs/microservices/evidence/cloud-native/20260831-103047581-overload/experiment-summary.json`
- `docs/microservices/evidence/cloud-native/20260831-103047581-overload/load-results.json`
- `docs/microservices/evidence/cloud-native/20260831-103639880/events.txt`
- `docs/microservices/evidence/cloud-native/20260831-103639880/experiment-summary.json`
- `docs/microservices/evidence/cloud-native/20260831-103639880/fault-results.json`
- `docs/microservices/evidence/cloud-native/20260831-103639880/hpa-describe.txt`
- `docs/microservices/evidence/cloud-native/20260831-103639880/hpa-final.yaml`
- `docs/microservices/evidence/cloud-native/20260831-103639880/load-results.json`
- `docs/microservices/evidence/cloud-native/20260831-103639880/pods-final.txt`
- `docs/microservices/evidence/cloud-native/20260831-103639880/user-service-top.txt`
- `docs/microservices/evidence/cloud-native/20260831-153212635-powershell51/events.txt`
- `docs/microservices/evidence/cloud-native/20260831-153212635-powershell51/experiment-summary.json`
- `docs/microservices/evidence/cloud-native/20260831-153212635-powershell51/fault-results.json`
- `docs/microservices/evidence/cloud-native/20260831-153212635-powershell51/hpa-describe.txt`
- `docs/microservices/evidence/cloud-native/20260831-153212635-powershell51/hpa-final.yaml`
- `docs/microservices/evidence/cloud-native/20260831-153212635-powershell51/load-results.json`
- `docs/microservices/evidence/cloud-native/20260831-153212635-powershell51/pods-final.txt`
- `docs/microservices/evidence/cloud-native/20260831-153212635-powershell51/user-service-top.txt`
- `docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/events.txt`
- `docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/experiment-summary.json`
- `docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/fault-results.json`
- `docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/hpa-describe.txt`
- `docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/hpa-final.yaml`
- `docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/load-results.json`
- `docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/pods-final.txt`
- `docs/microservices/evidence/cloud-native/20260831-154455611-powershell51/user-service-top.txt`
- `docs/microservices/evidence/performance/20260831-113157084-overload/dataset-manifest.json`
- `docs/microservices/evidence/performance/20260831-113157084-overload/raw/microservices-categories-run1.json`
- ……其余 152 项见 JSON

## 修改文件

- `.dockerignore`
- `.github/workflows/ci.yml`
- `.gitignore`
- `e2e/streamhub.spec.ts`
- `playwright.config.ts`
- `scripts/test_ci_contract.py`
- `src/pages/LiveStartPage.tsx`
- `webpack.config.js`

## 删除文件

- `.idea/.gitignore`
