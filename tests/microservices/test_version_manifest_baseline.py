import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "hash-version-manifest.py"


def load_module():
    spec = importlib.util.spec_from_file_location("hash_version_manifest", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_frozen_file_reconstructs_copy_time_source_baseline(tmp_path):
    module = load_module()
    source = tmp_path / "source"
    copy = tmp_path / "copy"
    source.mkdir()
    copy.mkdir()
    (source / "README.md").write_text("copy-time\n", encoding="utf-8")
    (copy / "README.md").write_text("copy-time\n", encoding="utf-8")
    baseline = module.inventory(source)
    baseline_tree = module.tree_hash(baseline)
    frozen_hash = baseline["README.md"]

    (source / "README.md").write_text("changed later\n", encoding="utf-8")
    reconstructed, observation = module.reconstruct_baseline(
        source,
        copy,
        baseline_tree,
        {"README.md": frozen_hash},
    )

    assert module.tree_hash(reconstructed) == baseline_tree
    assert observation["current_tree_sha256"] != baseline_tree
    assert observation["drifted_frozen_files"] == ["README.md"]


def test_baseline_reconstruction_rejects_unaccounted_source_change(tmp_path):
    module = load_module()
    source = tmp_path / "source"
    copy = tmp_path / "copy"
    source.mkdir()
    copy.mkdir()
    (source / "README.md").write_text("copy-time\n", encoding="utf-8")
    (copy / "README.md").write_text("copy-time\n", encoding="utf-8")
    baseline = module.inventory(source)
    baseline_tree = module.tree_hash(baseline)
    frozen_hash = baseline["README.md"]

    (source / "README.md").write_text("changed later\n", encoding="utf-8")
    (source / "unexpected.md").write_text("new\n", encoding="utf-8")

    try:
        module.reconstruct_baseline(
            source,
            copy,
            baseline_tree,
            {"README.md": frozen_hash},
        )
    except RuntimeError as error:
        assert "unaccounted source drift" in str(error)
    else:
        raise AssertionError("unaccounted source drift must fail closed")
