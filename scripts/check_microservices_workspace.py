import json
from pathlib import Path


def check_workspace(root: Path) -> None:
    # The gate runs on a git-less workspace copy of the project. No absolute
    # machine path is pinned: any folder is accepted as long as it carries a
    # valid marker, so the same copy works under any folder name/machine.
    resolved = root.resolve()

    if (resolved / ".git").exists():
        raise RuntimeError(
            "read-only source (git checkout): remove or move the .git folder "
            "to run the gate in this copy (see README)"
        )

    marker = resolved / ".microservices-workspace.json"
    if not marker.is_file():
        raise RuntimeError(f"workspace marker is missing: {marker}")
    data = json.loads(marker.read_text(encoding="utf-8"))

    if len(data.get("source_baseline_tree_sha256", "")) != 64:
        raise RuntimeError("copy-time source baseline is missing")
    if not data.get("source_baseline_frozen_files"):
        raise RuntimeError("frozen source baseline files are missing")
    if data.get("allow_git") or data.get("allow_remote"):
        raise RuntimeError("local-only policy mismatch")


if __name__ == "__main__":
    check_workspace(Path.cwd())
    print("WORKSPACE_GUARD=PASS")
