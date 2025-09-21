import pytest
from devtools.flatpack import validate_repo_root

def test_validate_repo_root_fails_outside_repo(tmp_path, monkeypatch):
    # Make sure git does NOT discover a repository by walking upward:
    # 1) Tell git to use a non-existent explicit repo dir.
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "_no_such_git_dir"))
    # 2) Also set a ceiling so discovery won't pass this directory.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))

    with pytest.raises(SystemExit):
        validate_repo_root(str(tmp_path))