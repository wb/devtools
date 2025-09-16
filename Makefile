# Makefile (repo root)
# Common tasks for devtools

PYTHON   ?= python3
PIP      ?= $(PYTHON) -m pip
PKG_NAME ?= devtools-lark
RELEASE_SCRIPT := scripts/release.sh

.PHONY: help install uninstall build release release-dry clean distclean

help:
	@echo "Targets:"
	@echo "  make install       - Editable install (pip install -e . --user)"
	@echo "  make uninstall     - Uninstall $(PKG_NAME)"
	@echo "  make build         - Build wheel + sdist into dist/"
	@echo "  make release       - Commit, tag, and push a release (wraps $(RELEASE_SCRIPT))"
	@echo "  make release-dry   - Dry-run release (no commit/tag/push)"
	@echo "  make clean         - Remove build artifacts"
	@echo "  make distclean     - clean + remove __pycache__"

install:
	$(PIP) install --user -e .

uninstall:
	$(PIP) uninstall -y $(PKG_NAME)

build:
	$(PIP) install --upgrade build
	$(PYTHON) -m build

release:
	@$(RELEASE_SCRIPT)

release-dry:
	@$(RELEASE_SCRIPT) --dry-run

clean:
	@echo "Cleaning build artifacts…"
	@rm -rf build/ dist/ .eggs/ *.egg-info

distclean: clean
	@find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	@find . -name "*.pyc" -delete -o -name "*.pyo" -delete