import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_SOURCE = Path(r"C:\Users\lausu\Desktop\SE2026")
DEFAULT_COPY = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".venv-ms",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    "test-results",
    "work",
    "reports",
    ".ci-results",
    "minio-data",
}
INCLUDED_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}
MEDIA_SUFFIXES = {
    ".avi",
    ".gif",
    ".jpeg",
    ".jpg",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".png",
    ".wav",
    ".webm",
    ".webp",
    ".zip",
}
GENERATED_PATHS = {
    "docs/microservices/version-manifest.json",
    "docs/microservices/monolith-vs-microservices.md",
}


def included(relative: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    posix = relative.as_posix()
    if posix in GENERATED_PATHS:
        return False
    name = relative.name
    if name.startswith(".env") and not name.endswith(".example"):
        return False
    if relative.suffix.lower() in MEDIA_SUFFIXES:
        return False
    return relative.suffix.lower() in INCLUDED_SUFFIXES or name in {
        "Dockerfile",
        "Dockerfile.frontend",
        ".dockerignore",
        ".gitignore",
    }


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inventory(root: Path) -> dict[str, str]:
    result = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if included(relative):
            result[relative.as_posix()] = file_hash(path)
    return result


def tree_hash(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path, value in sorted(files.items()):
        digest.update(f"{path}\0{value}\n".encode())
    return digest.hexdigest()


def reconstruct_baseline(
    source: Path,
    copy: Path,
    baseline_tree_sha256: str,
    frozen_files: dict[str, str],
) -> tuple[dict[str, str], dict]:
    current = inventory(source)
    current_tree = tree_hash(current)
    observation = {
        "current_tree_sha256": current_tree,
        "baseline_tree_sha256": baseline_tree_sha256,
        "drifted_frozen_files": [],
    }
    if current_tree == baseline_tree_sha256:
        return current, observation

    reconstructed = dict(current)
    for relative, expected_hash in sorted(frozen_files.items()):
        if current.get(relative) != expected_hash:
            observation["drifted_frozen_files"].append(relative)
        frozen_copy = copy / relative
        if not frozen_copy.is_file() or file_hash(frozen_copy) != expected_hash:
            raise RuntimeError(f"frozen baseline copy mismatch: {relative}")
        reconstructed[relative] = expected_hash

    if tree_hash(reconstructed) != baseline_tree_sha256:
        raise RuntimeError("unaccounted source drift outside frozen baseline files")
    return reconstructed, observation


def summarize(before: dict[str, str], after: dict[str, str]):
    before_paths = set(before)
    after_paths = set(after)
    common = before_paths & after_paths
    return {
        "added": sorted(after_paths - before_paths),
        "removed": sorted(before_paths - after_paths),
        "modified": sorted(path for path in common if before[path] != after[path]),
        "unchanged": sorted(path for path in common if before[path] == after[path]),
    }


def render_markdown(manifest: dict) -> str:
    diff = manifest["diff"]
    observation = manifest["source_observation"]
    lines = [
        "# StreamHub 单体版与微服务版代码证据",
        "",
        "## 两个本地版本",
        "",
        f"- 改造前（复制时冻结基线）：`{manifest['before']['root']}`",
        f"- 改造后（工作副本）：`{manifest['after']['root']}`",
        "- 本工作流只写副本、未提交、未推送；副本没有新增 Git 元数据。",
        "",
        "## 哈希摘要",
        "",
        f"- 改造前树 SHA-256：`{manifest['before']['tree_sha256']}`",
        f"- 改造后树 SHA-256：`{manifest['after']['tree_sha256']}`",
        f"- 当前源目录观察值：`{observation['current_tree_sha256']}`。",
        f"- 纳入哈希：前 {manifest['before']['file_count']} 个文件，后 {manifest['after']['file_count']} 个文件。",
        f"- 差异：新增 {len(diff['added'])}，修改 {len(diff['modified'])}，删除 {len(diff['removed'])}，未变 {len(diff['unchanged'])}。",
        "",
        "哈希排除了 Git、依赖、虚拟环境、缓存、`.env`、媒体二进制、数据库/MinIO 数据和测试产物，避免把密钥或大文件当作代码证据。完整逐文件结果见 `version-manifest.json`。该哈希是本地证据，不等同于 Git commit。",
        "",
        "源目录的 `README.md` 在复制后被其他进程改写；其当前哈希与冻结值不同。清单使用副本中经 SHA-256 验证的复制时 README 重建基线，且重建树哈希精确等于原基线；源目录未被回滚。",
        "",
        "## 结构差异",
        "",
        "| 改造前 | 改造后 |",
        "|---|---|",
        "| 一个 `backend/app/main.py` 承担全部业务 | user/content/social 三个独立 FastAPI 应用 |",
        "| 一个数据库账号直接访问单体表 | 三个受限账号、三个 Schema、禁止跨服务联表 |",
        "| 公开端口直接进入单体 8000 | Gateway 8100 按业务路由，服务端口不公开 |",
        "| 跨模块调用是进程内 ORM/函数 | 内部 HTTP；跨服务写使用 Outbox + 幂等接收 |",
        "| 单体 Dockerfile/Deployment | 三个 Dockerfile、三个 Deployment、独立探针/资源 |",
        "| 无收藏明细和历史计数残差边界 | 新增 favorites 与 interaction baseline，防止历史计数回退 |",
        "",
        "性能快慢不能从架构或哈希推断。三接口已按同机、同数据、同脚本各实测 3 次；本机结果中微服务吞吐均未提升，且内存成本更高。完整条件、全部轮次和原始结果见 `performance-comparison.md`。",
        "",
        "## 新增文件样例",
        "",
    ]
    lines.extend(f"- `{path}`" for path in diff["added"][:40])
    if len(diff["added"]) > 40:
        lines.append(f"- ……其余 {len(diff['added']) - 40} 项见 JSON")
    lines.extend(["", "## 修改文件", ""])
    lines.extend(f"- `{path}`" for path in diff["modified"][:40])
    if not diff["modified"]:
        lines.append("- 无")
    if len(diff["modified"]) > 40:
        lines.append(f"- ……其余 {len(diff['modified']) - 40} 项见 JSON")
    lines.extend(["", "## 删除文件", ""])
    lines.extend(f"- `{path}`" for path in diff["removed"][:40])
    if not diff["removed"]:
        lines.append("- 无；单体代码保留为改造前参考。")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--copy", type=Path, default=DEFAULT_COPY)
    args = parser.parse_args()
    source = args.source.resolve()
    copy = args.copy.resolve()
    if not source.is_dir() or not copy.is_dir():
        raise RuntimeError("source and copy directories must exist")
    if source == copy or copy.is_relative_to(source):
        raise RuntimeError("copy must be separate from read-only source")
    marker = copy / ".microservices-workspace.json"
    if not marker.is_file():
        raise RuntimeError("copy workspace marker is missing")

    marker_data = json.loads(marker.read_text(encoding="utf-8"))
    before, source_observation = reconstruct_baseline(
        source,
        copy,
        marker_data["source_baseline_tree_sha256"],
        marker_data["source_baseline_frozen_files"],
    )
    after = inventory(copy)
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "algorithm": "sha256",
        "exclusions": sorted(EXCLUDED_DIRS),
        "source_observation": source_observation,
        "before": {
            "root": str(source),
            "file_count": len(before),
            "tree_sha256": tree_hash(before),
            "files": before,
        },
        "after": {
            "root": str(copy),
            "file_count": len(after),
            "tree_sha256": tree_hash(after),
            "files": after,
        },
        "diff": summarize(before, after),
    }
    output_dir = copy / "docs" / "microservices"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "version-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "monolith-vs-microservices.md").write_text(
        render_markdown(manifest), encoding="utf-8"
    )
    print(
        "VERSION_MANIFEST=PASS "
        f"before={len(before)} after={len(after)} "
        f"added={len(manifest['diff']['added'])} "
        f"modified={len(manifest['diff']['modified'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
