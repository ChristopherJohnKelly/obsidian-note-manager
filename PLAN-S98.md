# PLAN-S98 — PlanPhaseTest

## Test sequence
1. `test_s98_marker_file`: creates `/tmp/s98-marker.txt` with content "phase 4 ok", then reads it back and asserts the file exists and content matches.
   - Uses pytest's `tmp_path` fixture to create a temporary subdirectory under `/tmp` to avoid race conditions.
   - Cleans up the file after test completion.

## Implementation sequence
1. **Create test file** `tests/unit/test_s98_marker.py` with a single test function `test_s98_marker_file`.
   - Import `pytest`, `pathlib.Path`.
   - Use `tmp_path` fixture to create a unique subdirectory under `/tmp`.
   - Write the marker file via `Path.write_text()`.
   - Read back and assert content.
   - Add teardown to remove the file (or rely on `tmp_path` cleanup).
2. **Run the test** via `pytest tests/unit/test_s98_marker.py -xvs` to verify it passes.
3. **Run the full test suite** to ensure no regressions.

## Known risks
- **File permissions**: `/tmp` may have restrictive permissions (noexec, no write). Mitigation: use `tmp_path` which creates a temporary directory under `/tmp` with user permissions; if that fails, fall back to a user‑writable location and log a warning.
- **Race condition**: multiple concurrent test runs could overwrite the same path. Mitigation: `tmp_path` guarantees a unique per‑test directory; we can place the marker file inside that directory and symlink to `/tmp/s98-marker.txt` (or ignore the exact‑path requirement, as the spec’s “only touches /tmp” is satisfied). Since the spec requires the exact path `/tmp/s98-marker.txt`, we will create the file directly there but ensure uniqueness by appending a PID or timestamp to the filename? The spec says the file must exist at that exact path for acceptance; we will assume no concurrent runs.
- **Leftover files**: If the test fails before cleanup, the marker file may remain. Mitigation: wrap the test in a try/finally block that removes the file if it exists.
- **Test discovery**: The new test file must be discovered by pytest. Ensure `tests/unit/__init__.py` exists (it does). No risk.

## External dependencies
- Context7: No.