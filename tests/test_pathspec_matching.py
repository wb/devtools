import pytest
from devtools.flatpack import compile_gitwild_patterns, decide_redaction

@pytest.mark.parametrize("path,patterns,redacted", [
    ("foo/bar.txt", ["*.txt"], True),
    ("foo/bar.txt", ["*.md"], False),
    ("foo/bar.txt", ["bar.txt"], True),
    ("foo/bar.txt", ["baz.txt"], False),
    ("foo/bar.txt", ["foo/*.txt"], True),
    ("foo/bar.txt", ["/foo/bar.txt"], True),
    ("foo/bar.txt", ["/bar.txt"], False),
    ("foo/bar/baz.txt", ["foo/"], True),
    ("foo/bar/baz.txt", ["/foo/"], True),
    ("foo/bar/baz.txt", ["bar/"], True),
    ("foo/bar/baz.txt", ["baz/"], False),
    ("foo/bar/baz.txt", ["**/baz.txt"], True),
    ("foo/keep.txt", ["*.txt", "!foo/keep.txt"], False),
])
def test_gitwildmatch_cases(path, patterns, redacted):
    pats = compile_gitwild_patterns(patterns)
    got, _reason = decide_redaction(path, pats)
    assert got == redacted