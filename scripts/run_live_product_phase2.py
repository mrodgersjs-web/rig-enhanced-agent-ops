"""Phase 2 live wiring CLI (Product Room) — read-only ARMS sweep + 6-harness bridge bundle.

Thin wrapper: all logic lives in ``src/robonuggets_ops/phase2_live_wiring``.

Hard bounds (invariants of this run):
- ``workforce.db`` is opened ``mode=ro`` with ``PRAGMA query_only=1`` and never
  written — no schedule, cron or launchd entry is created, armed or mutated;
- exit 0 means the sweep completed; blocked armings are FINDINGS (expected when
  schedules lack pre-arm evidence), not errors;
- bridges are thin pointers + invariants; no doctrine prose is copied.

stdlib only — no HTTP client, no sockets, no subprocess.
"""

from __future__ import annotations

import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from robonuggets_ops.phase2_live_wiring.live_wiring import (  # noqa: E402
    main,
    render_summary,
    run_arms,
    run_bridges,
    schedule_row_to_routine,
)

# Exact Python interfaces of this CLI (ticket #9 D1): re-exported for tests.
__all__ = ["main", "schedule_row_to_routine", "run_arms", "run_bridges", "render_summary"]

if __name__ == "__main__":
    sys.exit(main())
