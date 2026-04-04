import argparse
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from app import GAME_DETAIL_CACHE_DIR, get_db_connection, _normalize_position


def normalize_name(value: str) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_suffix_name(first_name: str, last_name: str) -> str:
    return normalize_name(f"{first_name} {last_name}")


def choose_best_candidate(player_row: dict, candidates: List[dict]) -> Optional[dict]:
    if not candidates:
        return None

    db_team_nba_id = str(player_row.get("team_nba_id") or "").strip()
    db_jersey = str(player_row.get("jersey_number") or "").strip()
    db_position = str(player_row.get("position") or "").strip().upper()

    scored = []
    for candidate in candidates:
        score = 0
        reasons = []
        if db_team_nba_id and db_team_nba_id in candidate.get("team_nba_ids", set()):
            score += 5
            reasons.append("team")
        if db_jersey and db_jersey in candidate.get("jerseys", set()):
            score += 3
            reasons.append("jersey")
        if db_position and db_position in candidate.get("positions", set()):
            score += 2
            reasons.append("position")
        score += min(int(candidate.get("appearances", 0)), 5)
        reasons.append(f"appearances={candidate.get('appearances', 0)}")
        scored.append((score, candidate, reasons))

    scored.sort(key=lambda item: (item[0], item[1].get("appearances", 0)), reverse=True)
    if len(scored) == 1:
        best = dict(scored[0][1])
        best["score"] = scored[0][0]
        best["score_reasons"] = scored[0][2]
        return best

    top_score = scored[0][0]
    top = [item for item in scored if item[0] == top_score]
    if len(top) != 1:
        return None

    best = dict(top[0][1])
    best["score"] = top[0][0]
    best["score_reasons"] = top[0][2]
    return best


def scan_cache(cache_dir: Path) -> dict:
    name_to_candidates: Dict[str, Dict[str, dict]] = defaultdict(dict)
    bad_files = []
    games_scanned = 0

    for path in sorted(cache_dir.glob("*.json"), key=lambda p: p.name):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            game = payload.get("game", {}) or {}
            if not game:
                raise ValueError("Missing game payload")
            games_scanned += 1

            for team_key in ("homeTeam", "awayTeam"):
                team = game.get(team_key, {}) or {}
                nba_team_id = str(team.get("teamId") or "").strip()
                for player in team.get("players", []) or []:
                    nba_player_id = str(player.get("personId") or "").strip()
                    if not nba_player_id:
                        continue

                    first_name = str(player.get("firstName") or "").strip()
                    last_name = str(player.get("familyName") or "").strip()
                    full_name = str(player.get("name") or "").strip()
                    if not first_name and full_name:
                        parts = full_name.split()
                        first_name = parts[0] if parts else ""
                    if not last_name and full_name:
                        parts = full_name.split()
                        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

                    normalized = normalize_suffix_name(first_name or full_name, last_name)
                    if not normalized:
                        continue

                    entry = name_to_candidates[normalized].get(nba_player_id)
                    if entry is None:
                        entry = {
                            "nba_player_id": nba_player_id,
                            "display_name": full_name or f"{first_name} {last_name}".strip(),
                            "team_nba_ids": set(),
                            "jerseys": set(),
                            "positions": set(),
                            "appearances": 0,
                            "sample_files": [],
                        }
                        name_to_candidates[normalized][nba_player_id] = entry

                    entry["team_nba_ids"].add(nba_team_id)
                    jersey = str(player.get("jerseyNum") or "").strip()
                    if jersey:
                        entry["jerseys"].add(jersey)
                    position = _normalize_position(player.get("position"))
                    if position:
                        entry["positions"].add(position)
                    entry["appearances"] += 1
                    if len(entry["sample_files"]) < 3:
                        entry["sample_files"].append(path.name)
        except Exception as exc:
            bad_files.append({"file": path.name, "error": str(exc)})

    # Convert set values to sorted lists for JSON/report friendliness
    output_candidates = {}
    for norm_name, candidates in name_to_candidates.items():
        output_candidates[norm_name] = {}
        for nba_id, candidate in candidates.items():
            output_candidates[norm_name][nba_id] = {
                **candidate,
                "team_nba_ids": sorted(candidate["team_nba_ids"]),
                "jerseys": sorted(candidate["jerseys"]),
                "positions": sorted(candidate["positions"]),
            }

    return {
        "games_scanned": games_scanned,
        "bad_files": bad_files,
        "name_to_candidates": output_candidates,
    }


