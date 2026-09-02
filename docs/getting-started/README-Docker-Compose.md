# 用 Docker Compose 启动完整 StreamHub

本方法最适合第一次运行项目。完成后可在浏览器中使用前端，并通过 API 网关访问 3 个业务微服务。

## 1. 检查 Docker

启动 Docker Desktop，等待界面显示 Engine running，然后在项目根目录执行：

```powershell
docker version
docker compose version
```

两条命令都必须成功。若无法连接 daemon，先修复 Docker Desktop，不要继续构建。

## 2. 创建本地环境变量

推荐让脚本生成随机且相互匹配的数据库密码、连接 URL、MinIO 密码和签名密钥：

```powershell
.\scripts\init-microservices-env.ps1
```

成功标志是 `MICROSERVICES_ENV=CREATED`。脚本默认不覆盖已有 `.env.microservices`；只有明确要替换时才使用 `-Force`。替换密码后，旧数据库卷可能无法再用新密码登录，因此不要随意覆盖。

也可以从模板手工创建：

```powershell
Copy-Item .env.microservices.example .env.microservices
notepad .env.microservices
```

手工修改时，3 个 `*_SERVICE_DB_PASSWORD` 必须分别与对应 `*_DATABASE_URL` 中冒号后的密码一致。所有 `replace-...` 占位符都必须替换。`.env.microservices` 只用于本机，不要提交或发送给别人。

## 3. 构建并启动

```powershell
docker compose -f docker-compose.microservices.yml --env-file .env.microservices up -d --build --wait --wait-timeout 240
```

首次构建通常较慢。命令返回成功后检查状态：

```powershell
docker compose -f docker-compose.microservices.yml --env-file .env.microservices ps
```

`postgres-ms`、`minio-ms`、`user-service`、`content-service`、`social-service`、`gateway`、`frontend-ms` 和 `srs-ms` 应为 `Up`，带健康检查的容器应显示 `healthy`。

## 4. 验证并打开系统

```powershell
Invoke-RestMethod http://127.0.0.1:8100/health
Invoke-RestMethod http://127.0.0.1:8100/ready
Invoke-RestMethod http://127.0.0.1:8100/version
Start-Process http://127.0.0.1:5273
```

常用地址：

| 地址 | 用途 |
|---|---|
| `http://127.0.0.1:5273` | StreamHub 前端 |
| `http://127.0.0.1:8100/health` | API 网关存活检查 |
| `http://127.0.0.1:8100/ready` | API 网关就绪检查 |
| `http://127.0.0.1:9101` | MinIO 管理界面 |

演示账号为 `user/user123`、`creator/creator123`、`admin/admin123`。这些只适用于本地课程环境。

## 5. 查看日志

```powershell
docker compose -f docker-compose.microservices.yml --env-file .env.microservices logs --tail 100 gateway user-service content-service social-service
```

持续跟踪时在命令末尾加 `-f`，按 `Ctrl+C` 只停止日志跟踪，不会停止容器。

## 6. 安全停止和再次启动

停止并移除容器、保留数据库和对象存储数据：

```powershell
docker compose -f docker-compose.microservices.yml --env-file .env.microservices down
```

再次启动：

```powershell
docker compose -f docker-compose.microservices.yml --env-file .env.microservices up -d --wait --wait-timeout 240
```

不要使用 `down -v`，除非明确要删除 PostgreSQL 和 MinIO 的全部本地数据。启动失败时先阅读 [README-Testing-Troubleshooting.md](README-Testing-Troubleshooting.md)。
