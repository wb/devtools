import io
from devtools.flatpack import write_tree_and_header

def test_header_contains_expected_sections(tmp_path):
    entries = [
        {"path": "foo.txt", "tracked": True, "size": 123,
         "redact": False, "reason": "-"}
    ]
    buf = io.StringIO()
    write_tree_and_header(
        buf, str(tmp_path), entries,
        tracked_count=1, untracked_count=0,
        redact_hash="abc123", include_untracked=True
    )
    out = buf.getvalue()
    assert "===== REPO TREE =====" in out
    assert "Root:" in out
    assert "Files:" in out
    assert "Redact-File:" in out
    assert "Redact-File-Hash:" in out
    assert "Resolved:" in out
