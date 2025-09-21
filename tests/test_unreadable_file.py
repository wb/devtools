import os
import subprocess
import pytest
from devtools.flatpack import dump_repo

def run(cmd, cwd):
    subprocess.check_call(cmd, cwd=cwd)

@pytest.mark.skipif(os.name == "nt", reason="chmod 000 semantics differ on Windows")
def test_unreadable_file_is_reported(tmp_path, capsys):
    # Make this directory a Git repo so untracked discovery works
    run(["git", "init"], cwd=tmp_path)

    p = tmp_path / "secret.txt"
    p.write_text("nope")
    p.chmod(0)  # make unreadable

    out = tmp_path / "dump.txt"
    try:
        # Current behavior: hashing warns, then reading raises PermissionError.
        with pytest.raises(PermissionError):
            dump_repo(str(out), str(tmp_path), include_untracked=True)

        # We still expect to have seen a WARN emitted during hashing.
        stderr = capsys.readouterr().err
        assert "WARN:" in stderr
    finally:
        # Restore perms so pytest can clean up the temp directory
        p.chmod(0o644)