import subprocess
import shutil
import pytest

def _has_git() -> bool:
    return shutil.which("git") is not None

def run(cmd, cwd):
    subprocess.check_call(cmd, cwd=cwd)

@pytest.mark.skipif(not _has_git(), reason="git not available")
def test_submodule_gitlink(tmp_path):
    # init parent repo
    run(["git", "init"], cwd=tmp_path)
    # make parent independent of user config
    run(["git", "config", "user.name", "Flatpack Test"], cwd=tmp_path)
    run(["git", "config", "user.email", "flatpack@example.com"], cwd=tmp_path)

    # create child repo
    child = tmp_path / "child"
    child.mkdir()
    run(["git", "init"], cwd=child)
    (child / "a.txt").write_text("x")
    run(["git", "add", "a.txt"], cwd=child)
    run(["git", "-c", "commit.gpgsign=false", "commit", "--no-gpg-sign", "-m", "c"], cwd=child)

    # add as submodule (allow local file transport explicitly)
    run(["git", "-c", "protocol.file.allow=always", "submodule", "add", str(child), "sub"], cwd=tmp_path)

    # Ensure gitlink shows up in tracked listing (not untracked)
    from devtools.flatpack import collect_entries, compile_gitwild_patterns
    pats = compile_gitwild_patterns([])
    entries, tracked_count, untracked_count = collect_entries(str(tmp_path), include_untracked=True, pats=pats)

    paths = {e["path"]: e for e in entries}
    # The submodule directory shouldn't be treated as a normal file body; we just
    # want to ensure it is present in the tree metadata. Depending on platform,
    # 'git ls-files' reports the path without trailing slash.
    assert "sub" in paths
    assert paths["sub"]["tracked"]