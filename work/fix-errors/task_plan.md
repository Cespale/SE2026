# Task Plan: 修复深度测试暴露的问题

## Goal
在不破坏现有通过链路和用户数据的前提下，修复故障实验恢复验收、HPA 现场命令、单体副本启动冲突、环境初始化、安全依赖及可安全处理的弃用问题，并留下可复现验证证据。

## Phases
- [x] Phase 1: 阅读交接与错题本，盘点现有实现和约束
- [x] Phase 2: 建立失败测试并确认根因
- [x] Phase 3: 逐项实施最小修复
- [x] Phase 4: 运行针对性测试、完整回归和运行态验证
- [x] Phase 5: 汇总结果与剩余风险

## Key Questions
1. 云原生实验是否在恢复完成前就宣告 PASS？
2. 哪些 README/脚本仍包含无效的 HPA 观察命令？
3. 单体 Compose 如何在复制目录中独立启动且不泄漏空密钥？
4. npm 漏洞能否通过兼容升级消除？

## Decisions Made
- 所有修复先有可观察的失败验证，再修改生产文件。
- 不删除容器、数据卷或用户证据；使用静态配置验证和隔离测试项目。

## Errors Encountered
- 升级 webpack-dev-server 6 后，旧对象式 `proxy` 配置被拒绝；已按新版数组格式改为 `pathFilter`，实启验证转发成功。
- webpack-dev-server 6 在 Windows 上处理旧的额外 glob `watchFiles` 时抛出路径参数错误；该配置与 Webpack 自身源码监听重复，移除后实启并成功编译。
- 一次只读 HTTP 探测误用了 PowerShell 保留变量 `$home`，命令立即失败且没有修改状态；随后改用任务专用变量重跑成功。

## Status
**Complete** - 修复、完整回归、两版运行态验证、双 PowerShell 云原生复跑和证据归档均已完成。
