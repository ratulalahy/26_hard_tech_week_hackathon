"""Stage 3 T12 step 3 (final review B4): the test cutoff F_test from completeness counts.

    cd lab && uv run python scripts/completeness_cutoff.py --log ../docs/evidence/completeness-<date>.jsonl

Runs `gridpilot.completeness.test_cutoff` on `$GRIDPILOT_DATA_DIR`: counts and timestamps only,
never a sealed value (AGENTS.md completeness exception). Every call appends one line to the log;
`scripts/write_freeze.py` reads F_test, D and the per-series last rows from the committed log.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gridpilot.completeness import test_cutoff


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--log", required=True, help="the completeness log (JSONL, appended)")
    a = p.parse_args(argv)
    rec = test_cutoff(Path(a.log).resolve())
    print(json.dumps(rec, indent=1, sort_keys=True))
    print(f"\nD = {rec['D']}   F_test = {rec['test_F']}   (logged to {a.log})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
