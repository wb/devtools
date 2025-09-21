from devtools.flatpack import human_size, is_utf8_text, _normalize_path

def test_human_size():
    assert human_size(0) == "0B"
    assert human_size(27) == "27B"
    assert human_size(1024) == "1.0KB"
    assert human_size(1536) == "1.5KB"
    assert human_size(1048576) == "1.0MB"

def test_is_utf8_text():
    assert is_utf8_text("hello".encode("utf-8")) is True
    assert is_utf8_text(b"\xff\xfe\xfa") is False  # invalid UTF-8 sequence

def test_normalize_path():
    assert _normalize_path("foo/bar") == "foo/bar"
    assert _normalize_path("./foo/bar") == "foo/bar"
    assert _normalize_path("././a") == "a"
    # do NOT strip leading dot of filenames
    assert _normalize_path("./.env") == ".env"