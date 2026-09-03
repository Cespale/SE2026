import json
from pathlib import Path

import pytest

from scripts.check_microservices_workspace import check_workspace

# The guard is path-agnostic, so the tests build throwaway workspaces and never
# depend on machine-specific source/target paths from the checked-in marker.
_SOURCE_BASELINE = "5f37c423ebad88b0bdc702ad425c4def8129af4e2fd2694f3f8304e8bfcc9902"
_README_HASH = "61ce29566ce6aaab238064cb2b2cf886b8a4b09abc4cb1996ebd15c93ba68c92"


def _write_marker(root: Path, allow_git: bool = False, allow_remote: bool = False) -> None:
    data = {
        "source_baseline_tree_sha256": _SOURCE_BASELINE,
        "source_baseline_frozen_files": {"README.md": _README_HASH},
        "allow_git": allow_git,
        "allow_remote": allow_remote,
    }
    (root / ".microservices-workspace.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_accepts_gitless_workspace(tmp_path: Path) -> None:
    _write_marker(tmp_path)
    check_workspace(tmp_path)  # no exception -> guard is delivery-agnostic


def test_rejects_git_checkout(tmp_path: Path) -> None:
    _write_marker(tmp_path)
    (tmp_path / ".git").mkdir()
    with pytest.raises(RuntimeError, match="read-only source"):
        check_workspace(tmp_path)


def test_requires_marker(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="workspace marker is missing"):
        check_workspace(tmp_path)


def test_rejects_remote_allowed_policy(tmp_path: Path) -> None:
    _write_marker(tmp_path, allow_remote=True)
    with pytest.raises(RuntimeError, match="local-only policy mismatch"):
        check_workspace(tmp_path)
