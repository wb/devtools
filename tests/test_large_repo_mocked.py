from devtools import flatpack as fp

def test_collect_entries_many_files(monkeypatch, tmp_path):
    many = [f"f{i}.txt" for i in range(3000)]
    # create a subset so size/stat works for some; others will be skipped by isfile
    for name in many[:50]:
        (tmp_path / name).write_text("x")

    monkeypatch.setattr(fp, "git_ls_tracked", lambda root: many)
    monkeypatch.setattr(fp, "git_ls_untracked", lambda root: [])
    pats = fp.compile_gitwild_patterns([])
    entries, t, u = fp.collect_entries(str(tmp_path), include_untracked=False, pats=pats)
    # Only files that actually exist get included
    assert len(entries) == 50