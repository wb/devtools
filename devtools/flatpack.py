#!/usr/bin/env python3
"""
flatpack — flatten a Git working tree into a single text stream with a tree header.

Scope vs. Redaction:
- Scope decides which files appear at all (tree + metadata).
- Redaction hides bodies but keeps metadata.

Defaults (no config file required):
- Includes tracked AND untracked files in scope (untracked respects .gitignore).
- No automatic redaction (unless a `.flatpackredact` file is present).
- Includes a SHA-256 hash per file (always on).
- Writes to STDOUT if -o/--output is not provided.
- Tree header is always printed first.

Output blocks:

===== REPO TREE =====
Root: <repo-root-basename>
Files: <count>   Tracked: <count>   Untracked: <count>
Legend: [T]=tracked [U]=untracked [inc]=included [redact:<reason>]=redacted
<tree lines>
===== END TREE =====

Redact-File: .flatpackredact (found|absent)
Redact-File-Hash: sha256:<hex|-> 
Resolved:
  include_untracked = true|false

===== BEGIN FILE =====
Path: <relative/path>
Mode: text|binary
Encoding: utf-8|base64
Size: <bytes>
Redacted: yes|no
Redact-Reason: <reason or ->
Hash: sha256:<hex>
----- CONTENT -----
<file content or empty if redacted>
===== END FILE =====
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import os
import subprocess
import sys
from typing import List, Optional, Tuple, Dict, Any

# Third-party: pathspec implements Git's gitignore "gitwildmatch" semantics.
import pathspec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

SEP_BEGIN = "===== BEGIN FILE ====="
SEP_CONTENT = "----- CONTENT -----"
SEP_END = "===== END FILE ====="
TREE_BEGIN = "===== REPO TREE ====="
TREE_END = "===== END TREE ====="

REDACT_FILE_NAME = ".flatpackredact"


# ------- git helpers -------

def git_ls_tracked(repo_root: str) -> List[str]:
    try:
        out = subprocess.check_output(["git", "ls-files", "-z"], cwd=repo_root)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: git ls-files failed: {e}", file=sys.stderr)
        sys.exit(1)
    parts = out.split(b"\x00")
    return [p.decode("utf-8", "surrogateescape") for p in parts if p]

def git_ls_untracked(repo_root: str) -> List[str]:
    """Untracked files (not ignored) according to .gitignore and standard excludes."""
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=repo_root
        )
    except subprocess.CalledProcessError as e:
        print(f"ERROR: git ls-files --others failed: {e}", file=sys.stderr)
        sys.exit(1)
    parts = out.split(b"\x00")
    return [p.decode("utf-8", "surrogateescape") for p in parts if p]

def git_ls_submodules(repo_root: str) -> List[str]:
    """
    Return paths of submodules (gitlinks) in the index.
    We parse `git ls-files --stage` for entries with mode 160000.
    """
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "--stage", "-z"],
            cwd=repo_root
        )
    except subprocess.CalledProcessError as e:
        print(f"ERROR: git ls-files --stage failed: {e}", file=sys.stderr)
        sys.exit(1)
    items = [p for p in out.split(b"\x00") if p]
    paths: List[str] = []
    for rec in items:
        # rec format (NUL-separated): b"{mode} {sha}\t{path}"
        try:
            meta, path = rec.split(b"\t", 1)
            mode = meta.split(b" ", 1)[0]
            if mode == b"160000":
                paths.append(path.decode("utf-8", "surrogateescape"))
        except Exception:
            continue
    return paths


# ------- io/utility -------

def read_working_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()

def is_utf8_text(b: bytes) -> bool:
    try:
        b.decode("utf-8")
        return True
    except UnicodeDecodeError:
        return False

def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    x = float(n)
    while x >= 1024 and i < len(units) - 1:
        x /= 1024.0
        i += 1
    return f"{int(x)}{units[i]}" if i == 0 else f"{x:.1f}{units[i]}"

def parse_bool(v: Optional[str]) -> bool:
    if v is None:
        return True  # bare --flag means True
    s = str(v).strip().lower()
    if s in ("1", "true", "t", "yes", "y", "on"):
        return True
    if s in ("0", "false", "f", "no", "n", "off"):
        return False
    raise argparse.ArgumentTypeError(f"Expected boolean (true/false), got: {v}")

def sha256_file(path: str) -> str:
    """Streaming SHA-256 of a file on disk."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _normalize_path(p: str) -> str:
    # Remove literal "./" prefixes only; do NOT strip leading dots.
    while p.startswith("./"):
        p = p[2:]
    return p


