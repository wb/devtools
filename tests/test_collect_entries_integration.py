import subprocess
import pytest
from devtools.flatpack import collect_entries, load_redact_lines, compile_gitwild_patterns

pytestmark = pytest.mark.integration

def run(cmd, cwd):
    subprocess.check_call(cmd, cwd=cwd)

def test_collect_entries_integration(tmp_path):
    # init repo
    run(["git", "init"], cwd=tmp_path)
    (tmp_path / "foo.py").write_text("print('hi')")
    (tmp_path / "bar.txt").write_text("hello")
    (tmp_path / ".gitignore").write_text("ignored.txt\n")
    (tmp_path / "ignored.txt").write_text("ignore me")

    # Make the test independent of user/global git config:
    #  - turn off commit signing (avoids passphrase prompts)
    #  - set a local identity in case global user.name/email are missing
    run(["git", "config", "user.name", "Flatpack Test"], cwd=tmp_path)
    run(["git", "config", "user.email", "flatpack@example.com"], cwd=tmp_path)

    run(["git", "add", "foo.py"], cwd=tmp_path)
    run(["git", "-c", "commit.gpgsign=false", "commit", "--no-gpg-sign", "-m", "init"], cwd=tmp_path)

    lines, _ = load_redact_lines(str(tmp_path))
    pats = compile_gitwild_patterns(lines)
    entries, tracked_count, untracked_count = collect_entries(
        str(tmp_path), include_untracked=True, pats=pats
    )

    paths = {e["path"]: e for e in entries}
    assert "foo.py" in paths and paths["foo.py"]["tracked"]
    assert "bar.txt" in paths and not paths["bar.txt"]["tracked"]
    # .gitignore excluded untracked `ignored.txt`
    assert "ignored.txt" not in paths