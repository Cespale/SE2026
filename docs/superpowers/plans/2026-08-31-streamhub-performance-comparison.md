# StreamHub 性能对比实施计划

1. 先写失败契约：隔离 Compose、三接口、三轮、顺序运行、受控资源和原始证据字段。
2. 实现 `performance_load.py`：统一 HTTP 负载、P95、状态码、Docker CPU/内存采样和 JSON/CSV。
3. 实现 `docker-compose.performance.yml`：独立端口、tmpfs 数据、相同活动业务 CPU 限制。
4. 实现 `run-performance-comparison.ps1`：初始化/迁移/校验数据，交替启动版本，执行 18 个测量，聚合结果，失败留证并安全停止。
5. 运行脚本契约和本地模拟负载测试；修复到全绿。
6. 构建并启动真实隔离栈；核对两版接口成功与数据摘要一致。
7. 实跑 3 接口 × 2 版本 × 3 轮，保留所有 JSON/CSV/日志。
8. 聚合中位数/范围，写正式报告；解释 Gateway、内部 HTTP、进程基线和 bcrypt 的影响。
9. 全量回归、刷新验证报告和版本哈希。禁止删除现有数据卷或宣称未实测的提升。
