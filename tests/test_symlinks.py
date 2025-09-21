import os
import subprocess
from devtools.flatpack import compile_gitwild_patterns, collect_entries

def run(cmd, cwd):
    subprocess.check_call(cmd, cwd=cwd)

def test_symlink_included_when_points_to_file(tmp_path):
    # Make this directory a Git repo
    run(["git", "init"], cwd=tmp_path)

    (tmp_path / "real.txt").write_text("data")
    os.symlink((tmp_path / "real.txt"), (tmp_path / "link.txt"))

    pats = compile_gitwild_patterns([])
    entries, *_ = collect_entries(str(tmp_path), include_untracked=True, pats=pats)
    paths = {e["path"] for e in entries}

    # Both should appear: the real file and the symlink
    assert "real.txt" in paths
    assert "link.txt" in paths