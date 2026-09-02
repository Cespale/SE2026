# Deliverable: 云原生实验

- 正式报告：`docs/microservices/cloud-native-experiments.md`
- HPA：`k8s/microservices/user-service-hpa.yaml`
- 本地集群：`scripts/setup-kind-lab.ps1`
- 自动实验：`scripts/run-cloud-native-experiments.ps1`
- 压测器：`scripts/cloud_native_load.py`
- 主证据：`docs/microservices/evidence/cloud-native/20260831-103639880/`
- 过载对照：`docs/microservices/evidence/cloud-native/20260831-103047581-overload/`

主结果：并发 4，Pod 1→4→1；244/244 成功，2.013 req/s，平均 1975.251 ms，P95 3802.347 ms，错误率 0%。故障实验返回设计的 503，user/social 均为 200。
