# Flatpack Test Suite

This test suite covers the core functionality of flatpack.

## Structure

- `test_pathspec_matching.py` — gitignore-style matching via pathspec (exercise decide_redaction)
- `test_decide_redaction.py` — unit tests for `decide_redaction` (order/negation semantics)
- `test_header_and_plan_output.py` — checks header, tree, and plan output formatting
- `test_collect_entries_integration.py` — integration test with a temporary Git repo (marked `@integration`)

## Running tests

Run all tests:

```bash
pytest
```

Run only fast (non-integration) tests:

```bash
pytest -m "not integration"
```

Run only integration tests:

```bash
pytest -m integration
```
