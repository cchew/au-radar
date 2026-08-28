"""Deprecated shim. Use the `au-radar` console command instead:

    au-radar --help
    au-radar --dry-run
    au-radar --services none --agent-tasks passport_agent --contact you@example.org

Equivalent to `python -m au_radar`. Kept so existing invocations keep working;
all logic now lives in `au_radar.cli`.
"""
import sys

from au_radar.cli import main

if __name__ == "__main__":
    print(
        "note: scripts/run_live_collection.py is deprecated — use `au-radar` (or "
        "`python -m au_radar`).\n",
        file=sys.stderr,
    )
    sys.exit(main())
