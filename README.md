# StreamHub 在线视频与直播网站

## 系统使用说明

### 步骤 1：本地把系统跑起来

```bash
# 首次克隆后：复制环境变量模板（.env 已被 gitignore，不会提交）
cp .env.example .env        # Windows 命令行用：copy .env.example .env

# 编辑 .env，把 CHANGE_ME 换成你自己的值（本地我建好了一份，可直接用）
# POSTGRES_PASSWORD=123456
# SECRET_KEY=随便一串字符

# 启动三容器
docker compose up -d --build

# 看日志确认都起来了
docker compose ps
```

启动后访问：
- 前端：http://localhost:5173
- 后端：http://localhost:8000/docs （FastAPI 自动文档）

### 步骤 2：给 GitHub 仓库配 Secrets（CI 部署阶段要用）

1. 打开 `https://github.com/Bolic137/SE2026/settings/secrets/actions`
2. 点 **New repository secret**，加两个：
   - `POSTGRES_PASSWORD` → 比如 `123456`
   - `SECRET_KEY` → 随便一串字符

> 不配这两个，流水线部署阶段会报「需要设置 POSTGRES_PASSWORD/SECRET_KEY」。

### 步骤 3：提交代码、推上去触发流水线

```bash
git add .
git commit -m "P5: 清理硬编码密钥 + 添加 CI/CD 流水线 + K8s 部署清单"
git push origin main
```

推到 main 后，打开仓库 **Actions** 标签页，就能看到流水线跑起来。三个 job 全绿 = 通过。

### 步骤 4（可选）：本机验证 K8s 部署

需要有 Docker Desktop + kubectl + Kind（或 minikube），装好后：

```bash
# 起一个本地 K8s 集群
kind create cluster

# 打镜像（带版本号）
docker build -f backend/Dockerfile -t streamhub-backend:test .
docker build -f Dockerfile.frontend -t streamhub-frontend:test .

# 把镜像塞进集群
kind load docker-image streamhub-backend:test
kind load docker-image streamhub-frontend:test

# 部署（脚本会自动读 .env 里的密钥）
export VERSION=test
bash scripts/deploy.sh

# 健康检查
bash scripts/health-check.sh
```

看到 `全部健康检查通过` 就说明部署成功了。前端可以通过 NodePort 访问：http://localhost:30000