# ------- redact rules (.flatpackredact via pathspec) -------

def load_redact_lines(repo_root: str) -> Tuple[List[str], Optional[str]]:
    """
    Load .flatpackredact lines (from repo root only).
    Returns (lines, sha256_hex_or_None).
    Comments (# ...) and blank lines are skipped. Raw patterns (including leading '!') are preserved.
    """
    path = os.path.join(repo_root, REDACT_FILE_NAME)
    if not os.path.isfile(path):
        return [], None
    try:
        raw = read_working_file(path)
    except Exception as e:
        print(f"WARN: cannot read {REDACT_FILE_NAME}: {e}", file=sys.stderr)
        return [], None

    lines: List[str] = []
    for line in raw.decode("utf-8", "replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        lines.append(s)
    return lines, sha256_bytes(raw)

def compile_gitwild_patterns(lines: List[str]) -> List[GitWildMatchPattern]:
    """Compile redact lines into GitWildMatchPattern objects (order preserved)."""
    return [GitWildMatchPattern(p) for p in lines]

def decide_redaction(rel_path: str, pats: List[GitWildMatchPattern]) -> Tuple[bool, str]:
    """
    Apply patterns in order (gitignore semantics): last match wins.
    Returns (redact, reason) where reason is "glob:<pattern>" or "negate:!<pattern>" or "-".

    Note on mapping to redaction:
      - For GitWildMatchPattern, `include == True` means a normal ignore rule (no '!').
        We treat "ignored" as **redacted** -> (True, "glob:<pattern>").
      - `include == False` means a negated rule ('!…').
        We treat negation as **unredact** -> (False, "negate:!<core>").
    """
    rel_path = _normalize_path(rel_path)
    last: Optional[Tuple[bool, str]] = None  # (include_flag, pattern_text)
    for p in pats:
        if p.match_file(rel_path):
            last = (p.include, p.pattern)
    if last is None:
        return False, "-"
    include, pat_text = last
    if include:
        # Normal ignore rule => redact
        return True, f"glob:{pat_text}"
    else:
        # Negated rule => unredact; ensure reason uses a single leading '!'
        core = pat_text.lstrip("!")
        return False, f"negate:!{core}"


# ------- tree building/rendering -------

def build_tree_index(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    entries: dicts with keys:
      - path (str)
      - tracked (bool)
      - size (int)
      - redact (bool)
      - reason (str)
    Returns a nested dict with "__dirs__" and "__files__".
    """
    root: Dict[str, Any] = {"__dirs__": {}, "__files__": []}
    for e in entries:
        parts = e["path"].split("/")
        node = root
        for p in parts[:-1]:
            node = node["__dirs__"].setdefault(p, {"__dirs__": {}, "__files__": []})
        node["__files__"].append(e)
    return root

def render_tree(node: Dict[str, Any], outfh, prefix: str = "") -> None:
    dir_names = sorted(node["__dirs__"].keys())
    file_entries = sorted(node["__files__"], key=lambda e: e["path"].split("/")[-1])

    items: List[Tuple[str, Any]] = [("dir", name) for name in dir_names] + [("file", e) for e in file_entries]

    for idx, item in enumerate(items):
        last = (idx == len(items) - 1)
        branch = "└── " if last else "├── "
        if item[0] == "dir":
            name = item[1]
            outfh.write(f"{prefix}{branch}{name}/\n")
            child_prefix = prefix + ("    " if last else "│   ")
            render_tree(node["__dirs__"][name], outfh, child_prefix)
        else:
            e = item[1]
            tag = "[T]" if e["tracked"] else "[U]"
            status = "[inc]" if not e["redact"] else f"[redact:{e['reason']}]"
            fname = e["path"].split("/")[-1]
            outfh.write(f"{prefix}{branch}{fname} {tag} {status} ({human_size(e['size'])})\n")


# ------- core routines -------

def collect_entries(repo_root: str, include_untracked: bool, pats: List[GitWildMatchPattern]) -> Tuple[List[Dict[str, Any]], int, int]:
    tracked = set(git_ls_tracked(repo_root))
    submods = set(git_ls_submodules(repo_root))  # gitlinks present in the index
    files = set(tracked)
    untracked = set()
    if include_untracked:
        untracked = set(git_ls_untracked(repo_root))
        files.update(untracked)
    # Ensure submodule paths are represented even though they aren't regular files
    files.update(submods)
    files = sorted(files)

    entries: List[Dict[str, Any]] = []
    tracked_count = 0
    untracked_count = 0

    for rel in files:
        abs_path = os.path.join(repo_root, rel)

        # Special-case: submodule gitlinks are directories on disk; include them
        if rel in submods:
            is_tracked = True
            tracked_count += 1
            redact, reason = decide_redaction(rel, pats)
            entries.append({
                "path": rel,
                "tracked": is_tracked,
                "size": 0,
                "redact": redact,
                "reason": reason,
            })
            continue

        if not os.path.isfile(abs_path):
            continue
        try:
            size = os.path.getsize(abs_path)
        except OSError as e:
            print(f"WARN: cannot stat {rel}: {e}", file=sys.stderr)
            continue

        is_tracked = rel in tracked
        if is_tracked:
            tracked_count += 1
        else:
            untracked_count += 1

        redact, reason = decide_redaction(rel, pats)

        entries.append({
            "path": rel,
            "tracked": is_tracked,
            "size": size,
            "redact": redact,
            "reason": reason,
        })
    return entries, tracked_count, untracked_count

def write_tree_and_header(outfh, repo_root: str, entries: List[Dict[str, Any]],
                          tracked_count: int, untracked_count: int,
                          redact_hash: Optional[str], include_untracked: bool) -> None:
    root_name = os.path.basename(os.path.abspath(repo_root.rstrip(os.sep))) or "/"
    outfh.write(f"{TREE_BEGIN}\n")
    outfh.write(f"Root: {root_name}\n")
    outfh.write(f"Files: {len(entries)}   Tracked: {tracked_count}   Untracked: {untracked_count}\n")
    outfh.write("Legend: [T]=tracked [U]=untracked [inc]=included [redact:<reason>]=redacted\n\n")
    tree = build_tree_index(entries)
    render_tree(tree, outfh)
    outfh.write(f"{TREE_END}\n\n")

    outfh.write(f"Redact-File: {REDACT_FILE_NAME} ({'found' if redact_hash else 'absent'})\n")
    outfh.write(f"Redact-File-Hash: {'sha256:' + redact_hash if redact_hash else '-'}\n")
    outfh.write("Resolved:\n")
    outfh.write(f"  include_untracked = {'true' if include_untracked else 'false'}\n\n")

def dump_repo(output_path: Optional[str],
              repo_root: str,
              include_untracked: bool) -> None:
    # Strictly designed for Git repos (fail fast if not in a repo)
    repo_root = validate_repo_root(repo_root)

    # Load redact rules
    lines, redact_hash = load_redact_lines(repo_root)
    pats = compile_gitwild_patterns(lines) if lines else []

    # Open destination
    close_when_done = False
    if output_path:
        outfh = open(output_path, "w", encoding="utf-8", newline="\n")
        close_when_done = True
    else:
        outfh = sys.stdout
        try:
            outfh.reconfigure(encoding="utf-8", newline="\n")  # type: ignore[attr-defined]
        except Exception:
            pass

    # Build entries
    entries, tracked_count, untracked_count = collect_entries(repo_root, include_untracked, pats)

    # TREE + header
    write_tree_and_header(outfh, repo_root, entries, tracked_count, untracked_count, redact_hash, include_untracked)

    # FILE BLOCKS
    for e in entries:
        rel = e["path"]
        abs_path = os.path.join(repo_root, rel)

        # Always compute per-file hash (streaming)
        try:
            hexhash = sha256_file(abs_path)
            hash_line = f"Hash: sha256:{hexhash}"
        except Exception as ex:
            print(f"WARN: cannot hash {rel}: {ex}", file=sys.stderr)
            hash_line = "Hash: -"

        if e["redact"]:
            mode = "binary"   # conservative default when we don't read content
            enc = "base64"
            outfh.write(f"{SEP_BEGIN}\n")
            outfh.write(f"Path: {rel}\n")
            outfh.write(f"Mode: {mode}\n")
            outfh.write(f"Encoding: {enc}\n")
            outfh.write(f"Size: {e['size']}\n")
            outfh.write(f"Redacted: yes\n")
            outfh.write(f"Redact-Reason: {e['reason']}\n")
            outfh.write(f"{hash_line}\n")
            outfh.write(f"{SEP_CONTENT}\n")
            outfh.write(f"{SEP_END}\n\n")
            continue

        data = read_working_file(abs_path)
        if is_utf8_text(data):
            mode = "text"
            enc = "utf-8"
            body = data.decode("utf-8")
        else:
            mode = "binary"
            enc = "base64"
            body = base64.b64encode(data).decode("ascii")

        outfh.write(f"{SEP_BEGIN}\n")
        outfh.write(f"Path: {rel}\n")
        outfh.write(f"Mode: {mode}\n")
        outfh.write(f"Encoding: {enc}\n")
        outfh.write(f"Size: {len(data)}\n")
        outfh.write(f"Redacted: no\n")
        outfh.write(f"Redact-Reason: -\n")
        outfh.write(f"{hash_line}\n")
        outfh.write(f"{SEP_CONTENT}\n")
        outfh.write(body)
        if not body.endswith("\n"):
            outfh.write("\n")
        outfh.write(f"{SEP_END}\n\n")

    if close_when_done:
        outfh.close()


# ------- plan subcommand -------

def run_plan(repo_root: str, include_untracked: bool) -> int:
    # Strictly designed for Git repos
    repo_root = validate_repo_root(repo_root)

    lines, redact_hash = load_redact_lines(repo_root)
    pats = compile_gitwild_patterns(lines) if lines else []
    entries, tracked_count, untracked_count = collect_entries(repo_root, include_untracked, pats)

    # Print tree + header (same as dump, but no file bodies)
    outfh = sys.stdout
    try:
        outfh.reconfigure(encoding="utf-8", newline="\n")  # type: ignore[attr-defined]
    except Exception:
        pass

    write_tree_and_header(outfh, repo_root, entries, tracked_count, untracked_count, redact_hash, include_untracked)

    # Decisions list
    for e in entries:
        if e["redact"]:
            outfh.write(f"[redact:{e['reason']}] {e['path']}\n")
        elif e["reason"].startswith("negate:!"):
            outfh.write(f"[include:{e['reason']}] {e['path']}\n")
        else:
            outfh.write(f"[include] {e['path']}\n")
    return 0


# ------- arg parsing / main -------

def validate_repo_root(path: str) -> str:
    """
    Return the absolute path to the Git repo's top-level directory.
    Works even if 'path' is a subdirectory inside the repo.

    This tool is **strictly** for Git repos: we fail fast if not in a repo.
    """
    if not os.path.isdir(path):
        print(f"ERROR: {path} is not a directory.", file=sys.stderr)
        sys.exit(1)
    try:
        # Confirm we're inside a repo
        subprocess.check_output(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
        # Resolve to the repo root (top-level)
        top = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], cwd=path
        ).decode("utf-8", "replace").strip()
    except subprocess.CalledProcessError:
        print(f"ERROR: {path} is not a Git repository.", file=sys.stderr)
        sys.exit(1)
    return os.path.abspath(top)

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="flatpack: flatten Git working files into a single text stream with a tree header."
    )
    sub = ap.add_subparsers(dest="command", required=False)

    # main dump command (default when no subcommand provided)
    ap.add_argument("--repo", default=".", help="Path to the Git repository (default: current directory)")
    ap.add_argument("-o", "--output", default=None, help="Output file path (default: STDOUT)")
    ap.add_argument("--include-untracked", nargs="?", type=parse_bool, const=True, default=True,
                    help="Include untracked files (respects .gitignore). Default: true. Use --include-untracked=false to disable.")

    # plan subcommand
    plan = sub.add_parser("plan", help="Preview redaction decisions (no file bodies, no hashing)")
    plan.add_argument("--repo", default=".", help="Path to the Git repository (default: current directory)")
    plan.add_argument("-o", "--output", default=None, help="(ignored)")
    plan.add_argument("--include-untracked", nargs="?", type=parse_bool, const=True, default=True,
                      help="Include untracked files (respects .gitignore). Default: true.")

    return ap

def main():
    ap = build_parser()
    args = ap.parse_args()

    repo_root = validate_repo_root(getattr(args, "repo", "."))

    if getattr(args, "command", None) == "plan":
        raise SystemExit(run_plan(repo_root, include_untracked=args.include_untracked))

    # default: dump
    dump_repo(
        output_path=args.output,
        repo_root=repo_root,
        include_untracked=args.include_untracked,
    )

    if args.output:
        print(f"Wrote {args.output} from repo root: {repo_root}", file=sys.stderr)

if __name__ == "__main__":
    main()