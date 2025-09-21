# Makefile (repo root)
# Common tasks for devtools

PYTHON   ?= python3
PIP      ?= $(PYTHON) -m pip
PKG_NAME ?= devtools-lark
RELEASE_SCRIPT := scripts/release.sh

# Pytest options
PYTEST    ?= $(PYTHON) -m pytest
PYTEST_OPTS ?=
TEST_PATH ?= tests

.PHONY: help install install-dev uninstall build release release-dry clean distclean \
        test test-all test-integration

help:
	@echo "Targets:"
	@echo "  make install         - Editable install (pip install -e . --user)"
	@echo "  make install-dev     - Editable install + dev deps (pip install -e .[dev] --user)"
	@echo "  make uninstall       - Uninstall $(PKG_NAME)"
	@echo "  make build           - Build wheel + sdist into dist/"
	@echo "  make test            - Run tests excluding @integration (default fast suite)"
	@echo "  make test-all        - Run entire test suite (includes @integration)"
	@echo "  make test-integration- Only @integration tests"
	@echo "  make release         - Commit, tag, and push a release (wraps $(RELEASE_SCRIPT))"
	@echo "  make release-dry     - Dry-run release (no commit/tag/push)"
	@echo "  make clean           - Remove build artifacts"
	@echo "  make distclean       - clean + remove __pycache__"

install:
	$(PIP) install --user -e .

install-dev:
	$(PIP) install --user -e .[dev]

uninstall:
	$(PIP) uninstall -y $(PKG_NAME)

build:
	$(PIP) install --upgrade build
	$(PYTHON) -m build

# --- Tests ---

# Fast suite: everything except tests marked with @pytest.mark.integration
test:
	$(PYTEST) -m "not integration" $(PYTEST_OPTS) $(TEST_PATH)

# Full suite, including integration tests
test-all:
	$(PYTEST) $(PYTEST_OPTS) $(TEST_PATH)

# Only the integration tests
test-integration:
	$(PYTEST) -m "integration" $(PYTEST_OPTS) $(TEST_PATH)

# --- Release ---

release:
	@$(RELEASE_SCRIPT)

release-dry:
	@$(RELEASE_SCRIPT) --dry-run

# --- Cleanup ---

clean:
	@echo "Cleaning build artifacts…"
	@rm -rf build/ dist/ .eggs/ *.egg-info .pytest_tmp

distclean: clean
	@find . -name "__pycache__" -type d -prune -exec rm -rf {} +
	@find . -name "*.pyc" -delete -o -name "*.pyo" -delete