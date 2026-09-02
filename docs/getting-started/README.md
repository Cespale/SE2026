# StreamHub 本地运行入口

这组文档面向完全不了解本项目、只拿到一份代码、希望在 Windows 电脑上把系统跑起来的人。命令默认在 PowerShell 中执行，项目目录记为 `C:\Users\你的用户名\Desktop\SE2026-microservices`。

## 先选目标

| 目标 | 阅读文档 | 最终看到什么 |
|---|---|---|
| 从 clone 到课程四项完整验收 | [../../TESTING.md](../../TESTING.md) | 按固定顺序跑完全部测试，并知道每一步的正确结果和证据位置 |
| 最快打开完整网页 | [README-Docker-Compose.md](README-Docker-Compose.md) | 浏览器打开 StreamHub，前端、网关、3 个业务服务和基础设施全部运行 |
| 演示 Docker、Kubernetes、Kind 和 CI/CD | [README-Kind-CICD.md](README-Kind-CICD.md) | 自动测试、构建镜像、部署到 Kind，并验证健康、就绪和版本 |
| 跑测试或处理启动失败 | [README-Testing-Troubleshooting.md](README-Testing-Troubleshooting.md) | 找到失败阶段、日志和诊断证据 |

第一次接触项目，建议先完成 Docker Compose 文档；确认网页可用后，再做 Kind CI/CD。

## 共同前提

- Windows 10/11 和 PowerShell 5.1 或更高版本。
- Docker Desktop 已启动，并使用 Linux containers。
- 项目放在本机可写目录，不要直接修改原始备份 `SE2026`。
- 首次构建需要联网下载基础镜像和依赖。
- Kind 路线还需要 Python、Node.js、Git Bash 和 `kubectl`，详细版本见对应文档。

先打开 PowerShell，进入项目根目录：

```powershell
Set-Location 'C:\Users\你的用户名\Desktop\SE2026-microservices'
```

后续所有命令都从这个目录执行。路径不同只需替换这一行，不要修改脚本里的业务配置。

## 两条路线的区别

- Docker Compose 路线包含可访问的前端，适合日常开发和功能展示。
- Kind CI/CD 路线重点验证后端微服务部署，默认不部署前端和 SRS，以减少课堂实验的资源占用；看网页仍使用 Compose 路线。
- 两条路线可以共用本地 Docker 镜像，但不要同时占用相同端口。

## 数据安全

普通停止命令不会删除数据库卷。任何带 `-v` 的 Compose 删除命令，以及 `kind delete cluster`，都会删除相应环境中的本地数据；执行前必须明确确认不再需要这些数据。
