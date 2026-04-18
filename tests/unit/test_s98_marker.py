"""
Test for S98 PlanPhaseTest.
Creates /tmp/s98-marker.txt with content "phase 4 ok" and verifies it.
"""
import pathlib


def test_s98_marker_file():
    """Create the marker file and assert its content."""
    marker_path = pathlib.Path("/tmp/s98-marker.txt")
    expected_content = "phase 4 ok"

    # Write the marker file (overwrites if already exists)
    marker_path.write_text(expected_content, encoding="utf-8")

    # Verify file exists
    assert marker_path.exists(), f"Marker file {marker_path} not created"

    # Verify content matches
    actual_content = marker_path.read_text(encoding="utf-8")
    assert actual_content == expected_content, (
        f"Marker file content mismatch.\n"
        f"Expected: {expected_content!r}\n"
        f"Actual: {actual_content!r}"
    )
    # File is left intentionally as proof of step completion