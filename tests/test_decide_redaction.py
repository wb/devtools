import pytest
from devtools.flatpack import compile_gitwild_patterns, decide_redaction

def test_no_rules_includes_by_default():
    pats = compile_gitwild_patterns([])
    assert decide_redaction("foo.txt", pats) == (False, "-")

def test_simple_redact():
    pats = compile_gitwild_patterns(["*.txt"])
    assert decide_redaction("foo.txt", pats) == (True, "glob:*.txt")

def test_simple_unredact():
    # last match wins; !foo.txt negates earlier *.txt
    pats = compile_gitwild_patterns(["*.txt", "!foo.txt"])
    assert decide_redaction("foo.txt", pats) == (False, "negate:!foo.txt")

def test_last_match_wins_exact_overrides():
    pats = compile_gitwild_patterns(["*.txt", "!foo.txt", "foo.txt"])
    assert decide_redaction("foo.txt", pats) == (True, "glob:foo.txt")

def test_directory_rule_and_subdir():
    pats = compile_gitwild_patterns(["data/"])
    assert decide_redaction("data/file.bin", pats) == (True, "glob:data/")
    assert decide_redaction("data/sub/n.txt", pats) == (True, "glob:data/")
    assert decide_redaction("other/file.txt", pats) == (False, "-")

def test_root_anchored_rule():
    pats = compile_gitwild_patterns(["/README.md"])
    assert decide_redaction("README.md", pats) == (True, "glob:/README.md")
    assert decide_redaction("docs/README.md", pats) == (False, "-")

def test_double_star_wildcard():
    pats = compile_gitwild_patterns(["**/secret.txt"])
    assert decide_redaction("secret.txt", pats) == (True, "glob:**/secret.txt")
    assert decide_redaction("a/b/secret.txt", pats) == (True, "glob:**/secret.txt")