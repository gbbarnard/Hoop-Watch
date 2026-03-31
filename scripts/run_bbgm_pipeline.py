#!/usr/bin/env python3
"""
run_bbgm_pipeline.py

One-command runner for the "old way" pipeline:
1) populate_rosters_bbgm.py (no stats.nba.com)
2) fix_missing_headshots.py (tries to match any remaining names)

Usage:
  py .\run_bbgm_pipeline.py --wipe-all
"""

import argparse
import subprocess
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wipe-all", action="store_true")
    ap.add_argument("--include-unmatched", action="store_true")
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()

    cmd1 = [sys.executable, str(THIS_DIR / "populate_rosters_bbgm.py")]
    if args.wipe_all:
        cmd1.append("--wipe-all")
    if args.include_unmatched:
        cmd1.append("--include-unmatched")
    if args.only:
        cmd1.extend(["--only", *args.only])

    print("Running:", " ".join(cmd1))
    subprocess.check_call(cmd1)

    cmd2 = [sys.executable, str(THIS_DIR / "fix_missing_headshots.py")]
    print("Running:", " ".join(cmd2))
    subprocess.check_call(cmd2)

    print("\nAll done.")

if __name__ == "__main__":
    main()

