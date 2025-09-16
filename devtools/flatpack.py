#!/usr/bin/env python3
"""
flatpack — flatten a Git working tree into a single text stream with a tree header.

Scope vs. Redaction:
- Scope decides which files appear at all (tree + metadata).
- Redaction hides bodies but keeps metadata.

Defaults:
- Includes tracked AND untracked files in scope.
- Redacts image bodies (keeps their metadata).
- Includes a SHA-256 hash per file (disable with --no-hash).
- Writes to STDOUT if -o/--output is not provided.
- Tree header is always printed first.

Output blocks:

===== REPO TREE =====
Root: <repo-root-basename>
Files: <count>   Tracked: <count>   Untracked: <count>
Legend: [T]=tracked [U]=untracked [inc]=included [redact:<reason>]=redacted
<tree lines>
===== END TREE =====

===== BEGIN FILE =====
Path: <relative/path>
Mode: text|binary
Encoding: utf-8|base64
Size: <bytes>
Redacted: yes|no
Redact-Reason: <reason or ->
Hash: sha256:<hex> | -
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
from fnmatch import fnmatch
from typing import List, Optional, Tuple, Dict, Any

SEP_BEGIN = "===== BEGIN FILE ====="
SEP_CONTENT = "----- CONTENT -----"
SEP_END = "===== END FILE ====="
TREE_BEGIN = "===== REPO TREE ====="
TREE_END = "===== END TREE ====="

# Common image extensions (lowercase, with leading dot)
IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico",
    ".tif", ".tiff", ".psd", ".ai", ".heic", ".heif", ".avif", ".svg"
}

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

def normalize_exts(exts: List[str]) -> set[str]:
    return {e.lower() if e.startswith(".") else f".{e.lower()}" for e in exts}

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

# ------- redaction / filtering -------

def should_redact(rel_path: str,
                  size: int,
                  redact_images: bool,
                  redacted_exts: set[str],
                  redact_globs: List[str],
                  max_bytes: Optional[int],
                  redact_all: bool) -> Tuple[bool, str]:
    """Return (redact, reason)."""
    if redact_all:
        return True, "redact-all"

    ext = os.path.splitext(rel_path)[1].lower()

    if redact_images and ext in IMAGE_EXTS:
        return True, f"image-ext:{ext}"

    if ext in redacted_exts:
        return True, f"ext:{ext}"

    for pat in redact_globs:
        if fnmatch(rel_path, pat):
            return True, f"glob:{pat}"

    if max_bytes is not None and size > max_bytes:
        return True, f"max-bytes:{max_bytes}"

    return False, "-"

def should_exclude(rel_path: str,
                   excluded_exts: set[str],
                   exclude_globs: List[str]) -> bool:
    ext = os.path.splitext(rel_path)[1].lower()
    if ext in excluded_exts:
        return True
    for pat in exclude_globs:
        if fnmatch(rel_path, pat):
            return True
    return False

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

# ------- main flatten -------

def dump_repo(output_path: Optional[str],
              repo_root: str,
              exclude_untracked: bool,
              redact_images: bool,
              redact_exts: List[str],
              redact_globs: List[str],
              max_bytes: Optional[int],
              redact_all: bool,
              exclude_exts: List[str],
              exclude_globs: List[str],
              no_hash: bool) -> None:
    tracked = set(git_ls_tracked(repo_root))
    files = set(tracked)
    untracked = set()
    if not exclude_untracked:
        untracked = set(git_ls_untracked(repo_root))
        files.update(untracked)
    files = sorted(files)

    redacted_exts = normalize_exts(redact_exts)
    excluded_exts = normalize_exts(exclude_exts)

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

    # Pre-scan entries (stat + scope/exclude + redaction decision)
    entries: List[Dict[str, Any]] = []
    tracked_count = 0
    untracked_count = 0

    for rel in files:
        abs_path = os.path.join(repo_root, rel)
        if not os.path.isfile(abs_path):
            continue

        # Scope excludes first
        if should_exclude(rel, excluded_exts, exclude_globs):
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

        redact, reason = should_redact(
            rel_path=rel,
            size=size,
            redact_images=redact_images,
            redacted_exts=redacted_exts,
            redact_globs=redact_globs,
            max_bytes=max_bytes,
            redact_all=redact_all,
        )

        entries.append({
            "path": rel,
            "tracked": is_tracked,
            "size": size,
            "redact": redact,
            "reason": reason,
        })

    # TREE HEADER (always)
    root_name = os.path.basename(os.path.abspath(repo_root.rstrip(os.sep))) or "/"
    outfh.write(f"{TREE_BEGIN}\n")
    outfh.write(f"Root: {root_name}\n")
    outfh.write(f"Files: {len(entries)}   Tracked: {tracked_count}   Untracked: {untracked_count}\n")
    outfh.write("Legend: [T]=tracked [U]=untracked [inc]=included [redact:<reason>]=redacted\n\n")
    tree = build_tree_index(entries)
    render_tree(tree, outfh)
    outfh.write(f"{TREE_END}\n\n")

    # FILE BLOCKS
    for e in entries:
        rel = e["path"]
        abs_path = os.path.join(repo_root, rel)

        # Compute hash (streaming) unless disabled
        if no_hash:
            hash_line = "Hash: -"
        else:
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

def validate_repo_root(path: str) -> str:
    """
    Return the absolute path to the Git repo's top-level directory.
    Works even if 'path' is a subdirectory inside the repo.
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

