#!/usr/bin/env python3
"""
populate_rosters_bbgm.py

"Old way" roster loader that DOES NOT hit stats.nba.com.

It downloads a community roster JSON (BBGM) from GitHub, maps teams by abbreviation,
and inserts players into your MySQL `players` table.

By default it ONLY inserts players that can be matched to a real NBA playerId
(using nba_api's built-in static player list). This removes the "fake" filler names.

Matched players get a real NBA headshot URL:
  https://cdn.nba.com/headshots/nba/latest/260x190/<playerId>.png

Unmatched players (optional) use your placeholder:
  /static/Headshots/placeholder.png

Usage:
  py .\populate_rosters_bbgm.py --wipe-all
  py .\populate_rosters_bbgm.py --wipe-all --include-unmatched
  py .\populate_rosters_bbgm.py --only GSW BOS LAL

Notes:
- This avoids NBA Stats blocks.
- This is not guaranteed to be a perfect up-to-the-minute roster; it's a dataset.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

import mysql.connector
import requests
from nba_api.stats.static import players as nba_players


# ----------------------------
# EDIT THESE VALUES IF NEEDED
# ----------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "IzzyPop2025!",
    "database": "hoopwatch",
}

ROSTER_URL = "https://raw.githubusercontent.com/alexnoob/BasketBall-GM-Rosters/master/2025-26.NBA.Roster.json"

NBA_HEADSHOT_TEMPLATE = "https://cdn.nba.com/headshots/nba/latest/260x190/{pid}.png"
PLACEHOLDER = "/static/Headshots/placeholder.png"

SUFFIXES = {"JR", "SR", "II", "III", "IV", "V"}


# ----------------------------
# Helpers
# ----------------------------
def strip_accents(s: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", s or "")
        if not unicodedata.combining(ch)
    )


def clean_name(s: str) -> str:
    s = strip_accents(s or "")
    s = s.replace(".", " ").replace("-", " ").replace("'", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def remove_suffix(last_name: str) -> str:
    parts = clean_name(last_name).split()
    parts = [p for p in parts if p.upper() not in SUFFIXES]
    return " ".join(parts).strip()


def norm_full_name(first: str, last: str) -> str:
    return (clean_name(first) + " " + remove_suffix(last)).strip().lower()


def safe_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        s = str(v).strip()
        if s == "" or s.lower() == "nan":
            return None
        return int(float(s))
    except Exception:
        return None


def build_nba_name_index() -> Dict[str, str]:
    """normalized full_name -> nba playerId (prefer active when duplicates)"""
    index: Dict[str, Tuple[str, bool]] = {}
    for p in nba_players.get_players():
        full = clean_name(p.get("full_name", "")).lower()
        if not full:
            continue
        pid = str(p.get("id"))
        active = bool(p.get("is_active"))
        if full not in index or (index[full][1] is False and active is True):
            index[full] = (pid, active)
    return {k: v[0] for k, v in index.items()}


@dataclass(frozen=True)
class DBTeam:
    team_id: int
    abbr: str
    name: str


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wipe-all", action="store_true", help="DELETE all players before inserting")
    ap.add_argument("--include-unmatched", action="store_true", help="Keep unmatched names (placeholder headshots)")
    ap.add_argument("--only", nargs="*", help="Only these team abbreviations (e.g., --only GSW BOS)")
    ap.add_argument("--url", default=ROSTER_URL, help="Roster JSON URL")
    args = ap.parse_args()

    print("Downloading roster JSON...")
    r = requests.get(args.url, timeout=60)
    r.raise_for_status()
    data = r.json()

    teams_json = data.get("teams", [])
    players_json = data.get("players", [])
    if not teams_json or not players_json:
        raise RuntimeError("Roster JSON missing 'teams' or 'players' list.")

    # Build BBGM tid -> team abbreviation mapping
    tid_to_abbr: Dict[int, str] = {}
    for t in teams_json:
        tid = t.get("tid")
        abbr = (t.get("abbrev") or t.get("abbreviation") or "").upper().strip()
        if tid is None or not abbr:
            continue
        tid_to_abbr[int(tid)] = abbr

    # Load DB teams
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT team_id, abbreviation, name FROM teams")
    db_rows = cur.fetchall()
    db_by_abbr: Dict[str, DBTeam] = {row["abbreviation"].upper(): DBTeam(int(row["team_id"]), row["abbreviation"].upper(), row["name"])
                                     for row in db_rows}

    if args.only:
        only = {x.upper() for x in args.only}
        db_by_abbr = {k: v for k, v in db_by_abbr.items() if k in only}

    print("DB teams to fill:", len(db_by_abbr))

    # NBA name index (no network)
    name_to_nba_id = build_nba_name_index()
    used_nba_ids = set()

    if args.wipe_all:
        print("Wiping ALL players...")
        cur.execute("SET SQL_SAFE_UPDATES=0;")
        cur.execute("DELETE FROM players;")
        conn.commit()

    inserted = 0
    unmatched = 0
    skipped_fake = 0

    # Group BBGM players by tid for faster delete/insert
    by_tid: Dict[int, List[dict]] = {}
    for p in players_json:
        tid = p.get("tid")
        if tid is None:
            continue
        tid = int(tid)
        if tid < 0:
            continue
        by_tid.setdefault(tid, []).append(p)

    # For each DB team, find matching BBGM tid(s) by abbreviation
    abbr_to_tids: Dict[str, List[int]] = {}
    for tid, abbr in tid_to_abbr.items():
        if abbr in db_by_abbr:
            abbr_to_tids.setdefault(abbr, []).append(tid)

    for abbr, db_team in db_by_abbr.items():
        tids = abbr_to_tids.get(abbr, [])
        if not tids:
            print(f"Skipping {abbr}: no matching team in roster dataset")
            continue

        # Replace ONLY this team's players
        cur.execute("DELETE FROM players WHERE team_id=%s", (db_team.team_id,))

        team_players = []
        for tid in tids:
            team_players.extend(by_tid.get(tid, []))

        # Insert players
        for p in team_players:
            first = p.get("firstName") or ""
            last = p.get("lastName") or ""
            if not first and not last:
                full = p.get("name") or p.get("fullName") or ""
                parts = clean_name(full).split()
                first = parts[0] if parts else ""
                last = " ".join(parts[1:]) if len(parts) > 1 else ""

            full_norm = norm_full_name(first, last)
            nba_id = name_to_nba_id.get(full_norm)

            # Only keep real NBA names unless include_unmatched is set
            if not nba_id and not args.include_unmatched:
                skipped_fake += 1
                continue

            # Avoid UNIQUE conflicts on nba_player_id
            if nba_id and nba_id in used_nba_ids:
                nba_id = None  # keep the row but without nba_player_id
            if nba_id:
                used_nba_ids.add(nba_id)

            headshot_url = NBA_HEADSHOT_TEMPLATE.format(pid=nba_id) if nba_id else PLACEHOLDER
            if not nba_id:
                unmatched += 1

            pos = p.get("pos")
            if not pos and isinstance(p.get("ratings"), list) and p["ratings"]:
                pos = p["ratings"][-1].get("pos")
            pos = (str(pos).upper().strip() if pos else None)
            if pos not in {"PG", "SG", "SF", "PF", "C", "G", "F"}:
                # some rosters store weird values; ignore
                pos = None

            jersey = safe_int(p.get("jersey"))
            height_in = safe_int(p.get("hgt"))  # BBGM usually stores inches
            weight_lb = safe_int(p.get("weight"))

            cur.execute(
                """
                INSERT INTO players
                  (nba_player_id, team_id, first_name, last_name, position,
                   jersey_number, height_in, weight_lb, birth_date, headshot_url, is_active)
                VALUES
                  (%s,%s,%s,%s,%s,%s,%s,%s,NULL,%s,TRUE)
                """,
                (nba_id, db_team.team_id, first, last, pos, jersey, height_in, weight_lb, headshot_url)
            )
            inserted += 1

        conn.commit()
        print(f"{abbr}: inserted {inserted} total so far")

    cur.close()
    conn.close()

    print("\nDONE")
    print("Inserted players:", inserted)
    print("Unmatched (placeholder):", unmatched)
    if not args.include_unmatched:
        print("Skipped (unmatched filtered out):", skipped_fake)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
