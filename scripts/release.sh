#!/usr/bin/env bash
# scripts/release.sh — commit, tag, and push a release based on pyproject.toml + CHANGELOG.md
set -euo pipefail

DRY_RUN=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/release.sh [--dry-run]

Flow:
  1) Read version from pyproject.toml
  2) Ensure CHANGELOG.md top released version matches
  3) Ensure BOTH pyproject.toml and CHANGELOG.md changed
  4) Offer to stage if unstaged
  5) Ensure ONLY those two files are staged
  6) Commit, tag, and push

Options:
  --dry-run  : show what would happen (skip commit/tag/push)
USAGE
      exit 0 ;;
    *)
      echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

prompt_yes() {
  local msg="$1"
  read -r -p "$msg [y/N] " ans
  [[ "$ans" == "y" || "$ans" == "Y" ]]
}

abort() { echo "Error: $*" >&2; exit 1; }

run() {
  if [[ $DRY_RUN -eq 1 ]]; then
    echo "[dry-run] $*"
  else
    eval "$@"
  fi
}

PTOML_VER="$(sed -nE 's/^version = "([^"]+)".*/\1/p' pyproject.toml | head -n1)"
[[ -n "$PTOML_VER" ]] || abort "couldn't parse version from pyproject.toml"
echo "Detected version: v$PTOML_VER"

CLOG_VER="$(sed -nE 's/^## \[([0-9]+\.[0-9]+\.[0-9]+)\].*/\1/p' CHANGELOG.md | head -n1)"
[[ -n "$CLOG_VER" ]] || abort "couldn't parse latest version from CHANGELOG.md"
[[ "$PTOML_VER" == "$CLOG_VER" ]] || abort "version mismatch: pyproject.toml=$PTOML_VER vs CHANGELOG.md=$CLOG_VER"

CHANGED_PY="$(git diff --name-only -- pyproject.toml)"
CHANGED_CL="$(git diff --name-only -- CHANGELOG.md)"
STAGED_PY="$(git diff --cached --name-only -- pyproject.toml)"
STAGED_CL="$(git diff --cached --name-only -- CHANGELOG.md)"
[[ -n "$CHANGED_PY$STAGED_PY" ]] || abort "pyproject.toml has no changes"
[[ -n "$CHANGED_CL$STAGED_CL" ]] || abort "CHANGELOG.md has no changes"

if [[ -n "$CHANGED_PY$CHANGED_CL" ]]; then
  if prompt_yes "Stage pyproject.toml and CHANGELOG.md now?"; then
    run "git add pyproject.toml CHANGELOG.md"
  else
    abort "Aborting release."
  fi
fi

# Enforce staging only in real mode (skip in --dry-run)
if [[ $DRY_RUN -eq 0 ]]; then
  STAGED_ALL="$(git diff --cached --name-only || true)"
  echo "$STAGED_ALL" | grep -qx "pyproject.toml" || abort "pyproject.toml not staged"
  echo "$STAGED_ALL" | grep -qx "CHANGELOG.md"   || abort "CHANGELOG.md not staged"
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    [[ "$f" == "pyproject.toml" || "$f" == "CHANGELOG.md" ]] || abort "other file staged: $f"
  done <<< "$STAGED_ALL"
fi

if git rev-parse -q --verify "refs/tags/v$PTOML_VER" >/dev/null 2>&1; then
  abort "tag v$PTOML_VER already exists"
fi

if ! prompt_yes "Proceed with release v$PTOML_VER?"; then
  abort "Aborted."
fi

run "git commit -m 'chore(release): $PTOML_VER'"
run "git tag -a 'v$PTOML_VER' -m 'Release v$PTOML_VER'"
run "git push"
run "git push --tags"

echo "Done."