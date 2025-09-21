import subprocess, pytest
from devtools.flatpack import git_ls_tracked

def test_git_ls_tracked_crash_is_exit(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise subprocess.CalledProcessError(2, "git")
    monkeypatch.setattr(subprocess, "check_output", boom)
    with pytest.raises(SystemExit):
        git_ls_tracked(str(tmp_path))