import re
from devtools.flatpack import dump_repo
from pathlib import Path

def test_dump_repo_e2e(tmp_path):
    (tmp_path / "foo.txt").write_text("hello")
    (tmp_path / "bin.bin").write_bytes(b"\xff\x00\xff")
    out = tmp_path / "dump.txt"

    dump_repo(output_path=str(out), repo_root=str(tmp_path), include_untracked=True)

    text = out.read_text(encoding="utf-8")
    # header sections
    assert "===== REPO TREE =====" in text
    assert "Redact-File:" in text
    assert "Resolved:" in text
    # file blocks exist with hashes
    assert "Path: foo.txt" in text
    assert re.search(r"Hash: sha256:[0-9a-f]{64}", text)
    # binary encoded
    assert "Path: bin.bin" in text
    assert "Mode: binary" in text
    assert "Encoding: base64" in text