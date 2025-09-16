# devtools

Small developer utilities.

- [Installation](#installation)
- [softserve](#softserve)
- [flatpack](#flatpack)

_Requires Python 3.11+_

---

## Installation

Clone and install in editable mode (so changes reflect immediately):

```bash
git clone https://github.com/wb/devtools.git
cd devtools
make install
```

To uninstall:

```bash
make uninstall
```

This installs the tools into your `PATH`: `softserve`, `serve` (alias), and `flatpack`.

---

## softserve

A tiny static file server with **per-project config**.

Create a `.softserve.toml` in any repo (best run from repo root):

```bash
softserve init
```

and run:

```bash
softserve
```

### Features
- Config is per project (`.softserve.toml`).
- Automatically serves from your chosen directory (e.g. `public/`).
- Shows both **local** and **network** URLs (so you can test from your phone).
- CLI flags always override config (handy for quick one-offs).

### Usage

From a repo root:

```bash
softserve init                      # defaults: dir=public, port=8000, host=0.0.0.0
softserve init --dir public --port 9000 --host 0.0.0.0
softserve init --dry-run            # preview without writing
softserve init --force              # overwrite (backs up existing file)
```

then run from config:

```bash
softserve                # read .softserve.toml if present
```

or from CLI flags

```bash
softserve -d public      # serve ./public at http://localhost:8000
softserve --port 8000    # override port
softserve --host 0.0.0.0 # allow LAN devices to connect
```

Output looks like:

```
[softserve] Using config file: /path/to/.softserve.toml
[softserve] Serving /my/project/public at:
  Local:   http://localhost:8000/
  Network: http://192.168.1.41:8000/
(Ctrl+C to stop)
```

---

## flatpack

Flatten a Git repo into a single text file with a tree header --- ideal
for sharing with LLMs.

### Quick start

```bash
flatpack --repo . -o dump.txt
# or just pipe to your terminal
flatpack
# or to your clipboard
flatpack | pbcopy
```

### Defaults

-   Includes tracked **and** untracked files (respects `.gitignore`).
-   Redacts image contents (keeps metadata).
-   Adds a SHA-256 per file (disable with `--no-hash`).
-   Auto-detects repo root and works from any subfolder.

### Common options

``` bash
flatpack --exclude "secrets/**" "dist/**"        # drop from scope entirely
flatpack --exclude-ext .pem .key                 # drop by extension
flatpack --redact "config/*.json"                # keep file metadata, hide body
flatpack --redact-ext .pdf .zip                  # redact by extension
flatpack --max-bytes 100000                      # redact files over 100 KB
flatpack --exclude-untracked                     # only tracked files
```

---

### License
MIT © 2025 Walter Lark
