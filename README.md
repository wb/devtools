# devtools

Small developer utilities.

- [Installation](#installation)
- [flatpack](#flatpack)
- [softserve](#softserve)

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

## flatpack

Flatten a Git repo into a single text file with a tree header — ideal
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

- Includes tracked **and** untracked files (respects `.gitignore`).
- Redaction is controlled only by a root `.flatpackredact` file (gitignore-style).
- SHA-256 hashes are always included per file.
- Auto-detects repo root and works from any subfolder.

### Redaction rules

Flatpack looks for a single `.flatpackredact` file at the **repo root**.  
It uses [gitignore-style patterns](https://git-scm.com/docs/gitignore) (last match wins, `!` negates).  

Examples:

```gitignore
# redact all Markdown
*.md

# redact everything under devtools/
devtools/

# redact root file only
/.flatpackredact

# but keep README.md even if other rules match
!README.md
```

### Plan mode

Use `plan` to preview decisions without writing file bodies:

```bash
flatpack plan
```

This prints the tree, redact file hash, and a list of `[include]` / `[redact:…]` decisions.

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

### License
MIT © 2025 Walter Lark