def load_players(cursor, only_missing_stats: bool = False) -> List[dict]:
    sql = """
        SELECT
            p.player_id,
            p.nba_player_id,
            p.team_id,
            t.nba_team_id AS team_nba_id,
            t.abbreviation AS team_abbreviation,
            p.first_name,
            p.last_name,
            p.position,
            p.jersey_number
        FROM players p
        LEFT JOIN teams t ON t.team_id = p.team_id
        LEFT JOIN player_regular_season_stats s ON s.player_id = p.player_id
    """
    where = []
    if only_missing_stats:
        where.append("s.player_id IS NULL")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY p.last_name, p.first_name"
    cursor.execute(sql)
    return cursor.fetchall() or []


def audit_players(players_rows: List[dict], cache_index: dict) -> dict:
    candidates_by_name = cache_index["name_to_candidates"]
    ok = []
    repaired_candidates = []
    ambiguous = []
    unresolved = []
    suspicious = []

    for row in players_rows:
        full_name = f"{row.get('first_name') or ''} {row.get('last_name') or ''}".strip()
        normalized = normalize_name(full_name)
        current_id = str(row.get("nba_player_id") or "").strip()
        name_candidates_map = candidates_by_name.get(normalized, {})
        name_candidates = [
            {
                **candidate,
                "team_nba_ids": set(candidate.get("team_nba_ids") or []),
                "jerseys": set(candidate.get("jerseys") or []),
                "positions": set(candidate.get("positions") or []),
            }
            for candidate in name_candidates_map.values()
        ]

        base_info = {
            "player_id": row.get("player_id"),
            "current_nba_player_id": current_id,
            "player_name": full_name,
            "team_abbreviation": row.get("team_abbreviation"),
            "team_nba_id": row.get("team_nba_id"),
            "position": row.get("position"),
            "jersey_number": row.get("jersey_number"),
        }

        if current_id and current_id in name_candidates_map:
            ok.append({**base_info, "status": "ok_cache_match"})
            continue

        if not name_candidates:
            unresolved.append({**base_info, "status": "no_cache_name_match"})
            if not current_id or len(current_id) < 5:
                suspicious.append({**base_info, "reason": "no_cache_name_match_and_short_or_missing_id"})
            continue

        best = choose_best_candidate(row, name_candidates)
        if best is None:
            ambiguous.append({
                **base_info,
                "status": "ambiguous_candidates",
                "candidates": [
                    {
                        "nba_player_id": candidate.get("nba_player_id"),
                        "display_name": candidate.get("display_name"),
                        "team_nba_ids": sorted(candidate.get("team_nba_ids") or []),
                        "jerseys": sorted(candidate.get("jerseys") or []),
                        "positions": sorted(candidate.get("positions") or []),
                        "appearances": candidate.get("appearances"),
                    }
                    for candidate in name_candidates
                ],
            })
            continue

        repaired_candidates.append({
            **base_info,
            "status": "repair_candidate",
            "suggested_nba_player_id": best.get("nba_player_id"),
            "candidate_display_name": best.get("display_name"),
            "candidate_team_nba_ids": sorted(best.get("team_nba_ids") or []),
            "candidate_jerseys": sorted(best.get("jerseys") or []),
            "candidate_positions": sorted(best.get("positions") or []),
            "candidate_appearances": best.get("appearances"),
            "score": best.get("score"),
            "score_reasons": best.get("score_reasons"),
            "sample_files": best.get("sample_files"),
        })

    return {
        "ok": ok,
        "repair_candidates": repaired_candidates,
        "ambiguous": ambiguous,
        "unresolved": unresolved,
        "suspicious": suspicious,
    }


