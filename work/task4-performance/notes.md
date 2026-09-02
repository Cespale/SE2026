# Notes: 单体与微服务性能对比

## Audit facts

- Existing 8000/8100 stacks have different persistent data and cannot be compared directly.
- The backup SQL contains 3 users, 10 categories and a fixed video set. `migrate_monolith_data.py` copies rows from `public` to service-owned schemas without modifying source rows.
- Comparable read-only/business interfaces: categories, latest video list, login. Video detail mutates view count and is rejected as a benchmark target.
- Monolith and services all run one Uvicorn process. Benchmark will give the active business process and monolith the same 0.5 CPU/512 MiB limit.
- Isolated Compose can use tmpfs and unique ports, so no existing volume needs deletion.

## Confidence check

- Requirements and control variables: 96%.
- Existing migration/data path: 94%.
- Test strategy: 93%.
- Docker stats/first startup integration: 86%.
- Overall: 92%; proceed, with integration as an explicit fail-fast gate.

## Integration smoke

- Evidence: `.ci-results/performance/20260831-111538534`.
- Three short rounds completed all 18 measurements with zero HTTP errors.
- Dataset equality gate passed: users 3/3, categories 10/10, videos 18/18; source/target content digests match.
- Compose switching, raw JSON/CSV, Docker stats, aggregation and safe stop all passed.
- Smoke durations/samples are intentionally too short for the final performance conclusion.

## Formal runs

- Main evidence: `.ci-results/performance/20260831-114658527`, read concurrency 4; all 18 measurements zero errors.
- Overload evidence: `.ci-results/performance/20260831-113157084`, read concurrency 16; microservice video list 100% 503 in all 3 runs.
- Main mean throughput monolith→micro: categories 68.118→48.370; videos 18.579→12.288; login 0.933→0.904 req/s.
- Main mean app memory monolith→micro: about 86.6–87.4 MiB → 249.7–252.8 MiB.
- No performance improvement claim is supported.
