import json
from pathlib import Path

import pytest

from scripts.check_microservices_workspace import check_workspace

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_accepts_copy_and_rejects_source() -> None:
    # Derive paths from the workspace marker (single source of truth) so the
    # test stays valid when the workspace is moved to another machine/path.
    marker = json.loads(
        (_PROJECT_ROOT / ".microservices-workspace.json").read_text(encoding="utf-8")
    )
    copy_root = Path(marker["target"])
    source_root = Path(marker["source"])

    check_workspace(copy_root)

    with pytest.raises(RuntimeError, match="read-only source"):
        check_workspace(source_root)