def apply_repairs(connection, repair_candidates: List[dict]) -> dict:
    if not repair_candidates:
        return {"updated": 0, "conflicts": [], "applied": []}

    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT player_id, nba_player_id FROM players WHERE nba_player_id IS NOT NULL")
    rows = cursor.fetchall() or []
    existing_id_to_player = {str(row.get("nba_player_id") or "").strip(): row.get("player_id") for row in rows}

    updated = 0
    conflicts = []
    applied = []

    for item in repair_candidates:
        player_id = int(item["player_id"])
        target_id = str(item.get("suggested_nba_player_id") or "").strip()
        if not target_id:
            continue

        owner = existing_id_to_player.get(target_id)
        if owner and int(owner) != player_id:
            conflicts.append({
                "player_id": player_id,
                "player_name": item.get("player_name"),
                "suggested_nba_player_id": target_id,
                "conflict_player_id": owner,
            })
            continue

        cursor.execute(
            "UPDATE players SET nba_player_id = %s WHERE player_id = %s",
            (target_id, player_id),
        )
        updated += 1
        existing_id_to_player[target_id] = player_id
        applied.append({
            "player_id": player_id,
            "player_name": item.get("player_name"),
            "old_nba_player_id": item.get("current_nba_player_id"),
            "new_nba_player_id": target_id,
        })

    connection.commit()
    return {"updated": updated, "conflicts": conflicts, "applied": applied}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and optionally repair bad nba_player_id values using local cached NBA boxscores.")
    parser.add_argument("--apply", action="store_true", help="Apply suggested nba_player_id repairs to the players table.")
    parser.add_argument("--only-missing-stats", action="store_true", help="Audit only players who currently have no row in player_regular_season_stats.")
    parser.add_argument("--player-ids", nargs="*", type=int, help="Limit the audit to specific internal player_id values.")
    parser.add_argument("--report", default="database/player_id_audit_report.json", help="Path to write the audit report JSON.")
    args = parser.parse_args()

    cache_dir = Path(GAME_DETAIL_CACHE_DIR)
    cache_index = scan_cache(cache_dir)

    connection = get_db_connection()
    if not connection:
        raise RuntimeError("Database connection failed")

    try:
        cursor = connection.cursor(dictionary=True)
        players_rows = load_players(cursor, only_missing_stats=args.only_missing_stats)
        if args.player_ids:
            wanted = set(args.player_ids)
            players_rows = [row for row in players_rows if int(row.get("player_id")) in wanted]

        audit = audit_players(players_rows, cache_index)
        apply_result = {"updated": 0, "conflicts": [], "applied": []}
        if args.apply:
            apply_result = apply_repairs(connection, audit["repair_candidates"])

        report = {
            "games_scanned": cache_index["games_scanned"],
            "bad_cache_files": cache_index["bad_files"],
            "players_checked": len(players_rows),
            "ok_count": len(audit["ok"]),
            "repair_candidate_count": len(audit["repair_candidates"]),
            "ambiguous_count": len(audit["ambiguous"]),
            "unresolved_count": len(audit["unresolved"]),
            "suspicious_count": len(audit["suspicious"]),
            "apply_requested": bool(args.apply),
            "apply_result": apply_result,
            **audit,
        }

        report_path = Path(args.report)
        if not report_path.is_absolute():
            report_path = Path(__file__).resolve().parent.parent / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        print(json.dumps({
            "games_scanned": report["games_scanned"],
            "players_checked": report["players_checked"],
            "ok_count": report["ok_count"],
            "repair_candidate_count": report["repair_candidate_count"],
            "ambiguous_count": report["ambiguous_count"],
            "unresolved_count": report["unresolved_count"],
            "suspicious_count": report["suspicious_count"],
            "apply_requested": report["apply_requested"],
            "updated": apply_result.get("updated", 0),
            "conflicts": len(apply_result.get("conflicts", [])),
            "report_path": str(report_path),
        }, indent=2))

        if audit["repair_candidates"]:
            print("\nRepair candidates:")
            for item in audit["repair_candidates"]:
                print(
                    f"- {item['player_name']} | player_id={item['player_id']} | current={item['current_nba_player_id']} -> suggested={item['suggested_nba_player_id']}"
                )
        if audit["unresolved"]:
            print("\nUnresolved (no cache name match):")
            for item in audit["unresolved"][:25]:
                print(
                    f"- {item['player_name']} | player_id={item['player_id']} | current={item['current_nba_player_id']} | team={item.get('team_abbreviation')}"
                )
        if audit["ambiguous"]:
            print("\nAmbiguous matches:")
            for item in audit["ambiguous"][:25]:
                print(
                    f"- {item['player_name']} | player_id={item['player_id']} | current={item['current_nba_player_id']} | candidates={len(item.get('candidates') or [])}"
                )
        if apply_result.get("conflicts"):
            print("\nSkipped due to ID conflicts:")
            for item in apply_result["conflicts"][:25]:
                print(
                    f"- {item['player_name']} | player_id={item['player_id']} | suggested={item['suggested_nba_player_id']} already belongs to player_id={item['conflict_player_id']}"
                )
    finally:
        connection.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
