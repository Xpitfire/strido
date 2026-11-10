"""Repository discovery for the tooling."""

import pytest

from strido import workspace


def test_override_must_point_at_a_checkout(tmp_path, monkeypatch):
    workspace.repo_root.cache_clear()
    monkeypatch.setenv("STRIDO_REPO_ROOT", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="does not contain"):
        workspace.repo_root()
    (tmp_path / "hardware").mkdir()
    (tmp_path / "hardware/kinematics.yaml").write_text("{}")
    workspace.repo_root.cache_clear()
    assert workspace.repo_root() == tmp_path.resolve()
    assert workspace.build_dir("x").is_dir()
    workspace.repo_root.cache_clear()
