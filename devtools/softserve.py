#!/usr/bin/env python3
"""
softserve — tiny static server with per-project config.

- Looks for a TOML config in the current or parent dirs: .softserve.toml
- CLI flags override config file values.
- If no config is found, uses built-in defaults (overridable via CLI).

Example config (.softserve.toml):
    dir = "public"
    port = 8000
    host = "0.0.0.0"
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Dict, Optional, Tuple

import tomllib  # Python 3.11+

# Built-in defaults when no config file is present
FALLBACK_DEFAULTS: Dict[str, object] = {
    "dir": ".",
    "port": 8000,
    "host": "0.0.0.0",
}

CONFIG_NAMES = [".softserve.toml"]


# ---------- Config discovery & loading ----------

def find_config(start: Path) -> Optional[Path]:
    """Search for a config file from 'start' up to the filesystem root."""
    cur = start.resolve()
    root = cur.anchor
    while True:
        for name in CONFIG_NAMES:
            candidate = cur / name
            if candidate.exists():
                return candidate
        if str(cur) == root:
            return None
        cur = cur.parent


def load_config() -> Tuple[Dict[str, object], Optional[Path]]:
    """
    Return (config_dict, config_path). If no config is found, returns ({}, None).
    """
    cfg_path = find_config(Path.cwd())
    if not cfg_path:
        return {}, None

    try:
        data = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[softserve] Warning: failed to parse {cfg_path}: {e}", file=sys.stderr)
        data = {}

    return data, cfg_path


# ---------- CLI parsing ----------

def parse_args(cfg: Dict[str, object], cfg_path: Optional[Path]) -> argparse.Namespace:
    """
    Create parser with defaults coming from:
      - config file if present, otherwise
      - built-in FALLBACK_DEFAULTS.

    Also attach a list of '--flag=value' overrides as args._overrides for display.
    """
    if cfg_path:
        defaults = {**FALLBACK_DEFAULTS, **cfg}
    else:
        defaults = FALLBACK_DEFAULTS

    p = argparse.ArgumentParser(
        prog="softserve",
        description="Serve a folder via Python's HTTP server (with TOML config).",
    )
    sub = p.add_subparsers(dest="command", required=False)

    # normal serve args
    p.add_argument("-d", "--dir", default=defaults["dir"], help="Directory to serve")
    p.add_argument("-p", "--port", type=int, default=defaults["port"], help="Port to bind")
    p.add_argument("--host", default=defaults["host"], help="Host to bind")

    # --version flag (shows installed package version, or 0.0.0 from source)
    from importlib.metadata import version, PackageNotFoundError
    try:
        pkg_ver = version("devtools-lark")
    except PackageNotFoundError:
        pkg_ver = "0.0.0"
    p.add_argument("--version", action="version", version=f"%(prog)s {pkg_ver}")

    # init subcommand
    init = sub.add_parser("init", help="Create a default .softserve.toml in the current repo")
    init.add_argument("--dir", default="public", help="Directory to serve (default: public)")
    init.add_argument("--port", type=int, default=8000, help="Port to bind (default: 8000)")
    init.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    init.add_argument("--force", action="store_true", help="Overwrite existing file")
    init.add_argument("--dry-run", action="store_true", help="Print config instead of writing")

    args = p.parse_args()

    # Record which values were explicitly overridden on the CLI (serve mode only)
    overrides = []
    if getattr(args, "command", None) != "init":
        if str(args.dir) != str(defaults["dir"]):
            overrides.append(f"dir={args.dir}")
        if int(args.port) != int(defaults["port"]):
            overrides.append(f"port={args.port}")
        if str(args.host) != str(defaults["host"]):
            overrides.append(f"host={args.host}")
    args._overrides = overrides
    return args


# ---------- Helpers ----------

def get_local_ip() -> str:
    """Try to detect LAN IP so other devices on your network can connect."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't actually send packets; just forces a route lookup.
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def resolve_serve_dir(dir_arg: str, cfg_path: Optional[Path]) -> Path:
    """
    Resolve the serving directory:
      - If a config file is present and 'dir_arg' is relative, resolve it
        relative to the config file's directory (project root).
      - Otherwise, resolve relative to the current working directory.
    """
    dir_path = Path(dir_arg)
    if dir_path.is_absolute():
        return dir_path.resolve()

    base = cfg_path.parent if cfg_path else Path.cwd()
    return (base / dir_path).resolve()


# ---------- Init command ----------

def do_init(args) -> int:
    """Write a default .softserve.toml (or print if --dry-run)."""
    content = f"""# .softserve.toml
dir = "{args.dir}"
port = {args.port}
host = "{args.host}"
"""
    target = Path.cwd() / ".softserve.toml"
    if args.dry_run:
        print(content.strip())
        return 0
    if target.exists() and not args.force:
        print(f"[softserve] Error: {target} already exists (use --force to overwrite)", file=sys.stderr)
        return 1
    if target.exists() and args.force:
        backup = target.with_suffix(target.suffix + ".bak")
        try:
            target.rename(backup)
            print(f"[softserve] Existing file backed up as {backup}")
        except Exception as e:
            print(f"[softserve] Warning: failed to backup existing file: {e}", file=sys.stderr)
    try:
        target.write_text(content, encoding="utf-8")
    except Exception as e:
        print(f"[softserve] Error: failed to write {target}: {e}", file=sys.stderr)
        return 1
    print(f"[softserve] Wrote default config to {target}")
    return 0


# ---------- Main ----------

def main() -> int:
    cfg, cfg_path = load_config()
    args = parse_args(cfg, cfg_path)

    if args.command == "init":
        return do_init(args)

    serve_dir = resolve_serve_dir(str(args.dir), cfg_path)

    if cfg_path:
        print(f"[softserve] Using config file: {cfg_path}")
    else:
        print("[softserve] No config file found — using built-in defaults (overridable via CLI)")

    if args._overrides:
        print(f"[softserve] CLI overrides: {', '.join(args._overrides)}")

    if not serve_dir.exists() or not serve_dir.is_dir():
        print(f"[softserve] Error: directory not found: {serve_dir}", file=sys.stderr)
        return 2

    # Serve from the chosen directory
    os.chdir(serve_dir)

    class QuietHandler(SimpleHTTPRequestHandler):
        # Keep default logging for now; customize if you want less noise.
        pass

    addr = (args.host, args.port)
    try:
        httpd = ThreadingHTTPServer(addr, QuietHandler)
    except OSError as e:
        print(f"[softserve] Failed to bind {addr}: {e}", file=sys.stderr)
        return 2

    # Show "localhost" for typical dev hosts
    url_host = "localhost" if args.host in ("0.0.0.0", "127.0.0.1", "localhost") else args.host

    print(f"[softserve] Serving {serve_dir} at:")
    print(f"  Local:   http://{url_host}:{args.port}/")
    if args.host == "0.0.0.0":
        print(f"  Network: http://{get_local_ip()}:{args.port}/")
    elif args.host in ("127.0.0.1", "localhost"):
        print("[softserve] Note: bound to loopback only; other devices cannot connect. "
              "Use --host 0.0.0.0 to allow LAN access.")
    print("(Ctrl+C to stop)")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[softserve] Shutting down…")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())