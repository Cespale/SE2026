# Deliverable: 单体与微服务性能对比

- 正式报告：`docs/microservices/performance-comparison.md`
- 隔离环境：`docker-compose.performance.yml`
- 统一压测器：`scripts/performance_load.py`
- 自动三轮调度：`scripts/run-performance-comparison.ps1`
- 主结果：`docs/microservices/evidence/performance/20260831-114658527-main/`
- 并发 16 过载对照：`docs/microservices/evidence/performance/20260831-113157084-overload/`

结论：主对比 18/18 测量 0 错误；此配置下微服务三个接口均未提升吞吐，应用总内存约为单体 2.86–2.91 倍。
