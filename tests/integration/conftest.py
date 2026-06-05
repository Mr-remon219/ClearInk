"""Integration-test-only fixtures.

The root ``tests/conftest.py`` fixtures are inherited automatically.
This file adds isolation that should only apply to integration tests.
"""

from __future__ import annotations

# Intentionally empty — each integration test explicitly requests the
# fixtures it needs (tmp_data_dir, reset_global_state, mock_anthropic).
# Forcing autouse on all integration tests causes cross-test contamination
# when module-level cached config paths are involved.
