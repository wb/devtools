# Changelog

All notable changes to this project will be documented in this file.  

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).  

## [Unreleased]

## [0.2.0] - 2025-09-21

### Changed
- **flatpack** redesign:
  - Redaction is now driven **only by a root `.flatpackredact`** file (gitignore-style, via pathspec). There is no automatic redaction anymore.
  - SHA-256 file hashes are always included (`Hash:` line always present).
  - A new `plan` subcommand (`flatpack plan`) prints the repo tree, the redact file hash, and a per-file decision list (`[include]` / `[redact:…]`), without emitting file bodies or encodings.
  - `--include-untracked` now defaults to `true` (still respects `.gitignore`). Works the same for `plan`.
  - Submodules (gitlinks, mode 160000) are now detected and represented in the tree. They appear as tracked entries with `size=0` and no body output.

### Added
- **`.flatpackredact`** supports full gitignore-style matching:
  - Last match wins; `!pattern` unredacts.
  - Leading `/` anchors to the repo root (e.g., `/.flatpackredact`).
  - Trailing `/` targets directories (e.g., `devtools/`).
  - Patterns without `/` match both basenames and paths (e.g., `*.md`).
  - `**` wildcards are supported.
- The output header now includes:
  - `Redact-File: .flatpackredact (found|absent)`
  - `Redact-File-Hash: sha256:<hex|->`
  - A `Resolved:` block with `include_untracked = true|false`.
- **Dev / CI tooling**:
  - `pyproject.toml` declares `pathspec` as a dependency.
  - New optional `dev` extras with pytest.
  - Makefile targets for `test`, `test-all`, `test-integration`.
  - Pytest configured to use `--basetemp=./.pytest_tmp` and mark `integration` tests.

### Removed (**breaking**)
- Deprecated CLI flags removed in favor of `.flatpackredact`:
  - `--no-hash`, `--redact`, `--redact-ext`, `--redact-images`, `--max-bytes`, `--exclude`, `--exclude-ext`.
- Automatic image redaction (files like `*.png`, `*.jpg`, etc.) is no longer default. Add rules in `.flatpackredact` to restore this behavior.

### Migration notes
- Only the **root** `.flatpackredact` file is used. Files in subdirectories are ignored.
- To hide the redact file itself, add `/.flatpackredact` to it.
- Submodules are now surfaced in the tree view; if you previously relied on them being invisible, you may need to filter them out downstream.

## [0.1.0] - 2025-09-16

### Added
- **softserve**: a tiny static file server with per-project configuration.
  - Supports `.softserve.toml` for repo-local config.
  - CLI overrides (`--dir`, `--port`, `--host`) always take precedence.
  - Displays both local and LAN URLs for easy testing.
  - Includes `serve` as an alias for convenience.
  - `init` subcommand to quickly generate a default config.

- **flatpack**: flatten a Git repo into a single text file with a tree header — ideal for sharing with LLMs.
  - Includes tracked and untracked files (respects `.gitignore`).
  - Redacts image bodies by default (keeps metadata).
  - Per-file SHA-256 hashes (optional).
  - Flexible exclude/redact options by glob or extension.
  - Auto-detects the repo root so it works from any subfolder.

[Unreleased]: https://github.com/wb/devtools/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/wb/devtools/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/wb/devtools/releases/tag/v0.1.0
