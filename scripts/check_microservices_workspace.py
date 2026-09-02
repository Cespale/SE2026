import json
from pathlib import Path


def check_workspace(root: Path) -> None:
    resolved = root.resolve()
    source = Path(r"C:\Users\14537\SE2026").resolve()
    target = Path(r"C:\Users\14537\SE2026-microservices").resolve()

    if resolved == source:
        raise RuntimeError("read-only source")
    if resolved != target:
        raise RuntimeError(f"unexpected workspace: {resolved}")

    marker = resolved / ".microservices-workspace.json"
    data = json.loads(marker.read_text(encoding="utf-8"))

    if Path(data["target"]).resolve() != target:
        raise RuntimeError("workspace marker target mismatch")
    if len(data.get("source_baseline_tree_sha256", "")) != 64:
        raise RuntimeError("copy-time source baseline is missing")
    if not data.get("source_baseline_frozen_files"):
        raise RuntimeError("frozen source baseline files are missing")
    if data["allow_git"] or data["allow_remote"]:
        raise RuntimeError("local-only policy mismatch")
    if (resolved / ".git").exists():
        raise RuntimeError("Git metadata is forbidden in the copy")


if __name__ == "__main__":
    check_workspace(Path.cwd())
    print("WORKSPACE_GUARD=PASS")
