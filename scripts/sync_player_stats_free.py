import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from app import (
    GAME_DETAIL_CACHE_DIR,
    _fetch_boxscore_payload,
    _game_detail_cache_path,
    _normalize_position,
    _parse_iso_duration_seconds,
    _save_cached_boxscore_payload,
    _sync_completed_game_details,
    _current_nba_season_label,
    get_db_connection,
)

SEASON_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS player_regular_season_stats (
    player_id INT PRIMARY KEY,
    season_label VARCHAR(16) NOT NULL DEFAULT '',
    games_played INT NOT NULL DEFAULT 0,
    games_started INT NOT NULL DEFAULT 0,
    total_seconds BIGINT NOT NULL DEFAULT 0,
    total_points INT NOT NULL DEFAULT 0,
    total_rebounds INT NOT NULL DEFAULT 0,
    total_assists INT NOT NULL DEFAULT 0,
    total_blocks INT NOT NULL DEFAULT 0,
    total_steals INT NOT NULL DEFAULT 0,
    total_turnovers INT NOT NULL DEFAULT 0,
    total_fouls INT NOT NULL DEFAULT 0,
    total_fgm INT NOT NULL DEFAULT 0,
    total_fga INT NOT NULL DEFAULT 0,
    total_fg3m INT NOT NULL DEFAULT 0,
    total_fg3a INT NOT NULL DEFAULT 0,
    total_ftm INT NOT NULL DEFAULT 0,
    total_fta INT NOT NULL DEFAULT 0,
    min_per_game DECIMAL(6,2) NOT NULL DEFAULT 0,
    pts_per_game DECIMAL(6,2) NOT NULL DEFAULT 0,
    reb_per_game DECIMAL(6,2) NOT NULL DEFAULT 0,
    ast_per_game DECIMAL(6,2) NOT NULL DEFAULT 0,
    blk_per_game DECIMAL(6,2) NOT NULL DEFAULT 0,
    stl_per_game DECIMAL(6,2) NOT NULL DEFAULT 0,
    pf_per_game DECIMAL(6,2) NOT NULL DEFAULT 0,
    tov_per_game DECIMAL(6,2) NOT NULL DEFAULT 0,
    fg_pct DECIMAL(6,2) NOT NULL DEFAULT 0,
    fg3_pct DECIMAL(6,2) NOT NULL DEFAULT 0,
    ft_pct DECIMAL(6,2) NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_player_regular_season_stats_player
      FOREIGN KEY (player_id) REFERENCES players(player_id)
      ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB
"""

SEASON_TABLE_COLUMNS = {
    "player_id": "INT NOT NULL",
    "season_label": "VARCHAR(16) NOT NULL DEFAULT ''",
    "games_played": "INT NOT NULL DEFAULT 0",
    "games_started": "INT NOT NULL DEFAULT 0",
    "total_seconds": "BIGINT NOT NULL DEFAULT 0",
    "total_points": "INT NOT NULL DEFAULT 0",
    "total_rebounds": "INT NOT NULL DEFAULT 0",
    "total_assists": "INT NOT NULL DEFAULT 0",
    "total_blocks": "INT NOT NULL DEFAULT 0",
    "total_steals": "INT NOT NULL DEFAULT 0",
    "total_turnovers": "INT NOT NULL DEFAULT 0",
    "total_fouls": "INT NOT NULL DEFAULT 0",
    "total_fgm": "INT NOT NULL DEFAULT 0",
    "total_fga": "INT NOT NULL DEFAULT 0",
    "total_fg3m": "INT NOT NULL DEFAULT 0",
    "total_fg3a": "INT NOT NULL DEFAULT 0",
    "total_ftm": "INT NOT NULL DEFAULT 0",
    "total_fta": "INT NOT NULL DEFAULT 0",
    "min_per_game": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "pts_per_game": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "reb_per_game": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "ast_per_game": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "blk_per_game": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "stl_per_game": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "pf_per_game": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "tov_per_game": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "fg_pct": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "fg3_pct": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "ft_pct": "DECIMAL(6,2) NOT NULL DEFAULT 0",
    "updated_at": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP",
}


def safe_int(value, default: Optional[int] = 0):
    try:
        if value in (None, "", " "):
            return default
        return int(float(value))
    except Exception:
        return default


def season_label_from_game(game: dict) -> str:
    game_time_utc = str((game or {}).get("gameTimeUTC") or "").strip()
    if len(game_time_utc) >= 10:
        year = int(game_time_utc[:4])
        month = int(game_time_utc[5:7])
    else:
        from datetime import datetime
        now = datetime.utcnow()
        year = now.year
        month = now.month
    start_year = year if month >= 10 else year - 1
    end_year = start_year + 1
    return f"{start_year}-{str(end_year)[-2:]}"


def ensure_regular_season_stats_table(cursor, connection) -> None:
    cursor.execute(SEASON_TABLE_SQL)
    connection.commit()

    cursor.execute("SHOW COLUMNS FROM player_regular_season_stats")
    rows = cursor.fetchall() or []
    existing = {row.get("Field") if isinstance(row, dict) else row[0] for row in rows}

    for column_name, ddl in SEASON_TABLE_COLUMNS.items():
        if column_name in existing:
            continue
        cursor.execute(f"ALTER TABLE player_regular_season_stats ADD COLUMN {column_name} {ddl}")

    cursor.execute("SHOW INDEX FROM player_regular_season_stats WHERE Key_name = 'PRIMARY'")
    if not (cursor.fetchall() or []):
        cursor.execute("ALTER TABLE player_regular_season_stats ADD PRIMARY KEY (player_id)")

    connection.commit()


def iter_cache_files(cache_dir: Path) -> Iterable[Path]:
    return sorted(cache_dir.glob("*.json"), key=lambda path: path.name)


def detect_bad_cache_files(cache_dir: Path) -> List[dict]:
    bad_files: List[dict] = []
    for path in iter_cache_files(cache_dir):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or not payload.get("game"):
                raise ValueError("Missing game payload")
        except Exception as exc:
            bad_files.append({"file": path.name, "error": str(exc)})
    return bad_files


def repair_bad_cache_files(cache_dir: Path, bad_files: List[dict]) -> dict:
    repaired = 0
    failed: List[dict] = []
    request_cache: Dict[str, dict] = {}

    for item in bad_files:
        filename = str(item.get("file") or "").strip()
        game_id = Path(filename).stem
        if not game_id:
            continue
        try:
            payload = _fetch_boxscore_payload(game_id, request_cache)
            if not payload or not payload.get("game"):
                raise RuntimeError("Boxscore payload was empty")
            _save_cached_boxscore_payload(game_id, payload)
            repaired += 1
        except Exception as exc:
            failed.append({"game_id": game_id, "error": str(exc)})

    return {
        "requested": len(bad_files),
        "repaired": repaired,
        "failed": failed,
    }


def load_target_player_ids(cursor, only_missing: bool, player_ids: Optional[Set[int]], current_team_only: bool) -> Set[int]:
    where = []
    params: List[object] = []

    if current_team_only:
        where.append("p.team_id IS NOT NULL")
    if only_missing:
        where.append("s.player_id IS NULL")
    if player_ids:
        placeholders = ", ".join(["%s"] * len(player_ids))
        where.append(f"p.player_id IN ({placeholders})")
        params.extend(sorted(player_ids))

    sql = """
        SELECT p.player_id
        FROM players p
        LEFT JOIN player_regular_season_stats s ON s.player_id = p.player_id
    """
    if where:
        sql += " WHERE " + " AND ".join(where)

    cursor.execute(sql, tuple(params))
    rows = cursor.fetchall() or []
    ids = set()
    for row in rows:
        if isinstance(row, dict):
            ids.add(int(row.get("player_id")))
        else:
            ids.add(int(row[0]))
    return ids


def aggregate_from_cache(cache_dir: Path, target_internal_ids: Optional[Set[int]] = None):
    aggregated = defaultdict(lambda: {
        "games_played": 0,
        "games_started": 0,
        "total_seconds": 0,
        "total_points": 0,
        "total_rebounds": 0,
        "total_assists": 0,
        "total_blocks": 0,
        "total_steals": 0,
        "total_turnovers": 0,
        "total_fouls": 0,
        "total_fgm": 0,
        "total_fga": 0,
        "total_fg3m": 0,
        "total_fg3a": 0,
        "total_ftm": 0,
        "total_fta": 0,
        "season_label": "",
    })
    player_info = {}
    seen_game_player: Set[Tuple[str, str]] = set()
    games_scanned = 0
    bad_files = []

    target_nba_ids: Optional[Set[str]] = None
    existing_player_meta: Dict[str, int] = {}
    if target_internal_ids is not None:
        connection = get_db_connection()
        if not connection:
            raise RuntimeError("Database connection failed")
        try:
            cursor = connection.cursor(dictionary=True)
            placeholders = ", ".join(["%s"] * len(target_internal_ids)) if target_internal_ids else ""
            if target_internal_ids:
                cursor.execute(
                    f"SELECT player_id, nba_player_id FROM players WHERE player_id IN ({placeholders})",
                    tuple(sorted(target_internal_ids)),
                )
                rows = cursor.fetchall() or []
                target_nba_ids = set()
                for row in rows:
                    nba_id = str(row.get("nba_player_id") or "").strip()
                    if nba_id:
                        target_nba_ids.add(nba_id)
                        existing_player_meta[nba_id] = int(row.get("player_id"))
            else:
                target_nba_ids = set()
        finally:
            connection.close()

    for path in iter_cache_files(cache_dir):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            game = payload.get("game", {}) or {}
            season_label = season_label_from_game(game)
            games_scanned += 1

            for team_key in ("homeTeam", "awayTeam"):
                team = game.get(team_key, {}) or {}
                nba_team_id = str(team.get("teamId") or "").strip()
                for player in team.get("players", []) or []:
                    nba_player_id = str(player.get("personId") or "").strip()
                    if not nba_player_id:
                        continue
                    if target_nba_ids is not None and nba_player_id not in target_nba_ids:
                        continue

                    first_name = str(player.get("firstName") or "").strip()
                    last_name = str(player.get("familyName") or "").strip()
                    name = str(player.get("name") or "").strip()
                    if not first_name and name:
                        parts = name.split()
                        first_name = parts[0] if parts else ""
                    if not last_name and name:
                        parts = name.split()
                        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

                    player_info[nba_player_id] = {
                        "nba_player_id": nba_player_id,
                        "player_id": existing_player_meta.get(nba_player_id),
                        "first_name": first_name or name,
                        "last_name": last_name,
                        "position": _normalize_position(player.get("position")),
                        "jersey_number": safe_int(player.get("jerseyNum"), None),
                        "team_nba_id": nba_team_id,
                        "headshot_url": f"https://cdn.nba.com/headshots/nba/latest/260x190/{nba_player_id}.png",
                    }

                    stats = player.get("statistics", {}) or {}
                    played = str(player.get("played") or "0") == "1"
                    game_player_key = (path.name, nba_player_id)
                    if not played or game_player_key in seen_game_player:
                        continue
                    seen_game_player.add(game_player_key)

                    bucket = aggregated[nba_player_id]
                    if not bucket["season_label"]:
                        bucket["season_label"] = season_label

                    bucket["games_played"] += 1
                    if str(player.get("starter") or "0") == "1":
                        bucket["games_started"] += 1
                    bucket["total_seconds"] += _parse_iso_duration_seconds(stats.get("minutes"))
                    bucket["total_points"] += safe_int(stats.get("points"))
                    bucket["total_rebounds"] += safe_int(stats.get("reboundsTotal"))
                    bucket["total_assists"] += safe_int(stats.get("assists"))
                    bucket["total_blocks"] += safe_int(stats.get("blocks"))
                    bucket["total_steals"] += safe_int(stats.get("steals"))
                    bucket["total_turnovers"] += safe_int(stats.get("turnovers"))
                    bucket["total_fouls"] += safe_int(stats.get("foulsPersonal"))
                    bucket["total_fgm"] += safe_int(stats.get("fieldGoalsMade"))
                    bucket["total_fga"] += safe_int(stats.get("fieldGoalsAttempted"))
                    bucket["total_fg3m"] += safe_int(stats.get("threePointersMade"))
                    bucket["total_fg3a"] += safe_int(stats.get("threePointersAttempted"))
                    bucket["total_ftm"] += safe_int(stats.get("freeThrowsMade"))
                    bucket["total_fta"] += safe_int(stats.get("freeThrowsAttempted"))
        except Exception as exc:
            bad_files.append({"file": path.name, "error": str(exc)})

    return player_info, aggregated, games_scanned, bad_files


def upsert_players_and_stats(player_info, aggregated, report_path: Path, current_team_only: bool) -> dict:
    connection = get_db_connection()
    if not connection:
        raise RuntimeError("Database connection failed")

    try:
        cursor = connection.cursor(dictionary=True)
        ensure_regular_season_stats_table(cursor, connection)

        cursor.execute("SELECT team_id, nba_team_id FROM teams WHERE nba_team_id IS NOT NULL")
        team_rows = cursor.fetchall() or []
        team_map = {str(row.get("nba_team_id") or "").strip(): row.get("team_id") for row in team_rows}

        players_upserted = 0
        for info in player_info.values():
            team_id = team_map.get(str(info.get("team_nba_id") or "").strip())
            cursor.execute(
                """
                INSERT INTO players
                (
                    nba_player_id,
                    team_id,
                    first_name,
                    last_name,
                    position,
                    jersey_number,
                    headshot_url,
                    is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
                ON DUPLICATE KEY UPDATE
                    first_name = VALUES(first_name),
                    last_name = VALUES(last_name),
                    position = COALESCE(VALUES(position), position),
                    jersey_number = COALESCE(VALUES(jersey_number), jersey_number),
                    headshot_url = COALESCE(VALUES(headshot_url), headshot_url),
                    is_active = TRUE
                """,
                (
                    info.get("nba_player_id"),
                    team_id,
                    info.get("first_name") or "",
                    info.get("last_name") or "",
                    info.get("position"),
                    info.get("jersey_number"),
                    info.get("headshot_url"),
                ),
            )
            players_upserted += 1

        connection.commit()

        if aggregated:
            nba_ids = list(aggregated.keys())
            placeholders = ", ".join(["%s"] * len(nba_ids))
            cursor.execute(
                f"SELECT player_id, nba_player_id, team_id FROM players WHERE nba_player_id IN ({placeholders})",
                tuple(nba_ids),
            )
            mappings = cursor.fetchall() or []
        else:
            mappings = []
        player_id_map = {str(row.get("nba_player_id") or "").strip(): row.get("player_id") for row in mappings}
        team_id_map = {str(row.get("nba_player_id") or "").strip(): row.get("team_id") for row in mappings}

        stats_rows_upserted = 0
        missing_player_mappings: List[str] = []
        for nba_player_id, bucket in aggregated.items():
            player_id = player_id_map.get(str(nba_player_id).strip())
            if not player_id:
                missing_player_mappings.append(nba_player_id)
                continue
            if current_team_only and team_id_map.get(str(nba_player_id).strip()) is None:
                continue

            gp = bucket["games_played"] or 0
            min_per_game = round((bucket["total_seconds"] / 60.0) / gp, 2) if gp else 0
            pts_per_game = round(bucket["total_points"] / gp, 2) if gp else 0
            reb_per_game = round(bucket["total_rebounds"] / gp, 2) if gp else 0
            ast_per_game = round(bucket["total_assists"] / gp, 2) if gp else 0
            blk_per_game = round(bucket["total_blocks"] / gp, 2) if gp else 0
            stl_per_game = round(bucket["total_steals"] / gp, 2) if gp else 0
            pf_per_game = round(bucket["total_fouls"] / gp, 2) if gp else 0
            tov_per_game = round(bucket["total_turnovers"] / gp, 2) if gp else 0
            fg_pct = round((bucket["total_fgm"] / bucket["total_fga"]) * 100, 2) if bucket["total_fga"] else 0
            fg3_pct = round((bucket["total_fg3m"] / bucket["total_fg3a"]) * 100, 2) if bucket["total_fg3a"] else 0
            ft_pct = round((bucket["total_ftm"] / bucket["total_fta"]) * 100, 2) if bucket["total_fta"] else 0

            cursor.execute(
                """
                INSERT INTO player_regular_season_stats
                (
                    player_id,
                    season_label,
                    games_played,
                    games_started,
                    total_seconds,
                    total_points,
                    total_rebounds,
                    total_assists,
                    total_blocks,
                    total_steals,
                    total_turnovers,
                    total_fouls,
                    total_fgm,
                    total_fga,
                    total_fg3m,
                    total_fg3a,
                    total_ftm,
                    total_fta,
                    min_per_game,
                    pts_per_game,
                    reb_per_game,
                    ast_per_game,
                    blk_per_game,
                    stl_per_game,
                    pf_per_game,
                    tov_per_game,
                    fg_pct,
                    fg3_pct,
                    ft_pct
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    season_label = VALUES(season_label),
                    games_played = VALUES(games_played),
                    games_started = VALUES(games_started),
                    total_seconds = VALUES(total_seconds),
                    total_points = VALUES(total_points),
                    total_rebounds = VALUES(total_rebounds),
                    total_assists = VALUES(total_assists),
                    total_blocks = VALUES(total_blocks),
                    total_steals = VALUES(total_steals),
                    total_turnovers = VALUES(total_turnovers),
                    total_fouls = VALUES(total_fouls),
                    total_fgm = VALUES(total_fgm),
                    total_fga = VALUES(total_fga),
                    total_fg3m = VALUES(total_fg3m),
                    total_fg3a = VALUES(total_fg3a),
                    total_ftm = VALUES(total_ftm),
                    total_fta = VALUES(total_fta),
                    min_per_game = VALUES(min_per_game),
                    pts_per_game = VALUES(pts_per_game),
                    reb_per_game = VALUES(reb_per_game),
                    ast_per_game = VALUES(ast_per_game),
                    blk_per_game = VALUES(blk_per_game),
                    stl_per_game = VALUES(stl_per_game),
                    pf_per_game = VALUES(pf_per_game),
                    tov_per_game = VALUES(tov_per_game),
                    fg_pct = VALUES(fg_pct),
                    fg3_pct = VALUES(fg3_pct),
                    ft_pct = VALUES(ft_pct)
                """,
                (
                    player_id,
                    bucket["season_label"] or _current_nba_season_label(),
                    gp,
                    bucket["games_started"],
                    bucket["total_seconds"],
                    bucket["total_points"],
                    bucket["total_rebounds"],
                    bucket["total_assists"],
                    bucket["total_blocks"],
                    bucket["total_steals"],
                    bucket["total_turnovers"],
                    bucket["total_fouls"],
                    bucket["total_fgm"],
                    bucket["total_fga"],
                    bucket["total_fg3m"],
                    bucket["total_fg3a"],
                    bucket["total_ftm"],
                    bucket["total_fta"],
                    min_per_game,
                    pts_per_game,
                    reb_per_game,
                    ast_per_game,
                    blk_per_game,
                    stl_per_game,
                    pf_per_game,
                    tov_per_game,
                    fg_pct,
                    fg3_pct,
                    ft_pct,
                ),
            )
            stats_rows_upserted += 1

        connection.commit()

        cursor.execute(
            """
            SELECT
                p.player_id,
                p.nba_player_id,
                CONCAT(p.first_name, ' ', p.last_name) AS player_name,
                t.abbreviation AS team_abbreviation,
                p.position,
                p.jersey_number
            FROM players p
            LEFT JOIN teams t ON t.team_id = p.team_id
            LEFT JOIN player_regular_season_stats s ON s.player_id = p.player_id
            WHERE s.player_id IS NULL
              AND (%s = 0 OR p.team_id IS NOT NULL)
            ORDER BY t.abbreviation, p.last_name, p.first_name
            """,
            (1 if current_team_only else 0,),
        )
        unresolved_rows = cursor.fetchall() or []

        report = {
            "players_upserted": players_upserted,
            "stats_rows_upserted": stats_rows_upserted,
            "missing_player_mappings": missing_player_mappings,
            "players_still_missing_stats": unresolved_rows,
        }
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(
        description="Free player stat sync using only local/cached NBA CDN boxscores."
    )
    parser.add_argument("--refresh-cache", action="store_true", help="Download any missing completed-game boxscore cache files from the NBA CDN before syncing.")
    parser.add_argument("--force-refresh-cache", action="store_true", help="Redownload completed-game boxscore cache files even if they already exist.")
    parser.add_argument("--repair-bad-cache", action="store_true", help="Redownload only unreadable/empty cache files before syncing.")
    parser.add_argument("--only-missing", action="store_true", help="Only target players who currently do not have a regular-season stats row.")
    parser.add_argument("--current-team-only", action="store_true", help="Limit unresolved-player reporting to players who are still assigned to a team.")
    parser.add_argument("--player-ids", type=str, default="", help="Comma-separated internal player_id values to sync.")
    args = parser.parse_args()

    cache_dir = Path(GAME_DETAIL_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)

    cache_refresh_result = None
    if args.refresh_cache or args.force_refresh_cache:
        print("Refreshing completed-game cache from NBA CDN...")
        cache_refresh_result = _sync_completed_game_details(force=args.force_refresh_cache)
        print(json.dumps(cache_refresh_result, indent=2))

    bad_cache_repair_result = None
    bad_files_before = detect_bad_cache_files(cache_dir)
    if args.repair_bad_cache and bad_files_before:
        print("Repairing unreadable cache files from NBA CDN...")
        bad_cache_repair_result = repair_bad_cache_files(cache_dir, bad_files_before)
        print(json.dumps(bad_cache_repair_result, indent=2))

    player_ids = {int(chunk) for chunk in args.player_ids.split(",") if chunk.strip()} if args.player_ids else None

    target_internal_ids = None
    if args.only_missing or player_ids:
        connection = get_db_connection()
        if not connection:
            raise RuntimeError("Database connection failed")
        try:
            cursor = connection.cursor(dictionary=True)
            ensure_regular_season_stats_table(cursor, connection)
            target_internal_ids = load_target_player_ids(
                cursor,
                only_missing=args.only_missing,
                player_ids=player_ids,
                current_team_only=args.current_team_only,
            )
        finally:
            connection.close()

    print(f"Scanning cached boxscores in: {cache_dir}")
    player_info, aggregated, games_scanned, bad_files_after = aggregate_from_cache(cache_dir, target_internal_ids=target_internal_ids)
    report_path = cache_dir.parent / "player_stats_free_sync_report.json"
    result = upsert_players_and_stats(player_info, aggregated, report_path, current_team_only=args.current_team_only)

    summary = {
        "games_scanned": games_scanned,
        "players_found_in_cache": len(player_info),
        "players_with_stats_in_cache": len(aggregated),
        "target_player_count": len(target_internal_ids) if target_internal_ids is not None else None,
        "bad_cache_files_before": bad_files_before[:20],
        "bad_cache_files_after": bad_files_after[:20],
        "cache_refresh": cache_refresh_result,
        "bad_cache_repair": bad_cache_repair_result,
        **result,
        "report_path": str(report_path),
    }
    print(json.dumps(summary, indent=2))

    if bad_files_after:
        print("\nSome cache files still could not be read. Re-run with --repair-bad-cache or inspect bad_cache_files_after in the summary.")

    unresolved = result.get("players_still_missing_stats") or []
    if unresolved:
        print(f"\nPlayers still missing stats rows: {len(unresolved)}")
        for row in unresolved[:25]:
            print(
                f"- {row.get('player_name') or 'Unknown'}"
                f" | team={row.get('team_abbreviation') or 'None'}"
                f" | nba_id={row.get('nba_player_id') or 'None'}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