def main():
    ap = argparse.ArgumentParser(
        description="flatpack: flatten Git working files into a single text stream with a tree header (WIP-friendly)."
    )
    ap.add_argument("--repo", default=".", help="Path to the Git repository (default: current directory)")
    ap.add_argument("-o", "--output", default=None, help="Output file path (default: STDOUT)")

    # Scope
    ap.add_argument("--exclude-untracked", nargs="?", type=parse_bool, const=True, default=False,
                    help="Exclude untracked files from scope (default: false = include untracked).")
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="Glob patterns to EXCLUDE from scope entirely (e.g. 'secrets/**' 'dist/**').")
    ap.add_argument("--exclude-ext", nargs="*", default=[],
                    help="File extensions to EXCLUDE from scope (e.g. .pem .key).")

    # Redaction
    ap.add_argument("--redact-images", nargs="?", type=parse_bool, const=True, default=True,
                    help="Redact image contents (keep metadata). Default: true. Use --redact-images=false to include.")
    ap.add_argument("--redact", nargs="*", default=[],
                    help="Glob patterns to REDACT contents for (metadata only).")
    ap.add_argument("--redact-ext", nargs="*", default=[],
                    help="Extensions to REDACT contents for (e.g. .pdf .zip).")
    ap.add_argument("--max-bytes", type=int, default=None,
                    help="REDACT contents for files larger than this size in bytes.")
    ap.add_argument("--redact-all", action="store_true",
                    help="REDACT contents for EVERY file (tree + metadata only).")

    # Hashing
    ap.add_argument("--no-hash", action="store_true",
                    help="Do not compute per-file SHA-256 hashes (Hash: -).")

    args = ap.parse_args()
    repo_root = validate_repo_root(args.repo)

    dump_repo(
        output_path=args.output,
        repo_root=repo_root,
        exclude_untracked=args.exclude_untracked,
        redact_images=args.redact_images,
        redact_exts=args.redact_ext,
        redact_globs=args.redact,
        max_bytes=args.max_bytes,
        redact_all=args.redact_all,
        exclude_exts=args.exclude_ext,
        exclude_globs=args.exclude,
        no_hash=args.no_hash,
    )

    if args.output:
        print(f"Wrote {args.output} from repo root: {repo_root}", file=sys.stderr)

if __name__ == "__main__":
    main()