# Changelog

All notable changes to this project will be documented in this file.  

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),  
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).  

## [Unreleased]

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

[Unreleased]: https://github.com/wb/devtools/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/wb/devtools/releases/tag/v0.1.0