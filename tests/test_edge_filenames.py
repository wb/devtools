import subprocess
from devtools.flatpack import compile_gitwild_patterns, collect_entries

def run(cmd, cwd):
    subprocess.check_call(cmd, cwd=cwd)

def test_unusual_filenames(tmp_path):
    # Make this a Git repo so ls-files works for untracked files
    run(["git", "init"], cwd=tmp_path)

    files = [
        " spaced name .txt",
        "ümlaut-ß.txt",
        ".leadingdot",
        "emoji-📁/note.txt",
    ]
    (tmp_path / "emoji-📁").mkdir(exist_ok=True)
    for f in files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("ok", encoding="utf-8")

    pats = compile_gitwild_patterns([])  # no redaction
    entries, _t, _u = collect_entries(str(tmp_path), include_untracked=True, pats=pats)

    names = {e["path"] for e in entries}
    assert " spaced name .txt" in names
    assert "ümlaut-ß.txt" in names
    assert ".leadingdot" in names
    assert "emoji-📁/note.txt" in names