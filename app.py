"""
Basketball Web App Backend - Flask API
Connects to hoopwatch MySQL database and serves team/player data
"""

import os
import json
import datetime
import re
import time
import secrets
import requests
from collections import defaultdict
from dotenv import load_dotenv

# Load environment variables from a local .env file (if present)
load_dotenv()

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash

from nba_api.live.nba.endpoints import scoreboard
from nba_api.stats.static import teams
from nba_api.stats.endpoints import commonteamroster
from nba_api.stats.endpoints import leaguestandings

app = Flask(__name__)
CORS(app)

# ================= DATABASE CONFIG =================

db_config = {
    # Prefer 127.0.0.1 on Windows (avoids some localhost socket quirks)
    "host": os.environ.get("MYSQL_HOST", "127.0.0.1"),
    "port": int(os.environ.get("MYSQL_PORT", "3306")),
    "user": os.environ.get("MYSQL_USER", "root"),
    "password": os.environ.get("MYSQL_PASSWORD", "IzzyPop2025!"),  # set in env if needed
    # Support either MYSQL_DATABASE or MYSQL_DB
    "database": os.environ.get("MYSQL_DATABASE") or os.environ.get("MYSQL_DB") or "hoopwatch",
}

GAME_DETAIL_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "game_detail_cache")
os.makedirs(GAME_DETAIL_CACHE_DIR, exist_ok=True)
GAME_DETAIL_BOX_CACHE = {}
AUTH_SESSION_TTL_SECONDS = 60 * 60 * 24 * 7
AUTH_SESSIONS = {}


def _make_json_safe(value):
    if isinstance(value, dict):
        return {key: _make_json_safe(val) for key, val in value.items()}

    if isinstance(value, list):
        return [_make_json_safe(item) for item in value]

    if isinstance(value, tuple):
        return [_make_json_safe(item) for item in value]

    if isinstance(value, datetime.datetime):
        return value.isoformat()

    if isinstance(value, datetime.date):
        return value.isoformat()

    if isinstance(value, datetime.timedelta):
        total_seconds = int(value.total_seconds())
        sign = '-' if total_seconds < 0 else ''
        total_seconds = abs(total_seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"

    return value

def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Database connection error: {e}")
        return None


# ================= NBA API FUNCTIONS =================




def ensure_user_account_columns():
    connection = get_db_connection()
    if not connection:
        return False

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'users'
            """,
            (db_config.get('database'),),
        )
        existing = {row[0] for row in (cursor.fetchall() or [])}

        alter_statements = []
        if 'username' not in existing:
            alter_statements.append("ALTER TABLE users ADD COLUMN username VARCHAR(80) NULL UNIQUE AFTER email")
        if 'display_name' not in existing:
            alter_statements.append("ALTER TABLE users ADD COLUMN display_name VARCHAR(120) NULL AFTER username")
        if 'bio' not in existing:
            alter_statements.append("ALTER TABLE users ADD COLUMN bio TEXT NULL AFTER display_name")
        if 'profile_image_url' not in existing:
            alter_statements.append("ALTER TABLE users ADD COLUMN profile_image_url VARCHAR(500) NULL AFTER bio")

        for statement in alter_statements:
            cursor.execute(statement)

        if alter_statements:
            connection.commit()

        cursor.close()
        return True
    except Exception as exc:
        print(f"User account column ensure error: {exc}")
        return False
    finally:
        connection.close()


def _normalize_auth_user_row(row):
    if not row:
        return None

    return {
        'user_id': row.get('user_id'),
        'email': row.get('email'),
        'username': row.get('username'),
        'display_name': row.get('display_name') or row.get('username') or row.get('email'),
        'bio': row.get('bio') or '',
        'profile_image_url': row.get('profile_image_url'),
        'role': row.get('role') or 'base',
    }


def _issue_auth_token(user_id):
    token = secrets.token_urlsafe(32)
    AUTH_SESSIONS[token] = {
        'user_id': int(user_id),
        'created_at': time.time(),
    }
    return token


def _get_authorized_user_id():
    auth_header = request.headers.get('Authorization', '').strip()
    token = ''

    if auth_header.lower().startswith('bearer '):
        token = auth_header.split(' ', 1)[1].strip()
    elif request.headers.get('X-Auth-Token'):
        token = request.headers.get('X-Auth-Token', '').strip()

    if not token:
        return None

    session = AUTH_SESSIONS.get(token)
    if not session:
        return None

    if time.time() - session.get('created_at', 0) > AUTH_SESSION_TTL_SECONDS:
        AUTH_SESSIONS.pop(token, None)
        return None

    session['created_at'] = time.time()
    return session.get('user_id')


def _get_auth_user_by_identifier(cursor, identifier):
    cursor.execute(
        """
        SELECT user_id, email, username, display_name, bio, profile_image_url, password_hash, role
        FROM users
        WHERE email = %s OR username = %s
        LIMIT 1
        """,
        (identifier, identifier),
    )
    return cursor.fetchone()


def get_user_by_id(user_id):
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        ensure_user_account_columns()
        cursor.execute("SELECT user_id, email, username, display_name, bio, profile_image_url, role FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        cursor.close()
        return row
    except Exception as e:
        print(f"User lookup error: {e}")
        return None
    finally:
        connection.close()


def resolve_internal_game_id(game_identifier, create_from_live=True):
    """Resolve either an internal game_id or nba_game_id to the internal DB game_id."""
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT game_id, nba_game_id
            FROM games
            WHERE CAST(game_id AS CHAR) = %s OR nba_game_id = %s
            LIMIT 1
            """,
            (str(game_identifier), str(game_identifier)),
        )
        row = cursor.fetchone()
        cursor.close()
        if row:
            return int(row["game_id"])
    except Exception as e:
        print(f"Game resolve lookup error: {e}")
    finally:
        connection.close()

    if not create_from_live:
        return None

    try:
        for game in fetch_live_games() or []:
            if str(game.get("gameId")) == str(game_identifier):
                cache_game(game)
                break
    except Exception as e:
        print(f"Live game backfill failed: {e}")

    try:
        schedule_game = _find_schedule_game_by_id(game_identifier)
        if schedule_game:
            _cache_schedule_game_record(schedule_game)
    except Exception as e:
        print(f"Schedule game backfill failed: {e}")

    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT game_id
            FROM games
            WHERE CAST(game_id AS CHAR) = %s OR nba_game_id = %s
            LIMIT 1
            """,
            (str(game_identifier), str(game_identifier)),
        )
        row = cursor.fetchone()
        cursor.close()
        return int(row["game_id"]) if row else None
    except Exception as e:
        print(f"Game resolve retry error: {e}")
        return None
    finally:
        connection.close()

def fetch_live_games():
    games = scoreboard.ScoreBoard()
    data = games.get_dict()
    return data["scoreboard"]["games"]


def cache_game(game):
    """Store a lightweight cache snapshot in MySQL.

    NOTE: Our schema uses an internal AUTO_INCREMENT games.game_id, and stores the NBA id in games.nba_game_id.
    game_cache references games.game_id (internal).
    """
    connection = get_db_connection()
    if not connection:
        return

    cursor = connection.cursor()

    try:
        nba_game_id = str(game.get("gameId"))
        home_nba_team_id = str(game["homeTeam"]["teamId"])
        away_nba_team_id = str(game["awayTeam"]["teamId"])

            # Resolve internal team ids from teams.nba_team_id
        cursor.execute("SELECT team_id FROM teams WHERE nba_team_id = %s", (home_nba_team_id,))
        home_row = cursor.fetchone()

        cursor.execute("SELECT team_id FROM teams WHERE nba_team_id = %s", (away_nba_team_id,))
        away_row = cursor.fetchone()

        if not home_row or not away_row:
            print(f"Cache error: could not map NBA team ids {home_nba_team_id}, {away_nba_team_id} to internal team ids")
            connection.commit()
            return

        home_team = int(home_row[0])
        away_team = int(away_row[0])

        # Try to get date from API payload; otherwise fallback to today
        game_date_str = (
            game.get("gameDateEst")
            or game.get("gameDate")
            or game.get("gameEt")  # sometimes like "2026-03-08T19:00:00Z"
        )
        game_date = None
        if isinstance(game_date_str, str):
            # pick YYYY-MM-DD if present
            m = re.search(r"(\d{4}-\d{2}-\d{2})", game_date_str)
            if m:
                game_date = m.group(1)

        if not game_date:
            game_date = datetime.date.today().isoformat()

        status = "scheduled"
        if game.get("gameStatus") == 2:
            status = "live"
        elif game.get("gameStatus") == 3:
            status = "final"

        # Upsert into games by nba_game_id (unique)
        cursor.execute(
            """
            INSERT INTO games (nba_game_id, home_team_id, away_team_id, game_date, status)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                home_team_id = VALUES(home_team_id),
                away_team_id = VALUES(away_team_id),
                game_date = VALUES(game_date),
                status = VALUES(status)
            """,
            (nba_game_id, home_team, away_team, game_date, status),
        )

        # Resolve internal game_id for cache table
        cursor.execute("SELECT game_id FROM games WHERE nba_game_id=%s", (nba_game_id,))
        row = cursor.fetchone()
        if not row:
            connection.commit()
            return
        internal_game_id = int(row[0])

        clock = game.get("gameClock") or "0:00"

        cursor.execute(
            """
            INSERT INTO game_cache
                (game_id, home_score, away_score, period, clock, fetched_at)
            VALUES (%s,%s,%s,%s,%s,NOW())
            ON DUPLICATE KEY UPDATE
                home_score=VALUES(home_score),
                away_score=VALUES(away_score),
                period=VALUES(period),
                clock=VALUES(clock),
                fetched_at=NOW()
            """,
            (
                internal_game_id,
                int(game["homeTeam"].get("score") or 0),
                int(game["awayTeam"].get("score") or 0),
                int(game.get("period") or 0),
                clock,
            ),
        )

        connection.commit()

    except Exception as e:
        print("Cache error:", e)

    finally:
        cursor.close()
        connection.close()

def fetch_team_roster(team_id):

    roster = commonteamroster.CommonTeamRoster(team_id=team_id)
    data = roster.get_dict()

    return data


def _get_table_columns(connection, table_name):
    cur = connection.cursor()
    cur.execute(f"SHOW COLUMNS FROM {table_name}")
    cols = cur.fetchall()
    cur.close()
    # SHOW COLUMNS columns: Field, Type, Null, Key, Default, Extra
    return {c[0]: {"type": c[1], "null": c[2], "key": c[3], "default": c[4], "extra": c[5]} for c in cols}

def _parse_height_to_inches(height_str):
    """
    Convert heights like '6-8' to total inches.
    Returns None if parsing fails.
    """
    if not height_str:
        return None

    try:
        s = str(height_str).strip()
        if "-" in s:
            ft, inch = s.split("-")
            return int(ft) * 12 + int(inch)
    except Exception:
        pass

    return None

def sync_teams():
    nba_teams = teams.get_teams()

    connection = get_db_connection()
    if not connection:
        return

    cols = _get_table_columns(connection, "teams")
    has_auto_team_id = (
        "team_id" in cols and
        "auto_increment" in str(cols["team_id"]["extra"]).lower()
    )

    cursor = connection.cursor()

    east_teams = {
        "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DET",
        "IND", "MIA", "MIL", "NYK", "ORL", "PHI", "TOR", "WAS"
    }

    arena_map = {
        "ATL": "State Farm Arena",
        "BOS": "TD Garden",
        "BKN": "Barclays Center",
        "CHA": "Spectrum Center",
        "CHI": "United Center",
        "CLE": "Rocket Mortgage FieldHouse",
        "DAL": "American Airlines Center",
        "DEN": "Ball Arena",
        "DET": "Little Caesars Arena",
        "GSW": "Chase Center",
        "HOU": "Toyota Center",
        "IND": "Gainbridge Fieldhouse",
        "LAC": "Intuit Dome",
        "LAL": "Crypto.com Arena",
        "MEM": "FedExForum",
        "MIA": "Kaseya Center",
        "MIL": "Fiserv Forum",
        "MIN": "Target Center",
        "NOP": "Smoothie King Center",
        "NYK": "Madison Square Garden",
        "OKC": "Paycom Center",
        "ORL": "Kia Center",
        "PHI": "Wells Fargo Center",
        "PHX": "Footprint Center",
        "POR": "Moda Center",
        "SAC": "Golden 1 Center",
        "SAS": "Frost Bank Center",
        "TOR": "Scotiabank Arena",
        "UTA": "Delta Center",
        "WAS": "Capital One Arena",
    }

    for team in nba_teams:
        nba_id = int(team["id"])
        full_name = team.get("full_name") or team.get("name") or ""
        abbr = team.get("abbreviation") or ""
        city = team.get("city") or ""
        state = team.get("state") or ""
        conf = "East" if abbr in east_teams else "West"
        arena = arena_map.get(abbr, "")
        logo = f"https://cdn.nba.com/logos/nba/{nba_id}/primary/L/logo.svg"

        fields = []
        values = []
        updates = []

        def add(field, value):
            if field in cols:
                fields.append(field)
                values.append(value)
                updates.append(f"{field}=VALUES({field})")

        if "team_id" in cols and not has_auto_team_id:
            add("team_id", nba_id)

        add("nba_team_id", str(nba_id))
        add("name", full_name)
        add("abbreviation", abbr)
        add("city", city)
        add("state", state)
        add("conference", conf)
        add("arena_name", arena)
        add("logo_url", logo)

        if not fields:
            continue

        sql = f"""
            INSERT INTO teams ({', '.join(fields)})
            VALUES ({', '.join(['%s'] * len(fields))})
            ON DUPLICATE KEY UPDATE
                {', '.join(updates)}
        """
        cursor.execute(sql, tuple(values))

    connection.commit()
    cursor.close()
    connection.close()


def _current_nba_season_start_year(today=None):
    today = today or datetime.date.today()
    return today.year if today.month >= 10 else today.year - 1


def _compute_standings_from_games(game_iterable):
    standings = {}

    def ensure_team(team_id):
        if team_id not in standings:
            standings[team_id] = {"nba_team_id": team_id, "wins": 0, "losses": 0}
        return standings[team_id]

    for game in game_iterable:
        game_id = str(game.get("game_id", "")).strip()
        if not game_id.startswith("002"):
            continue

        status = game.get("status")
        status_text = str(game.get("status_text", "") or "").strip().lower()
        is_final = status == 3 or status_text.startswith("final") or "final" in status_text
        if not is_final:
            continue

        away_id = str(game.get("away_id", "")).strip()
        home_id = str(game.get("home_id", "")).strip()
        away_score_raw = str(game.get("away_score", "")).strip()
        home_score_raw = str(game.get("home_score", "")).strip()

        if not away_id or not home_id:
            continue
        if not away_score_raw.isdigit() or not home_score_raw.isdigit():
            continue

        away_score = int(away_score_raw)
        home_score = int(home_score_raw)

        away_row = ensure_team(away_id)
        home_row = ensure_team(home_id)

        if away_score > home_score:
            away_row["wins"] += 1
            home_row["losses"] += 1
        elif home_score > away_score:
            home_row["wins"] += 1
            away_row["losses"] += 1

    rows = list(standings.values())
    if not rows:
        raise RuntimeError("schedule feed returned no completed regular-season games")

    return rows


def _fetch_regular_season_standings_from_cdn_schedule():
    """Compute standings from NBA's static CDN schedule feed.

    This feed is public and does not depend on stats.nba.com, which is timing out
    on the user's machine. The public schedule structure is documented as
    leagueSchedule -> gameDates -> games. Each game includes gameId, gameStatus,
    gameStatusText, and nested homeTeam / awayTeam score and id fields.
    """
    urls = [
        "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
        "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nba.com/schedule",
    }

    last_error = None
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            payload = response.json()
            game_dates = payload.get("leagueSchedule", {}).get("gameDates", [])
            games_out = []
            for game_date in game_dates:
                for game in game_date.get("games", []) or []:
                    home = game.get("homeTeam", {}) or {}
                    away = game.get("awayTeam", {}) or {}
                    games_out.append({
                        "game_id": str(game.get("gameId", "") or game.get("gid", "")).strip(),
                        "status": game.get("gameStatus"),
                        "status_text": str(game.get("gameStatusText", "") or game.get("stt", "") or game.get("st", "")).strip(),
                        "home_id": str(home.get("teamId", "") or home.get("tid", "")).strip(),
                        "away_id": str(away.get("teamId", "") or away.get("tid", "")).strip(),
                        "home_score": str(home.get("score", "") or home.get("s", "")).strip(),
                        "away_score": str(away.get("score", "") or away.get("s", "")).strip(),
                    })
            return _compute_standings_from_games(games_out)
        except Exception as exc:
            last_error = exc
            print(f"cdn schedule fetch failed for {url}: {exc}")

    raise last_error or RuntimeError("cdn schedule fetch failed")


def _fetch_regular_season_standings_from_schedule():
    """Fallback schedule-based standings using the older data.nba.com feed."""
    season_start = _current_nba_season_start_year()
    url = f"https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/{season_start}/league/00_full_schedule.json"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nba.com/schedule",
        "Origin": "https://www.nba.com",
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()

    games_out = []
    for month_block in payload.get("lscd", []):
        month_data = month_block.get("mscd", {}) if isinstance(month_block, dict) else {}
        games = month_data.get("g", []) if isinstance(month_data, dict) else []
        for game in games:
            away = game.get("v", {}) or {}
            home = game.get("h", {}) or {}
            games_out.append({
                "game_id": str(game.get("gid", "")).strip(),
                "status": None,
                "status_text": str(game.get("stt", "") or game.get("st", "")).strip(),
                "away_id": str(away.get("tid", "")).strip(),
                "home_id": str(home.get("tid", "")).strip(),
                "away_score": str(away.get("s", "")).strip(),
                "home_score": str(home.get("s", "")).strip(),
            })

    return _compute_standings_from_games(games_out)


def _fetch_standings_from_data_nba():
    season_start = _current_nba_season_start_year()
    url = f"https://data.nba.com/data/10s/v2015/json/mobile_teams/nba/{season_start}/00_standings.json"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nba.com/standings",
        "Origin": "https://www.nba.com",
    }

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    payload = response.json()

    teams_rows = []
    conferences = payload.get("sta", {}).get("co", [])

    for conference in conferences:
        if conference.get("val") not in ("East", "West"):
            continue

        for division in conference.get("di", []):
            for team in division.get("t", []):
                nba_team_id = str(team.get("tid", "")).strip()
                if not nba_team_id:
                    continue

                try:
                    wins = int(team.get("w", 0) or 0)
                except Exception:
                    wins = 0

                try:
                    losses = int(team.get("l", 0) or 0)
                except Exception:
                    losses = 0

                teams_rows.append({
                    "nba_team_id": nba_team_id,
                    "wins": wins,
                    "losses": losses,
                })

    if not teams_rows:
        raise RuntimeError("data.nba.com returned no NBA standings rows")

    return teams_rows


def _fetch_standings_from_stats_nba():
    standings = leaguestandings.LeagueStandings(timeout=45)
    data = standings.get_dict()

    headers = data["resultSets"][0]["headers"]
    rows = data["resultSets"][0]["rowSet"]

    def idx(col_name):
        return headers.index(col_name) if col_name in headers else None

    team_id_idx = idx("TeamID") if idx("TeamID") is not None else idx("TEAM_ID")
    wins_idx = idx("WINS") if idx("WINS") is not None else idx("W")
    losses_idx = idx("LOSSES") if idx("LOSSES") is not None else idx("L")

    parsed_rows = []
    for team in rows:
        parsed_rows.append({
            "nba_team_id": str(team[team_id_idx]),
            "wins": int(team[wins_idx]) if str(team[wins_idx]).isdigit() else 0,
            "losses": int(team[losses_idx]) if str(team[losses_idx]).isdigit() else 0,
        })

    if not parsed_rows:
        raise RuntimeError("stats.nba.com returned no standings rows")

    return parsed_rows


def sync_standings():
    last_error = None

    try:
        rows = _fetch_regular_season_standings_from_cdn_schedule()
        standings_source = "cdn.nba.com scheduleLeagueV2"
    except Exception as e:
        last_error = e
        print(f"cdn schedule-based standings fetch failed: {e}")

        try:
            rows = _fetch_regular_season_standings_from_schedule()
            standings_source = "data.nba.com schedule"
        except Exception as e1:
            last_error = e1
            print(f"data.nba.com schedule-based standings fetch failed: {e1}")

            try:
                rows = _fetch_standings_from_data_nba()
                standings_source = "data.nba.com standings"
            except Exception as e2:
                last_error = e2
                print(f"data.nba.com standings fetch failed: {e2}")

                try:
                    rows = _fetch_standings_from_stats_nba()
                    standings_source = "stats.nba.com"
                except Exception as e3:
                    last_error = e3
                    print(f"stats.nba.com standings fetch failed: {e3}")
                    raise last_error

    connection = get_db_connection()
    if not connection:
        raise RuntimeError("Database connection failed")

    cursor = connection.cursor()
    updated_count = 0

    for team in rows:
        nba_team_id = str(team["nba_team_id"])
        wins = int(team["wins"])
        losses = int(team["losses"])

        cursor.execute("SELECT team_id FROM teams WHERE nba_team_id=%s", (nba_team_id,))
        exists = cursor.fetchone()

        if not exists:
            print(f"Skipping NBA team {nba_team_id}: not found in teams table")
            continue

        internal_team_id = exists[0]

        cursor.execute("""
            INSERT INTO team_standings (team_id, wins, losses)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                wins = VALUES(wins),
                losses = VALUES(losses)
        """, (internal_team_id, wins, losses))
        updated_count += 1

    connection.commit()
    cursor.close()
    connection.close()
    return {"updated": updated_count, "source": standings_source}



def _fetch_completed_regular_season_games_from_cdn_schedule():
    """Return completed regular-season games from the public NBA CDN schedule feed."""
    urls = [
        "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
        "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nba.com/schedule",
    }

    last_error = None
    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            payload = response.json()
            game_dates = payload.get("leagueSchedule", {}).get("gameDates", []) or []

            games_out = []
            for game_date in game_dates:
                for game in (game_date.get("games", []) or []):
                    game_id = str(game.get("gameId", "") or game.get("gid", "")).strip()
                    if not game_id.startswith("002"):
                        continue

                    status = game.get("gameStatus")
                    status_text = str(game.get("gameStatusText", "") or game.get("stt", "") or game.get("st", "")).strip()
                    home = game.get("homeTeam", {}) or {}
                    away = game.get("awayTeam", {}) or {}
                    home_score = str(home.get("score", "") or home.get("s", "")).strip()
                    away_score = str(away.get("score", "") or away.get("s", "")).strip()

                    is_final = (
                        status == 3
                        or status_text.lower().startswith("final")
                        or (home_score.isdigit() and away_score.isdigit())
                    )
                    if not is_final:
                        continue

                    games_out.append({
                        "game_id": game_id,
                        "home_id": str(home.get("teamId", "") or home.get("tid", "")).strip(),
                        "away_id": str(away.get("teamId", "") or away.get("tid", "")).strip(),
                    })

            if not games_out:
                raise RuntimeError("CDN schedule returned no completed regular-season games")

            return list(reversed(games_out))
        except Exception as exc:
            last_error = exc
            print(f"CDN roster schedule fetch failed for {url}: {exc}")

    raise last_error or RuntimeError("CDN roster schedule fetch failed")




def _safe_int(value):
    try:
        if value is None:
            return None
        s = str(value).strip()
        if s == "":
            return None
        return int(float(s))
    except Exception:
        return None


def _extract_date_string(*values):
    for value in values:
        if value is None:
            continue
        match = re.search(r"(\d{4}-\d{2}-\d{2})", str(value))
        if match:
            return match.group(1)
    return None


def _extract_start_time(*values):
    for value in values:
        if value is None:
            continue
        raw = str(value).strip()
        if not raw:
            continue

        try:
            iso_candidate = raw.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(iso_candidate)
            return dt.strftime("%H:%M:%S")
        except Exception:
            pass

        match = re.search(r"(\d{2}:\d{2})(?::(\d{2}))?", raw)
        if match:
            hhmm = match.group(1)
            ss = match.group(2) or "00"
            return f"{hhmm}:{ss}"

    return None


def _normalize_schedule_status(status_code, status_text, home_score=None, away_score=None):
    status_text = str(status_text or "").strip()
    lowered = status_text.lower()

    if status_code == 3 or lowered.startswith("final"):
        return "final", "Final"

    if status_code == 2 or lowered.startswith("q") or "halftime" in lowered:
        return "live", status_text or "Live"

    if home_score is not None and away_score is not None and status_code not in (1, 2):
        return "final", "Final"

    return "scheduled", status_text or "Upcoming"


def _load_team_lookup():
    connection = get_db_connection()
    if not connection:
        raise RuntimeError("Database connection failed")

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                t.team_id,
                t.nba_team_id,
                t.name,
                t.city,
                t.abbreviation,
                t.logo_url,
                t.arena_name,
                COALESCE(ts.wins, 0) AS wins,
                COALESCE(ts.losses, 0) AS losses
            FROM teams t
            LEFT JOIN team_standings ts ON ts.team_id = t.team_id
            """
        )
        rows = cursor.fetchall() or []
        cursor.close()
    finally:
        connection.close()

    by_nba = {}
    by_internal = {}
    for row in rows:
        nba_id = str(row.get("nba_team_id") or "").strip()
        if nba_id:
            by_nba[nba_id] = row
        by_internal[str(row.get("team_id"))] = row

    return {"by_nba": by_nba, "by_internal": by_internal}


def _team_payload_from_schedule(raw_team, team_row):
    city = (raw_team or {}).get("teamCity") or (team_row or {}).get("city") or ""
    nickname = (raw_team or {}).get("teamName") or (team_row or {}).get("name") or "Team"
    full_name = f"{city} {nickname}".strip()
    abbreviation = (raw_team or {}).get("teamTricode") or (team_row or {}).get("abbreviation") or ""

    return {
        "id": (team_row or {}).get("team_id") or (raw_team or {}).get("teamId") or None,
        "nba_team_id": (raw_team or {}).get("teamId") or (team_row or {}).get("nba_team_id") or None,
        "full_name": full_name,
        "abbreviation": abbreviation,
        "wins": _safe_int((raw_team or {}).get("wins")) if (raw_team or {}).get("wins") not in (None, "") else _safe_int((team_row or {}).get("wins")) or 0,
        "losses": _safe_int((raw_team or {}).get("losses")) if (raw_team or {}).get("losses") not in (None, "") else _safe_int((team_row or {}).get("losses")) or 0,
        "logo_url": (team_row or {}).get("logo_url") or None,
    }


def _build_schedule_game_payload(game, game_date_block, team_lookup):
    home_raw = game.get("homeTeam", {}) or {}
    away_raw = game.get("awayTeam", {}) or {}

    game_identifier = str(game.get("gameId", "") or game.get("gid", "")).strip()
    if not game_identifier.startswith("002"):
        return None

    home_nba_id = str(home_raw.get("teamId", "") or home_raw.get("tid", "")).strip()
    away_nba_id = str(away_raw.get("teamId", "") or away_raw.get("tid", "")).strip()
    if not home_nba_id or not away_nba_id:
        return None

    home_team_row = team_lookup["by_nba"].get(home_nba_id)
    away_team_row = team_lookup["by_nba"].get(away_nba_id)

    home_score = _safe_int(home_raw.get("score", "") or home_raw.get("s", ""))
    away_score = _safe_int(away_raw.get("score", "") or away_raw.get("s", ""))

    raw_status = _safe_int(game.get("gameStatus"))
    raw_status_text = str(game.get("gameStatusText", "") or game.get("stt", "") or game.get("st", "")).strip()
    status_key, status_label = _normalize_schedule_status(raw_status, raw_status_text, home_score, away_score)

    game_date = _extract_date_string(
        game.get("gameDateEst"),
        game.get("gameDate"),
        game.get("gameEt"),
        game.get("gameDateTimeEst"),
        game.get("gameDateUTC"),
        (game_date_block or {}).get("gameDate"),
        (game_date_block or {}).get("gameDateString"),
    )

    game_datetime = (
        game.get("gameEt")
        or game.get("gameDateTimeEst")
        or game.get("gameDateUTC")
        or game.get("gameDateTimeUTC")
        or None
    )
    start_time = _extract_start_time(
        game_datetime,
        game.get("gameTimeUTC"),
        game.get("gameDateTimeUTC"),
        game.get("gameDateTimeEst"),
    )

    home_payload = _team_payload_from_schedule(home_raw, home_team_row)
    away_payload = _team_payload_from_schedule(away_raw, away_team_row)

    winner_team_id = None
    loser_team_id = None
    winner_side = None
    if home_score is not None and away_score is not None and home_score != away_score:
        if home_score > away_score:
            winner_team_id = home_payload["id"]
            loser_team_id = away_payload["id"]
            winner_side = "home"
        else:
            winner_team_id = away_payload["id"]
            loser_team_id = home_payload["id"]
            winner_side = "away"

    return {
        "game_id": game_identifier,
        "gameId": game_identifier,
        "nba_game_id": game_identifier,
        "gameStatus": raw_status,
        "status": status_label if status_key != "scheduled" else "Upcoming",
        "status_key": status_key,
        "game_time": raw_status_text or ("Final" if status_key == "final" else "TBD"),
        "game_date": game_date,
        "game_datetime": game_datetime,
        "start_time": start_time,
        "arena_name": (home_team_row or {}).get("arena_name") or "Arena TBD",
        "home_team": home_payload,
        "away_team": away_payload,
        "home_score": home_score,
        "away_score": away_score,
        "winner_team_id": winner_team_id,
        "loser_team_id": loser_team_id,
        "winner_side": winner_side,
        "is_completed": status_key == "final",
        "is_live": status_key == "live",
        "is_upcoming": status_key == "scheduled",
    }


def _fetch_regular_season_schedule_from_cdn():
    urls = [
        "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json",
        "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json",
    ]

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nba.com/schedule",
    }

    team_lookup = _load_team_lookup()
    last_error = None

    for url in urls:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            payload = response.json()
            game_dates = payload.get("leagueSchedule", {}).get("gameDates", []) or []

            games_out = []
            for game_date_block in game_dates:
                for game in (game_date_block.get("games", []) or []):
                    parsed = _build_schedule_game_payload(game, game_date_block, team_lookup)
                    if parsed:
                        games_out.append(parsed)

            if not games_out:
                raise RuntimeError("CDN schedule returned no regular-season games")

            return games_out
        except Exception as exc:
            last_error = exc
            print(f"regular season schedule fetch failed for {url}: {exc}")

    raise last_error or RuntimeError("regular season schedule fetch failed")


def _cache_schedule_game_record(game_payload):
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor(dictionary=True)

        home_team_id = game_payload.get("home_team", {}).get("id")
        away_team_id = game_payload.get("away_team", {}).get("id")
        nba_game_id = str(game_payload.get("game_id") or game_payload.get("nba_game_id") or "").strip()
        game_date = game_payload.get("game_date") or datetime.date.today().isoformat()
        start_time = game_payload.get("start_time")
        status_key = game_payload.get("status_key") or "scheduled"

        if not home_team_id or not away_team_id or not nba_game_id:
            return None

        cursor.execute(
            """
            INSERT INTO games (nba_game_id, home_team_id, away_team_id, game_date, start_time, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                home_team_id = VALUES(home_team_id),
                away_team_id = VALUES(away_team_id),
                game_date = VALUES(game_date),
                start_time = VALUES(start_time),
                status = VALUES(status)
            """,
            (nba_game_id, home_team_id, away_team_id, game_date, start_time, status_key),
        )

        cursor.execute("SELECT game_id FROM games WHERE nba_game_id = %s LIMIT 1", (nba_game_id,))
        row = cursor.fetchone()
        internal_game_id = int(row["game_id"]) if row and row.get("game_id") else None

        home_score = game_payload.get("home_score")
        away_score = game_payload.get("away_score")
        if internal_game_id and home_score is not None and away_score is not None:
            cursor.execute(
                """
                INSERT INTO game_cache (game_id, home_score, away_score, period, clock, fetched_at)
                VALUES (%s, %s, %s, NULL, NULL, NOW())
                ON DUPLICATE KEY UPDATE
                    home_score = VALUES(home_score),
                    away_score = VALUES(away_score),
                    fetched_at = NOW()
                """,
                (internal_game_id, int(home_score), int(away_score)),
            )

        connection.commit()
        cursor.close()
        return internal_game_id
    except Exception as exc:
        print(f"Schedule cache error: {exc}")
        return None
    finally:
        connection.close()


def _find_schedule_game_by_id(game_identifier):
    target = str(game_identifier or "").strip()
    if not target:
        return None

    for game in _fetch_regular_season_schedule_from_cdn():
        if str(game.get("game_id")) == target or str(game.get("nba_game_id")) == target:
            return game

    return None

def _normalize_position(position):
    allowed = {"PG", "SG", "SF", "PF", "C", "G", "F"}
    if not position:
        return None

    pos = str(position).strip().upper()
    if pos in allowed:
        return pos

    combo_map = {
        "G-F": "G",
        "F-G": "F",
        "F-C": "F",
        "C-F": "C",
        "G/C": "G",
        "C/G": "C",
        "F/C": "F",
        "C/F": "C",
        "G-F-C": "G",
        "F-G-C": "F",
    }
    if pos in combo_map:
        return combo_map[pos]

    for candidate in ["PG", "SG", "SF", "PF", "C", "G", "F"]:
        if candidate in pos:
            return candidate

    return None


def _fetch_boxscore_payload(game_id, cache):
    if game_id in cache:
        return cache[game_id]

    url = f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.nba.com/game/" + game_id,
    }

    response = requests.get(url, headers=headers, timeout=20)
    response.raise_for_status()
    payload = response.json()
    cache[game_id] = payload
    return payload


def _collect_rosters_from_cdn_boxscores(target_team_ids, min_players_per_team=12, max_games_per_team=6):
    """Build recent team rosters from public CDN boxscore feeds.

    This avoids stats.nba.com entirely. BoxScore liveData includes each team's
    players with personId, jerseyNum, position, name, firstName, and familyName.
    """
    games = _fetch_completed_regular_season_games_from_cdn_schedule()
    target_team_ids = {str(tid) for tid in target_team_ids if tid}

    rosters = {tid: {} for tid in target_team_ids}
    games_seen = defaultdict(int)
    boxscore_cache = {}
    errors = []

    def team_done(team_id):
        return len(rosters[team_id]) >= min_players_per_team or games_seen[team_id] >= max_games_per_team

    def record_players(team_payload):
        team_id = str(team_payload.get("teamId", "") or "").strip()
        if team_id not in rosters or team_done(team_id):
            return

        games_seen[team_id] += 1
        for player in team_payload.get("players", []) or []:
            nba_player_id = str(player.get("personId", "") or "").strip()
            if not nba_player_id:
                continue

            name = str(player.get("name", "") or "").strip()
            first_name = str(player.get("firstName", "") or "").strip()
            last_name = str(player.get("familyName", "") or "").strip()

            if (not first_name or not last_name) and name:
                parts = name.split()
                if not first_name and parts:
                    first_name = parts[0]
                if not last_name and len(parts) > 1:
                    last_name = " ".join(parts[1:])

            if not first_name and not last_name:
                continue

            rosters[team_id][nba_player_id] = {
                "nba_player_id": nba_player_id,
                "first_name": first_name or name,
                "last_name": last_name,
                "position": _normalize_position(player.get("position")),
                "jersey_number": player.get("jerseyNum"),
                "height_in": None,
                "weight_lb": None,
                "birth_date": None,
                "headshot_url": f"https://cdn.nba.com/headshots/nba/latest/260x190/{nba_player_id}.png",
            }

    for game in games:
        involved = []
        for tid in [game.get("home_id"), game.get("away_id")]:
            tid = str(tid or "").strip()
            if tid in rosters and not team_done(tid):
                involved.append(tid)

        if not involved:
            continue

        try:
            payload = _fetch_boxscore_payload(game["game_id"], boxscore_cache)
            game_payload = payload.get("game", {}) or {}
            record_players(game_payload.get("homeTeam", {}) or {})
            record_players(game_payload.get("awayTeam", {}) or {})
        except Exception as exc:
            errors.append(f"{game['game_id']}: {exc}")

        if all(team_done(team_id) for team_id in rosters):
            break

        time.sleep(0.08)

    if not any(rosters[team_id] for team_id in rosters):
        raise RuntimeError("CDN boxscore roster sync found no players")

    return {team_id: list(players.values()) for team_id, players in rosters.items()}, errors


def _upsert_player_row(cursor, internal_team_id, player_row):
    jersey = player_row.get("jersey_number")
    jersey_number = int(jersey) if str(jersey).isdigit() else None

    cursor.execute("""
        INSERT INTO players
        (
            nba_player_id,
            team_id,
            first_name,
            last_name,
            position,
            jersey_number,
            height_in,
            weight_lb,
            birth_date,
            headshot_url,
            is_active
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
        ON DUPLICATE KEY UPDATE
            team_id = VALUES(team_id),
            first_name = VALUES(first_name),
            last_name = VALUES(last_name),
            position = COALESCE(VALUES(position), position),
            jersey_number = COALESCE(VALUES(jersey_number), jersey_number),
            height_in = COALESCE(VALUES(height_in), height_in),
            weight_lb = COALESCE(VALUES(weight_lb), weight_lb),
            birth_date = COALESCE(VALUES(birth_date), birth_date),
            headshot_url = COALESCE(VALUES(headshot_url), headshot_url),
            is_active = TRUE
    """, (
        player_row.get("nba_player_id"),
        internal_team_id,
        player_row.get("first_name") or "",
        player_row.get("last_name") or "",
        player_row.get("position"),
        jersey_number,
        player_row.get("height_in"),
        player_row.get("weight_lb"),
        player_row.get("birth_date"),
        player_row.get("headshot_url"),
    ))


def sync_players():
    """Sync team rosters into the players table.

    Order of attempts:
    1) stats.nba.com CommonTeamRoster (full bio fields when it works)
    2) public CDN boxscores from recent completed regular-season games

    The CDN fallback avoids stats.nba.com, which is timing out on the user's
    machine. It reliably provides player ids, names, jersey numbers, positions,
    and headshot ids. Height/weight/birth date may stay NULL in fallback mode.
    """
    connection = get_db_connection()
    if not connection:
        raise RuntimeError("Database connection failed")

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT team_id, nba_team_id, abbreviation
            FROM teams
            WHERE nba_team_id IS NOT NULL
            ORDER BY team_id
        """)
        teams_rows = cursor.fetchall() or []

        if not teams_rows:
            raise RuntimeError("No teams found with nba_team_id")

        today = datetime.date.today()
        season_start = today.year if today.month >= 10 else today.year - 1
        season_end = season_start + 1
        season_str = f"{season_start}-{str(season_end)[-2:]}"

        source_used = None
        stats_failures = []
        updated_players = 0
        synced_team_ids = set()

        # Try stats.nba.com first, but do not depend on it.
        for team in teams_rows:
            internal_team_id = team["team_id"]
            nba_team_id = str(team["nba_team_id"]).strip()
            if not nba_team_id:
                continue

            try:
                roster = commonteamroster.CommonTeamRoster(
                    team_id=nba_team_id,
                    season=season_str,
                    timeout=20,
                )
                data = roster.get_dict()
                rs = (data.get("resultSets") or [None])[0]
                if not rs:
                    raise RuntimeError("CommonTeamRoster returned no resultSets")

                headers = rs.get("headers") or []
                rows = rs.get("rowSet") or []

                def idx(col):
                    return headers.index(col) if col in headers else None

                i_player_id = idx("PLAYER_ID")
                i_player = idx("PLAYER")
                i_num = idx("NUM")
                i_pos = idx("POSITION")
                i_height = idx("HEIGHT")
                i_weight = idx("WEIGHT")
                i_birth = idx("BIRTH_DATE")

                team_count = 0
                for row in rows:
                    nba_player_id = str(row[i_player_id]).strip() if i_player_id is not None and row[i_player_id] else None
                    full_name = str(row[i_player]).strip() if i_player is not None and row[i_player] else ""
                    if not nba_player_id or not full_name:
                        continue

                    parts = full_name.split()
                    first_name = parts[0]
                    last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

                    birth_date_sql = None
                    birth_date = row[i_birth] if i_birth is not None else None
                    if birth_date:
                        try:
                            if isinstance(birth_date, datetime.date):
                                birth_date_sql = birth_date
                            else:
                                m = re.search(r"(\d{4}-\d{2}-\d{2})", str(birth_date).strip())
                                if m:
                                    birth_date_sql = m.group(1)
                        except Exception:
                            birth_date_sql = None

                    weight_lb = row[i_weight] if i_weight is not None else None
                    try:
                        weight_lb = int(weight_lb) if weight_lb not in (None, "", " ") else None
                    except Exception:
                        weight_lb = None

                    player_row = {
                        "nba_player_id": nba_player_id,
                        "first_name": first_name,
                        "last_name": last_name,
                        "position": _normalize_position(row[i_pos] if i_pos is not None else None),
                        "jersey_number": row[i_num] if i_num is not None else None,
                        "height_in": _parse_height_to_inches(row[i_height] if i_height is not None else None),
                        "weight_lb": weight_lb,
                        "birth_date": birth_date_sql,
                        "headshot_url": f"https://cdn.nba.com/headshots/nba/latest/260x190/{nba_player_id}.png",
                    }
                    _upsert_player_row(cursor, internal_team_id, player_row)
                    updated_players += 1
                    team_count += 1

                connection.commit()
                if team_count:
                    synced_team_ids.add(nba_team_id)
                    source_used = source_used or "stats.nba.com commonteamroster"
                    print(f"Synced players for team {team['abbreviation']} ({nba_team_id}) from stats.nba.com")

                time.sleep(0.35)
            except Exception as exc:
                stats_failures.append(f"{team['abbreviation']} ({nba_team_id}): {exc}")
                print(f"stats roster sync failed for team {team['abbreviation']} ({nba_team_id}): {exc}")
                # If stats is failing repeatedly on this machine, stop burning requests and use CDN fallback.
                if len(stats_failures) >= 2:
                    break

        if len(synced_team_ids) == len(teams_rows):
            cursor.close()
            return {
                "updated_players": updated_players,
                "teams_updated": len(synced_team_ids),
                "source": source_used or "stats.nba.com commonteamroster",
                "fallback_used": False,
                "errors": stats_failures[:5],
            }

        # CDN fallback for everything stats missed.
        remaining_team_ids = [
            str(team["nba_team_id"]).strip()
            for team in teams_rows
            if str(team["nba_team_id"]).strip() and str(team["nba_team_id"]).strip() not in synced_team_ids
        ]
        rosters_by_team, cdn_errors = _collect_rosters_from_cdn_boxscores(remaining_team_ids)

        for team in teams_rows:
            internal_team_id = team["team_id"]
            nba_team_id = str(team["nba_team_id"]).strip()
            roster_rows = rosters_by_team.get(nba_team_id, [])
            if not roster_rows:
                continue

            team_count = 0
            for player_row in roster_rows:
                _upsert_player_row(cursor, internal_team_id, player_row)
                updated_players += 1
                team_count += 1

            if team_count:
                synced_team_ids.add(nba_team_id)
                print(f"Synced players for team {team['abbreviation']} ({nba_team_id}) from CDN boxscores: {team_count} players")

        connection.commit()
        cursor.close()

        return {
            "updated_players": updated_players,
            "teams_updated": len(synced_team_ids),
            "source": "cdn.nba.com liveData boxscore" if cdn_errors or stats_failures else (source_used or "cdn.nba.com liveData boxscore"),
            "fallback_used": True,
            "errors": (stats_failures + cdn_errors)[:8],
        }

    finally:
        connection.close()


# ================= STATIC ROUTES =================

@app.route('/database/Logos/<path:filename>')
def team_logos(filename):
    # legacy route for local PNG logos (optional)
    return send_from_directory(os.path.join(app.root_path, 'database', 'static', 'Logos'), filename)


@app.route('/assets/<path:filename>')
def assets(filename):
    return send_from_directory(app.root_path, filename)


# ================= BASKETBALL API =================

@app.route('/api/admin/sync-teams')
def admin_sync():

    sync_teams()

    return {"message":"teams synced"}
    
@app.route('/api/admin/sync-standings')
def admin_sync_standings():
    try:
        result = sync_standings()
        return {"message": "standings synced", **result}
    except Exception as e:
        print(f"sync_standings failed: {e}")
        return jsonify({"error": "sync-standings failed", "details": str(e)}), 502

@app.route('/api/admin/sync-players')
def admin_sync_players():
    try:
        result = sync_players()
        return {"message": "players synced", **result}
    except Exception as e:
        print(f"sync_players failed: {e}")
        return jsonify({"error": "sync-players failed", "details": str(e)}), 502

@app.route('/api/teams', methods=['GET'])
def get_teams():
    """Return all teams from DB + current standings W/L + a usable NBA logo URL.

    Our DB uses an internal teams.team_id (AUTO_INCREMENT). The NBA id may be stored in teams.nba_team_id.
    The frontend should use `id` for navigation, and `nba_team_id` for NBA CDN assets.
    """
    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500

    # Determine columns and whether team_locations exists (older schemas may store city separately)
    teams_cols = _get_table_columns(connection, "teams")
    has_team_locations = False
    try:
        cur = connection.cursor()
        cur.execute("SHOW TABLES LIKE 'team_locations'")
        has_team_locations = cur.fetchone() is not None
        cur.close()
    except Exception:
        pass

    # Build SELECT dynamically so we don't crash if a column is missing
    select_parts = ["t.team_id AS team_id"]
    if "nba_team_id" in teams_cols:
        select_parts.append("t.nba_team_id AS nba_team_id")
    if "name" in teams_cols:
        select_parts.append("t.name AS name")
    if "abbreviation" in teams_cols:
        select_parts.append("t.abbreviation AS abbreviation")
    if "conference" in teams_cols:
        select_parts.append("t.conference AS conference")
    if "logo_url" in teams_cols:
        select_parts.append("t.logo_url AS logo_url")
    if "city" in teams_cols:
        select_parts.append("t.city AS city")

    join_sql = ""
    if "city" not in teams_cols and has_team_locations:
        select_parts.append("tl.city AS city")
        join_sql = " LEFT JOIN team_locations tl ON tl.team_id = t.team_id "

    query = f"SELECT {', '.join(select_parts)} FROM teams t{join_sql} ORDER BY t.team_id"
    cursor = connection.cursor(dictionary=True)
    cursor.execute(query)
    db_teams = cursor.fetchall() or []
    cursor.close()
    connection.close()

    # First-run helper: if DB is empty, attempt to sync teams once
    if not db_teams:
        try:
            sync_teams()
            connection = get_db_connection()
            if not connection:
                return jsonify([]), 200
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query)
            db_teams = cursor.fetchall() or []
            cursor.close()
            connection.close()
        except Exception as e:
            print("sync_teams failed:", e)

    # NBA lookup map (abbr -> nba_id)
    nba_list = teams.get_teams()
    abbr_map = {str(t.get("abbreviation", "")).upper(): int(t["id"]) for t in nba_list if t.get("abbreviation")}
    name_map = {str(t.get("full_name", "")).lower(): int(t["id"]) for t in nba_list if t.get("full_name")}

    def nba_id_for_row(row):
        raw = row.get("nba_team_id")
        if raw is not None and str(raw).strip().isdigit():
            return int(str(raw).strip())
        abbr = str(row.get("abbreviation") or "").upper()
        if abbr in abbr_map:
            return abbr_map[abbr]
        nm = str(row.get("name") or "").lower().strip()
        if nm in name_map:
            return name_map[nm]
        return None

    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        sort_by = request.args.get('sort', 'name')
        sort_options = {
            'name': 't.name',
            'conference': 't.conference, t.name',
            'wins': 'COALESCE(ts.wins, 0) DESC, t.name',
            'losses': 'COALESCE(ts.losses, 0) DESC, t.name'
        }
        order_clause = sort_options.get(sort_by, 't.name')

        query = f"""
            SELECT
                t.team_id AS id,
                t.nba_team_id,
                t.name,
                t.city,
                t.abbreviation,
                t.conference,
                t.logo_url,
                COALESCE(ts.wins, 0) AS wins,
                COALESCE(ts.losses, 0) AS losses
            FROM teams t
            LEFT JOIN team_standings ts ON t.team_id = ts.team_id
            ORDER BY {order_clause}
        """

        cursor.execute(query)
        teams_out = cursor.fetchall()
        cursor.close()

        return jsonify(teams_out), 200

    except Error as e:
        return jsonify({"error": str(e)}), 500

    finally:
        connection.close()


@app.route('/api/teams/<int:team_id>', methods=['GET'])
def get_team_details(team_id):
    """Return a single team's info + current W/L record.

    `team_id` here is the INTERNAL id in our DB. The NBA id is returned as `nba_team_id`.
    """
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({"error": "Database connection failed"}), 500

        teams_cols = _get_table_columns(connection, "teams")
        has_team_locations = False
        try:
            cur = connection.cursor()
            cur.execute("SHOW TABLES LIKE 'team_locations'")
            has_team_locations = cur.fetchone() is not None
            cur.close()
        except Exception:
            pass

        select_parts = [
            "t.team_id AS team_id",
            "ts.wins AS wins",
            "ts.losses AS losses",
        ]
        if "nba_team_id" in teams_cols:
            select_parts.append("t.nba_team_id AS nba_team_id")
        if "name" in teams_cols:
            select_parts.append("t.name AS name")
        if "abbreviation" in teams_cols:
            select_parts.append("t.abbreviation AS abbreviation")
        if "conference" in teams_cols:
            select_parts.append("t.conference AS conference")
        if "logo_url" in teams_cols:
            select_parts.append("t.logo_url AS logo_url")
        if "city" in teams_cols:
            select_parts.append("t.city AS city")
        if "arena_name" in teams_cols:
            select_parts.append("t.arena_name AS arena_name")

        join_parts = [" LEFT JOIN team_standings ts ON ts.team_id = t.team_id "]
        if has_team_locations:
            join_parts.append(" LEFT JOIN team_locations tl ON tl.team_id = t.team_id ")
            if "city" not in teams_cols:
                select_parts.append("tl.city AS city")
            if "arena_name" not in teams_cols:
                select_parts.append("tl.arena_name AS arena_name")

        join_sql = "".join(join_parts)
        query = f"SELECT {', '.join(select_parts)} FROM teams t{join_sql} WHERE t.team_id = %s"
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, (team_id,))
        row = cursor.fetchone()
        cursor.close()

        # Support direct NBA ids in the URL by resolving to the internal DB row.
        if not row and "nba_team_id" in teams_cols:
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query.replace("WHERE t.team_id = %s", "WHERE t.nba_team_id = %s"), (team_id,))
            row = cursor.fetchone()
            cursor.close()

        connection.close()

        if not row:
            return jsonify({"error": "Team not found"}), 404

        nba_list = teams.get_teams()
        abbr_map = {str(t.get("abbreviation", "")).upper(): t for t in nba_list if t.get("abbreviation")}

        nba_id = None
        raw = row.get("nba_team_id")
        if raw is not None and str(raw).strip().isdigit():
            nba_id = int(str(raw).strip())
        else:
            abbr = str(row.get("abbreviation") or "").upper()
            if abbr in abbr_map:
                nba_id = int(abbr_map[abbr]["id"])

        if not nba_id:
            # cannot map to NBA data
            return jsonify({
                "id": int(row["team_id"]),
                "nba_team_id": None,
                "name": row.get("name"),
                "full_name": row.get("name"),
                "abbreviation": row.get("abbreviation"),
                "city": row.get("city"),
                "wins": 0,
                "losses": 0,
                "conference": row.get("conference"),
                "logo_url": row.get("logo_url"),
                "arena": row.get("arena_name"),
            }), 200

        # standings: prefer the synced DB values from team_standings.
        wins = row.get("wins")
        losses = row.get("losses")
        conf_from_standings = None

        if wins is not None:
            try:
                wins = int(wins)
            except Exception:
                wins = 0
        if losses is not None:
            try:
                losses = int(losses)
            except Exception:
                losses = 0

        if wins is None or losses is None:
            wins = 0
            losses = 0
            try:
                standings = leaguestandings.LeagueStandings().get_dict()
                headers = standings["resultSets"][0]["headers"]
                rows = standings["resultSets"][0]["rowSet"]

                team_id_idx = headers.index("TeamID") if "TeamID" in headers else headers.index("TEAM_ID")
                wins_idx = headers.index("WINS") if "WINS" in headers else headers.index("W")
                losses_idx = headers.index("LOSSES") if "LOSSES" in headers else headers.index("L")
                conf_idx = headers.index("Conference") if "Conference" in headers else (headers.index("CONFERENCE") if "CONFERENCE" in headers else None)

                for r in rows:
                    if int(r[team_id_idx]) == int(nba_id):
                        wins = int(r[wins_idx])
                        losses = int(r[losses_idx])
                        if conf_idx is not None:
                            conf = r[conf_idx]
                            conf_from_standings = "East" if str(conf).lower().startswith("e") else ("West" if conf else None)
                        break
            except Exception as e:
                print("nba_api standings fallback failed:", e)

        # nba static info for nicer labels
        static_team = None
        for t in nba_list:
            if int(t.get("id")) == int(nba_id):
                static_team = t
                break

        full_name = static_team.get("full_name") if static_team else row.get("name")
        city = static_team.get("city") if static_team else row.get("city")
        nickname = static_team.get("nickname") if static_team else None
        abbr = static_team.get("abbreviation") if static_team else row.get("abbreviation")
        logo_url = row.get("logo_url") or f"https://cdn.nba.com/logos/nba/{nba_id}/primary/L/logo.svg"

        return jsonify({
            "id": int(row["team_id"]),
            "nba_team_id": nba_id,
            "full_name": full_name,
            "name": nickname or full_name,
            "city": city,
            "abbreviation": abbr,
            "wins": wins,
            "losses": losses,
            "conference": row.get("conference") or conf_from_standings,
            "logo_url": logo_url,
            "arena": row.get("arena_name"),
        }), 200

    except Exception as e:
        print(f"Error fetching team details: {e}")
        return jsonify({"error": str(e)}), 500



@app.route('/api/teams/<int:team_id>/players', methods=['GET'])
def get_team_players(team_id):

    connection = get_db_connection()
    if not connection:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                player_id AS id,
                nba_player_id,
                CONCAT(first_name, ' ', last_name) AS name,
                jersey_number AS jersey,
                position,
                CASE
                    WHEN height_in IS NOT NULL THEN CONCAT(FLOOR(height_in / 12), '-', MOD(height_in, 12))
                    ELSE NULL
                END AS height,
                CASE
                    WHEN headshot_url IS NOT NULL AND headshot_url <> '' THEN headshot_url
                    WHEN nba_player_id IS NOT NULL AND nba_player_id <> '' THEN CONCAT('https://cdn.nba.com/headshots/nba/latest/260x190/', nba_player_id, '.png')
                    ELSE NULL
                END AS headshot_url
            FROM players
            WHERE team_id = %s
            ORDER BY
                CASE
                    WHEN jersey_number IS NULL THEN 999
                    ELSE jersey_number
                END,
                last_name,
                first_name
        """, (team_id,))

        players = cursor.fetchall()
        cursor.close()
        connection.close()

        return jsonify(players), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

        def _find_players_list(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "players" and isinstance(v, list):
                        return v
                    found = _find_players_list(v)
                    if found is not None:
                        return found
            elif isinstance(obj, list):
                for item in obj:
                    found = _find_players_list(item)
                    if found is not None:
                        return found
            return None

        players = None


        # fallback to nba_api stats endpoint (needs NBA team id)
        if players is None:
            if not nba_id:
                return jsonify({"error": "Could not map to NBA team id for roster fallback"}), 500

            season_str = f"{season_start}-{str(season_end)[-2:]}"
            roster = commonteamroster.CommonTeamRoster(team_id=nba_id, season=season_str)
            rs = roster.get_dict()["resultSets"][0]
            headers = rs["headers"]
            rows = rs["rowSet"]

            def idx(col):
                return headers.index(col) if col in headers else None

            i_player = idx("PLAYER")
            i_num = idx("NUM")
            i_pos = idx("POSITION")
            i_height = idx("HEIGHT")
            i_player_id = idx("PLAYER_ID")

            players = []
            for r in rows:
                player_id = int(r[i_player_id]) if i_player_id is not None and r[i_player_id] else 0
                jersey = r[i_num] if i_num is not None and r[i_num] else "-"
                name = r[i_player] if i_player is not None else ""
                pos = r[i_pos] if i_pos is not None and r[i_pos] else "-"
                height = r[i_height] if i_height is not None and r[i_height] else "-"
                headshot_url = f"https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png" if player_id else ""
                players.append({
                    "id": player_id,
                    "name": name,
                    "jersey": str(jersey),
                    "position": pos,
                    "height": height,
                    "headshot_url": headshot_url,
                })

            players.sort(key=lambda x: int(x["jersey"]) if str(x["jersey"]).isdigit() else 999)

        return jsonify(players or []), 200

    except Exception as e:
        print(f"Error fetching roster: {e}")
        return jsonify({"error": str(e)}), 500


def get_arena_by_nba_team_id(nba_team_id):
    connection = get_db_connection()
    if not connection:
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT arena_name
            FROM teams
            WHERE nba_team_id = %s
        """, (str(nba_team_id),))
        row = cursor.fetchone()
        cursor.close()
        return row["arena_name"] if row else None
    except Exception as e:
        print("Arena lookup error:", e)
        return None
    finally:
        connection.close()

@app.route('/api/games/season', methods=['GET'])
def get_season_games():
    status_filter = str(request.args.get('status', 'all') or 'all').strip().lower()

    try:
        games = _fetch_regular_season_schedule_from_cdn()

        if status_filter in ('upcoming', 'scheduled'):
            games = [g for g in games if g.get('status_key') == 'scheduled']
            games.sort(key=lambda g: ((g.get('game_date') or ''), (g.get('start_time') or '99:99:99')))
        elif status_filter == 'live':
            games = [g for g in games if g.get('status_key') == 'live']
            games.sort(key=lambda g: ((g.get('game_date') or ''), (g.get('start_time') or '99:99:99')))
        elif status_filter in ('completed', 'final'):
            games = [g for g in games if g.get('status_key') == 'final']
            games.sort(key=lambda g: ((g.get('game_date') or ''), (g.get('start_time') or '00:00:00')), reverse=True)
        else:
            upcoming_games = [g for g in games if g.get('status_key') == 'scheduled']
            live_games = [g for g in games if g.get('status_key') == 'live']
            final_games = [g for g in games if g.get('status_key') == 'final']

            live_games.sort(key=lambda g: ((g.get('game_date') or ''), (g.get('start_time') or '99:99:99')))
            upcoming_games.sort(key=lambda g: ((g.get('game_date') or ''), (g.get('start_time') or '99:99:99')))
            final_games.sort(key=lambda g: ((g.get('game_date') or ''), (g.get('start_time') or '00:00:00')), reverse=True)
            games = live_games + upcoming_games + final_games

        return jsonify(games), 200
    except Exception as e:
        print(f"Error fetching season games: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/teams/<int:team_id>/games', methods=['GET'])
def get_team_games(team_id):
    try:
        team_lookup = _load_team_lookup()
        team_row = team_lookup['by_internal'].get(str(team_id))
        if not team_row:
            return jsonify({'error': 'Team not found'}), 404

        nba_team_id = str(team_row.get('nba_team_id') or '').strip()
        games = [
            game for game in _fetch_regular_season_schedule_from_cdn()
            if str(game.get('home_team', {}).get('nba_team_id') or '') == nba_team_id
            or str(game.get('away_team', {}).get('nba_team_id') or '') == nba_team_id
        ]

        games.sort(key=lambda g: ((g.get('game_date') or ''), (g.get('start_time') or '99:99:99')))
        return jsonify(games), 200
    except Exception as e:
        print(f"Error fetching team games: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/games/live', methods=['GET'])
def get_live_games():
    games = fetch_live_games()
    # Transform the data for frontend
    transformed_games = []
    for game in games:
        cache_game(game)

        home = game.get('homeTeam', {})
        away = game.get('awayTeam', {})

        home_nba_team_id = str(home.get('teamId'))
        away_nba_team_id = str(away.get('teamId'))

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT team_id FROM teams WHERE nba_team_id = %s", (home_nba_team_id,))
        home_row = cursor.fetchone()

        cursor.execute("SELECT team_id FROM teams WHERE nba_team_id = %s", (away_nba_team_id,))
        away_row = cursor.fetchone()

        cursor.close()
        connection.close()

        home_internal_id = home_row["team_id"] if home_row else None
        away_internal_id = away_row["team_id"] if away_row else None

        arena_name = get_arena_by_nba_team_id(home_nba_team_id)
        
        transformed_game = {
            'game_id': game.get('gameId'),
            'gameId': game.get('gameId'),  # Add camelCase for frontend
            'gameStatus': game.get('gameStatus'),
            'status': 'Live' if game.get('gameStatus') == 2 else ('Final' if game.get('gameStatus') == 3 else 'Upcoming'),
            'game_time': game.get('gameStatusText', 'TBD'),
            'arena_name': arena_name or 'Arena TBD',
            'home_team': {
                'id': home_internal_id or home.get('teamId'),
                'nba_team_id': home.get('teamId'),
                'full_name': f"{home.get('teamCity', '')} {home.get('teamName', '')}".strip(),
                'abbreviation': home.get('teamTricode', ''),
                'wins': home.get('wins', 0),
                'losses': home.get('losses', 0)
            },
            'away_team': {
                'id': away_internal_id or away.get('teamId'),
                'nba_team_id': away.get('teamId'),
                'full_name': f"{away.get('teamCity', '')} {away.get('teamName', '')}".strip(),
                'abbreviation': away.get('teamTricode', ''),
                'wins': away.get('wins', 0),
                'losses': away.get('losses', 0)
            },
            'home_score': home.get('score'),
            'away_score': away.get('score')
        }
        transformed_games.append(transformed_game)
    
    return jsonify(transformed_games)
    
def _game_detail_cache_path(game_id):
    safe_game_id = re.sub(r"[^0-9A-Za-z_-]", "", str(game_id or "").strip())
    if not safe_game_id:
        raise ValueError("Invalid game id")
    return os.path.join(GAME_DETAIL_CACHE_DIR, f"{safe_game_id}.json")


def _load_cached_boxscore_payload(game_id):
    try:
        cache_path = _game_detail_cache_path(game_id)
        if not os.path.exists(cache_path):
            return None

        with open(cache_path, 'r', encoding='utf-8') as cache_file:
            payload = json.load(cache_file)
            if payload:
                GAME_DETAIL_BOX_CACHE[str(game_id)] = payload
            return payload
    except Exception as exc:
        print(f"Game detail cache read failed for {game_id}: {exc}")
        return None


def _save_cached_boxscore_payload(game_id, payload):
    if not payload:
        return False

    try:
        cache_path = _game_detail_cache_path(game_id)
        with open(cache_path, 'w', encoding='utf-8') as cache_file:
            json.dump(payload, cache_file, ensure_ascii=False)
        GAME_DETAIL_BOX_CACHE[str(game_id)] = payload
        return True
    except Exception as exc:
        print(f"Game detail cache write failed for {game_id}: {exc}")
        return False


def _lookup_arena_name_by_nba_team_id(nba_team_id, default='Arena TBD'):
    team_id = str(nba_team_id or '').strip()
    if not team_id:
        return default

    connection = get_db_connection()
    if not connection:
        return default

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT arena_name
            FROM teams
            WHERE nba_team_id = %s
            LIMIT 1
            """,
            (team_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        return (row or {}).get('arena_name') or default
    except Exception as exc:
        print(f"Arena lookup failed for {team_id}: {exc}")
        return default
    finally:
        connection.close()


def _parse_iso_duration_seconds(raw_value):
    if raw_value in (None, '', 'PT00M00.00S'):
        return 0

    text_value = str(raw_value).strip()
    if not text_value:
        return 0

    mmss_match = re.match(r'^(\d+):(\d{2})$', text_value)
    if mmss_match:
        return int(mmss_match.group(1)) * 60 + int(mmss_match.group(2))

    iso_match = re.match(r'PT(?:(\d+)M)?([\d.]+)S', text_value)
    if iso_match:
        minutes = int(iso_match.group(1) or 0)
        seconds = int(float(iso_match.group(2) or 0))
        return minutes * 60 + seconds

    return 0


def _parse_iso_duration_minutes(raw_value):
    total_seconds = _parse_iso_duration_seconds(raw_value)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f'{minutes}:{seconds:02d}'


def _process_boxscore_players(team_data):
    players = []
    for player in (team_data or {}).get('players', []) or []:
        stats = player.get('statistics', {}) or {}
        raw_minutes = stats.get('minutes', 'PT00M00.00S')
        seconds = _parse_iso_duration_seconds(raw_minutes)

        players.append({
            'name': player.get('name', ''),
            'nameI': player.get('nameI', ''),
            'position': player.get('position', ''),
            'jerseyNum': player.get('jerseyNum', ''),
            'starter': player.get('starter', '') == '1',
            'played': player.get('played', '0') == '1',
            'minutes': _parse_iso_duration_minutes(raw_minutes),
            'points': int(stats.get('points') or 0),
            'rebounds': int(stats.get('reboundsTotal') or 0),
            'assists': int(stats.get('assists') or 0),
            'steals': int(stats.get('steals') or 0),
            'blocks': int(stats.get('blocks') or 0),
            'turnovers': int(stats.get('turnovers') or 0),
            'fouls': int(stats.get('foulsPersonal') or 0),
            'fgm': int(stats.get('fieldGoalsMade') or 0),
            'fga': int(stats.get('fieldGoalsAttempted') or 0),
            'fg_pct': float(stats.get('fieldGoalsPercentage') or 0),
            'fg3m': int(stats.get('threePointersMade') or 0),
            'fg3a': int(stats.get('threePointersAttempted') or 0),
            'fg3_pct': float(stats.get('threePointersPercentage') or 0),
            'ftm': int(stats.get('freeThrowsMade') or 0),
            'fta': int(stats.get('freeThrowsAttempted') or 0),
            'ft_pct': float(stats.get('freeThrowsPercentage') or 0),
            'plusMinus': int(stats.get('plusMinusPoints') or 0),
            'statistics': {
                'seconds': seconds,
                'minutesCalculated': seconds,
                'points': int(stats.get('points') or 0),
                'fieldGoalsMade': int(stats.get('fieldGoalsMade') or 0),
                'fieldGoalsAttempted': int(stats.get('fieldGoalsAttempted') or 0),
                'threePointersMade': int(stats.get('threePointersMade') or 0),
                'threePointersAttempted': int(stats.get('threePointersAttempted') or 0),
                'freeThrowsMade': int(stats.get('freeThrowsMade') or 0),
                'freeThrowsAttempted': int(stats.get('freeThrowsAttempted') or 0),
                'reboundsTotal': int(stats.get('reboundsTotal') or 0),
                'assists': int(stats.get('assists') or 0),
                'steals': int(stats.get('steals') or 0),
                'blocks': int(stats.get('blocks') or 0),
                'turnovers': int(stats.get('turnovers') or 0),
                'foulsPersonal': int(stats.get('foulsPersonal') or 0),
                'plusMinusPoints': int(stats.get('plusMinusPoints') or 0),
            }
        })
    return players


def _process_boxscore_team_stats(team_data):
    team_data = team_data or {}
    stats = team_data.get('statistics', {}) or {}
    players = team_data.get('players', []) or []

    team_stats = {
        'points': int(stats.get('points') or 0),
        'fgm': int(stats.get('fieldGoalsMade') or 0),
        'fga': int(stats.get('fieldGoalsAttempted') or 0),
        'fg_pct': float(stats.get('fieldGoalsPercentage') or 0),
        'fg3m': int(stats.get('threePointersMade') or 0),
        'fg3a': int(stats.get('threePointersAttempted') or 0),
        'fg3_pct': float(stats.get('threePointersPercentage') or 0),
        'ftm': int(stats.get('freeThrowsMade') or 0),
        'fta': int(stats.get('freeThrowsAttempted') or 0),
        'ft_pct': float(stats.get('freeThrowsPercentage') or 0),
        'rebounds': int(stats.get('reboundsTotal') or 0),
        'offReb': int(stats.get('reboundsOffensive') or 0),
        'defReb': int(stats.get('reboundsDefensive') or 0),
        'assists': int(stats.get('assists') or 0),
        'steals': int(stats.get('steals') or 0),
        'blocks': int(stats.get('blocks') or 0),
        'turnovers': int(stats.get('turnoversTotal') or stats.get('turnovers') or 0),
        'fouls': int(stats.get('foulsPersonal') or 0),
        'pointsInPaint': int(stats.get('pointsInThePaint') or 0),
        'fastBreakPoints': int(stats.get('pointsFastBreak') or 0),
        'benchPoints': int(stats.get('benchPoints') or 0),
        'biggestLead': int(stats.get('biggestLead') or 0),
    }

    rebuild_needed = (
        int(team_data.get('score') or 0) > 0 and (
            team_stats['fgm'] == 0 or
            team_stats['fga'] == 0 or
            team_stats['rebounds'] == 0
        )
    )

    if rebuild_needed:
        rebuilt = {
            'points': 0,
            'fgm': 0,
            'fga': 0,
            'fg3m': 0,
            'fg3a': 0,
            'ftm': 0,
            'fta': 0,
            'rebounds': 0,
            'assists': 0,
            'steals': 0,
            'blocks': 0,
            'turnovers': 0,
            'fouls': 0,
        }

        for player in players:
            if player.get('played') != '1':
                continue

            pstats = player.get('statistics', {}) or {}
            rebuilt['points'] += int(pstats.get('points') or 0)
            rebuilt['fgm'] += int(pstats.get('fieldGoalsMade') or 0)
            rebuilt['fga'] += int(pstats.get('fieldGoalsAttempted') or 0)
            rebuilt['fg3m'] += int(pstats.get('threePointersMade') or 0)
            rebuilt['fg3a'] += int(pstats.get('threePointersAttempted') or 0)
            rebuilt['ftm'] += int(pstats.get('freeThrowsMade') or 0)
            rebuilt['fta'] += int(pstats.get('freeThrowsAttempted') or 0)
            rebuilt['rebounds'] += int(pstats.get('reboundsTotal') or 0)
            rebuilt['assists'] += int(pstats.get('assists') or 0)
            rebuilt['steals'] += int(pstats.get('steals') or 0)
            rebuilt['blocks'] += int(pstats.get('blocks') or 0)
            rebuilt['turnovers'] += int(pstats.get('turnovers') or 0)
            rebuilt['fouls'] += int(pstats.get('foulsPersonal') or 0)

        team_stats['points'] = rebuilt['points']
        team_stats['fgm'] = rebuilt['fgm']
        team_stats['fga'] = rebuilt['fga']
        team_stats['fg3m'] = rebuilt['fg3m']
        team_stats['fg3a'] = rebuilt['fg3a']
        team_stats['ftm'] = rebuilt['ftm']
        team_stats['fta'] = rebuilt['fta']
        team_stats['rebounds'] = rebuilt['rebounds']
        team_stats['assists'] = rebuilt['assists']
        team_stats['steals'] = rebuilt['steals']
        team_stats['blocks'] = rebuilt['blocks']
        team_stats['turnovers'] = rebuilt['turnovers']
        team_stats['fouls'] = rebuilt['fouls']

        team_stats['fg_pct'] = round((rebuilt['fgm'] / rebuilt['fga']) * 100, 1) if rebuilt['fga'] > 0 else 0
        team_stats['fg3_pct'] = round((rebuilt['fg3m'] / rebuilt['fg3a']) * 100, 1) if rebuilt['fg3a'] > 0 else 0
        team_stats['ft_pct'] = round((rebuilt['ftm'] / rebuilt['fta']) * 100, 1) if rebuilt['fta'] > 0 else 0

    team_stats['reb'] = team_stats['rebounds']
    team_stats['ast'] = team_stats['assists']
    team_stats['stl'] = team_stats['steals']
    team_stats['blk'] = team_stats['blocks']

    return team_stats


def _schedule_status_to_game_status(schedule_game):
    status_key = (schedule_game or {}).get('status_key')
    if status_key == 'final':
        return 3
    if status_key == 'live':
        return 2
    return 1


def _get_boxscore_payload_with_cache(game_id, schedule_game=None):
    game_id = str(game_id or '').strip()
    if not game_id:
        raise ValueError('Missing game id')

    cached_payload = _load_cached_boxscore_payload(game_id)
    if cached_payload and (schedule_game or {}).get('status_key') == 'final':
        return cached_payload

    try:
        payload = _fetch_boxscore_payload(game_id, GAME_DETAIL_BOX_CACHE)
        if payload and payload.get('game'):
            _save_cached_boxscore_payload(game_id, payload)
        return payload
    except Exception as exc:
        print(f"Live boxscore fetch failed for {game_id}: {exc}")
        if cached_payload:
            return cached_payload
        raise


def _transform_boxscore_payload(payload, schedule_game=None):
    game = (payload or {}).get('game', {}) or {}
    if not game:
        raise RuntimeError('Game detail payload was empty')

    home_team = game.get('homeTeam', {}) or {}
    away_team = game.get('awayTeam', {}) or {}

    arena_name = (
        game.get('arenaName')
        or (schedule_game or {}).get('arena_name')
        or _lookup_arena_name_by_nba_team_id(home_team.get('teamId'))
        or 'Arena TBD'
    )

    game_status = _safe_int(game.get('gameStatus'))
    if game_status is None:
        game_status = _schedule_status_to_game_status(schedule_game)

    game_status_text = str(
        game.get('gameStatusText')
        or (schedule_game or {}).get('game_time')
        or (schedule_game or {}).get('status')
        or ''
    ).strip()

    if not game_status_text:
        game_status_text = 'Final' if game_status == 3 else ('Live' if game_status == 2 else 'Upcoming')

    return {
        'gameId': game.get('gameId') or (schedule_game or {}).get('game_id') or '',
        'gameStatus': game_status,
        'gameStatusText': game_status_text,
        'period': _safe_int(game.get('period')) or 0,
        'gameClock': game.get('gameClock', ''),
        'arena_name': arena_name,
        'homeTeam': {
            'teamId': home_team.get('teamId', 0),
            'teamName': home_team.get('teamName', ''),
            'teamCity': home_team.get('teamCity', ''),
            'teamTricode': home_team.get('teamTricode', ''),
            'score': home_team.get('score', 0),
            'periods': home_team.get('periods', []),
            'players': _process_boxscore_players(home_team),
            'statistics': _process_boxscore_team_stats(home_team),
        },
        'awayTeam': {
            'teamId': away_team.get('teamId', 0),
            'teamName': away_team.get('teamName', ''),
            'teamCity': away_team.get('teamCity', ''),
            'teamTricode': away_team.get('teamTricode', ''),
            'score': away_team.get('score', 0),
            'periods': away_team.get('periods', []),
            'players': _process_boxscore_players(away_team),
            'statistics': _process_boxscore_team_stats(away_team),
        }
    }


def _sync_completed_game_details(limit=None, offset=0, force=False):
    schedule_games = _fetch_regular_season_schedule_from_cdn()
    completed_games = [game for game in schedule_games if game.get('status_key') == 'final']
    completed_games.sort(key=lambda game: ((game.get('game_date') or ''), (game.get('start_time') or '00:00:00')))

    total_available = len(completed_games)
    if offset and offset > 0:
        completed_games = completed_games[offset:]

    if limit and limit > 0:
        completed_games = completed_games[:limit]

    synced = 0
    skipped = 0
    schedule_cached = 0
    errors = []
    request_cache = {}

    for schedule_game in completed_games:
        game_id = str(schedule_game.get('game_id') or '').strip()
        if not game_id:
            continue

        try:
            cache_path = _game_detail_cache_path(game_id)
        except Exception:
            continue

        try:
            internal_id = _cache_schedule_game_record(schedule_game)
            if internal_id:
                schedule_cached += 1

            if not force and os.path.exists(cache_path):
                skipped += 1
                continue

            payload = _fetch_boxscore_payload(game_id, request_cache)
            if not payload or not payload.get('game'):
                raise RuntimeError('Boxscore payload was empty')

            _save_cached_boxscore_payload(game_id, payload)
            synced += 1
        except Exception as exc:
            errors.append({'game_id': game_id, 'error': str(exc)})

    return {
        'total_available_completed_games': total_available,
        'offset': offset,
        'requested_count': len(completed_games),
        'synced_game_details': synced,
        'skipped_existing_cache': skipped,
        'schedule_records_cached': schedule_cached,
        'errors': errors,
        'cache_directory': GAME_DETAIL_CACHE_DIR,
    }


@app.route('/api/admin/sync-completed-game-details', methods=['GET', 'POST'])
def sync_completed_game_details():
    try:
        args = request.get_json(silent=True) or {}
        limit_raw = request.args.get('limit', args.get('limit'))
        offset_raw = request.args.get('offset', args.get('offset'))
        force_raw = request.args.get('force', args.get('force', False))

        limit = _safe_int(limit_raw)
        offset = _safe_int(offset_raw) or 0
        force = str(force_raw).strip().lower() in {'1', 'true', 'yes', 'y', 'on'}

        result = _sync_completed_game_details(limit=limit, offset=offset, force=force)
        return jsonify(result), 200
    except Exception as exc:
        print(f"Completed game detail sync error: {exc}")
        return jsonify({'error': str(exc)}), 500


@app.route('/api/games/<game_id>', methods=['GET'])
def get_game_detail(game_id):
    """Get detailed game information for live and completed games."""
    schedule_game = None

    try:
        try:
            schedule_game = _find_schedule_game_by_id(game_id)
            if schedule_game:
                _cache_schedule_game_record(schedule_game)
        except Exception as lookup_exc:
            print(f"Schedule lookup failed for game detail {game_id}: {lookup_exc}")

        payload = _get_boxscore_payload_with_cache(game_id, schedule_game=schedule_game)
        result = _transform_boxscore_payload(payload, schedule_game=schedule_game)
        return jsonify(_make_json_safe(result)), 200
    except requests.HTTPError as exc:
        status_code = getattr(exc.response, 'status_code', 500) or 500
        if (schedule_game or {}).get('status_key') == 'scheduled':
            return jsonify({'error': 'Game detail is not available yet for this upcoming game.'}), 404
        return jsonify({'error': f'Could not load game detail: {exc}'}), status_code
    except Exception as exc:
        print(f"Game detail error for {game_id}: {exc}")
        if (schedule_game or {}).get('status_key') == 'scheduled':
            return jsonify({'error': 'Game detail is not available yet for this upcoming game.'}), 404
        return jsonify({'error': str(exc)}), 500


# ================= QOTD API =================

@app.route('/api/qotd/<date>', methods=['GET'])
def get_qotd_by_date(date):

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT question_id, question_text, question_date
            FROM qotd_questions
            WHERE question_date = %s AND is_open = TRUE
        """, (date,))
        question = cursor.fetchone()
        cursor.close()

        return jsonify(question), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


# 🔹 Get comments (joins users table to show username)
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT question_id, question_text, question_date
        FROM qotd_questions
        WHERE question_date = %s AND is_open = TRUE
    """, (date,))

    question = cursor.fetchone()

    cursor.close()
    connection.close()

    return jsonify(question)


@app.route('/api/qotd/<int:question_id>/comments', methods=['GET'])
def get_qotd_comments(question_id):

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                c.comment_id,
                c.question_id,
                c.user_id,
                c.parent_comment_id,
                c.comment_text,
                c.created_at,
                COALESCE(u.email, CONCAT('User ', u.user_id)) AS user_name,
                SUM(CASE WHEN v.vote_value = 1 THEN 1 ELSE 0 END) AS upvotes,
                SUM(CASE WHEN v.vote_value = -1 THEN 1 ELSE 0 END) AS downvotes
            FROM qotd_comments c
            JOIN users u ON c.user_id = u.user_id
            LEFT JOIN qotd_comment_votes v ON c.comment_id = v.comment_id
            WHERE c.question_id = %s
            GROUP BY
                c.comment_id,
                c.question_id,
                c.user_id,
                c.parent_comment_id,
                c.comment_text,
                c.created_at,
                u.email,
                u.user_id
            ORDER BY c.created_at ASC
        """, (question_id,))
        comments = cursor.fetchall()
        cursor.close()

        return jsonify(comments), 200

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/qotd/comment', methods=['POST'])
def post_qotd_comment():

    data = request.json

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO qotd_comments
            (question_id, user_id, parent_comment_id, comment_text, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (
            data['question_id'],
            data['user_id'],
            data.get('parent_comment_id'),
            data['comment_text']
        ))

        connection.commit()
        cursor.close()

        return jsonify({'message': 'Comment added'}), 201

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/qotd/vote', methods=['POST'])
def vote_qotd_comment():
    """
    Upvote or downvote a QOTD comment.
    Expects: { comment_id, user_id, vote_value (1 or -1) }
    """
    data = request.json

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO qotd_comment_votes (comment_id, user_id, vote_value, created_at)
            VALUES (%s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE vote_value = VALUES(vote_value)
        """, (
            data['comment_id'],
            data['user_id'],
            data['vote_value']
        ))

        connection.commit()
        cursor.close()

        return jsonify({'message': 'Vote recorded'}), 200

    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()



# ================= FAVORITES / ALERTS / GAME COMMENTS API =================

@app.route('/api/auth/register', methods=['POST'])
def register_auth_user():
    ensure_user_account_columns()
    data = request.get_json() or {}

    email = str(data.get('email') or '').strip().lower()
    username = str(data.get('username') or '').strip()
    display_name = str(data.get('display_name') or '').strip()
    password = str(data.get('password') or '')

    if not email or '@' not in email:
        return jsonify({'error': 'A valid email is required.'}), 400
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters.'}), 400
    if username and len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters.'}), 400

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("SELECT user_id FROM users WHERE email = %s LIMIT 1", (email,))
        if cursor.fetchone():
            cursor.close()
            return jsonify({'error': 'That email is already in use.'}), 409

        if username:
            cursor.execute("SELECT user_id FROM users WHERE username = %s LIMIT 1", (username,))
            if cursor.fetchone():
                cursor.close()
                return jsonify({'error': 'That username is already taken.'}), 409

        cursor.execute(
            """
            INSERT INTO users (email, username, display_name, bio, password_hash, role)
            VALUES (%s, %s, %s, %s, %s, 'base')
            """,
            (email, username or None, display_name or None, '', generate_password_hash(password)),
        )
        connection.commit()
        user_id = cursor.lastrowid

        cursor.execute(
            """
            SELECT user_id, email, username, display_name, bio, profile_image_url, role
            FROM users
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,),
        )
        user = _normalize_auth_user_row(cursor.fetchone())
        cursor.close()

        token = _issue_auth_token(user_id)
        return jsonify({'token': token, 'user': user}), 201
    except Exception as exc:
        print(f"Register error: {exc}")
        return jsonify({'error': str(exc)}), 500
    finally:
        connection.close()


@app.route('/api/auth/login', methods=['POST'])
def login_auth_user():
    ensure_user_account_columns()
    data = request.get_json() or {}

    identifier = str(data.get('identifier') or data.get('email') or '').strip()
    password = str(data.get('password') or '')

    if not identifier or not password:
        return jsonify({'error': 'Identifier and password are required.'}), 400

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        row = _get_auth_user_by_identifier(cursor, identifier)
        cursor.close()

        if not row or not row.get('password_hash') or not check_password_hash(row.get('password_hash'), password):
            return jsonify({'error': 'Invalid login credentials.'}), 401

        token = _issue_auth_token(row.get('user_id'))
        return jsonify({'token': token, 'user': _normalize_auth_user_row(row)}), 200
    except Exception as exc:
        print(f"Login error: {exc}")
        return jsonify({'error': str(exc)}), 500
    finally:
        connection.close()


@app.route('/api/auth/logout', methods=['POST'])
def logout_auth_user():
    auth_header = request.headers.get('Authorization', '').strip()
    token = ''
    if auth_header.lower().startswith('bearer '):
        token = auth_header.split(' ', 1)[1].strip()
    elif request.headers.get('X-Auth-Token'):
        token = request.headers.get('X-Auth-Token', '').strip()

    if token:
        AUTH_SESSIONS.pop(token, None)

    return jsonify({'success': True}), 200


@app.route('/api/users/<int:user_id>/profile', methods=['GET'])
def get_user_profile(user_id):
    ensure_user_account_columns()

    auth_user_id = _get_authorized_user_id()
    if auth_user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT user_id, email, username, display_name, bio, profile_image_url, role
            FROM users
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,),
        )
        row = cursor.fetchone()
        cursor.close()

        if not row:
            return jsonify({'error': 'User not found'}), 404

        return jsonify(_normalize_auth_user_row(row)), 200
    except Exception as exc:
        print(f"Profile fetch error: {exc}")
        return jsonify({'error': str(exc)}), 500
    finally:
        connection.close()


@app.route('/api/users/<int:user_id>/profile', methods=['PUT'])
def update_user_profile(user_id):
    ensure_user_account_columns()

    auth_user_id = _get_authorized_user_id()
    if auth_user_id != user_id:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json() or {}
    email = str(data.get('email') or '').strip().lower()
    username = str(data.get('username') or '').strip()
    display_name = str(data.get('display_name') or '').strip()
    bio = str(data.get('bio') or '').strip()
    profile_image_url = str(data.get('profile_image_url') or '').strip()
    current_password = str(data.get('current_password') or '')
    new_password = str(data.get('new_password') or '')

    if not email or '@' not in email:
        return jsonify({'error': 'A valid email is required.'}), 400
    if username and len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters.'}), 400
    if new_password and len(new_password) < 6:
        return jsonify({'error': 'New password must be at least 6 characters.'}), 400

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT user_id, email, username, display_name, bio, profile_image_url, password_hash, role
            FROM users
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,),
        )
        existing = cursor.fetchone()
        if not existing:
            cursor.close()
            return jsonify({'error': 'User not found'}), 404

        cursor.execute("SELECT user_id FROM users WHERE email = %s AND user_id <> %s LIMIT 1", (email, user_id))
        if cursor.fetchone():
            cursor.close()
            return jsonify({'error': 'That email is already in use.'}), 409

        if username:
            cursor.execute("SELECT user_id FROM users WHERE username = %s AND user_id <> %s LIMIT 1", (username, user_id))
            if cursor.fetchone():
                cursor.close()
                return jsonify({'error': 'That username is already taken.'}), 409

        password_hash = existing.get('password_hash')
        if new_password:
            if not password_hash or not current_password or not check_password_hash(password_hash, current_password):
                cursor.close()
                return jsonify({'error': 'Current password is incorrect.'}), 400
            password_hash = generate_password_hash(new_password)

        cursor.execute(
            """
            UPDATE users
            SET email = %s,
                username = %s,
                display_name = %s,
                bio = %s,
                profile_image_url = %s,
                password_hash = %s
            WHERE user_id = %s
            """,
            (email, username or None, display_name or None, bio, profile_image_url or None, password_hash, user_id),
        )
        connection.commit()

        cursor.execute(
            """
            SELECT user_id, email, username, display_name, bio, profile_image_url, role
            FROM users
            WHERE user_id = %s
            LIMIT 1
            """,
            (user_id,),
        )
        updated = _normalize_auth_user_row(cursor.fetchone())
        cursor.close()
        return jsonify(updated), 200
    except Exception as exc:
        print(f"Profile update error: {exc}")
        return jsonify({'error': str(exc)}), 500
    finally:
        connection.close()


@app.route('/api/users/<int:user_id>/favorites', methods=['GET'])
def get_user_favorites(user_id):
    if not get_user_by_id(user_id):
        return jsonify({'error': 'User not found'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                f.favorite_id,
                f.team_id,
                t.name,
                t.city,
                t.abbreviation,
                t.nba_team_id,
                t.logo_url,
                f.created_at
            FROM favorites f
            JOIN teams t ON f.team_id = t.team_id
            WHERE f.user_id = %s
            ORDER BY f.created_at DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall() or []
        cursor.close()
        return jsonify(_make_json_safe(rows)), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/users/<int:user_id>/favorites/<int:team_id>', methods=['GET'])
def get_favorite_status(user_id, team_id):
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT favorite_id FROM favorites WHERE user_id = %s AND team_id = %s LIMIT 1",
            (user_id, team_id),
        )
        row = cursor.fetchone()
        cursor.close()
        return jsonify({'is_favorite': bool(row)}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/users/<int:user_id>/favorites', methods=['POST'])
def add_user_favorite(user_id):
    data = request.get_json(silent=True) or {}
    team_id = data.get('team_id')

    if not team_id:
        return jsonify({'error': 'team_id is required'}), 400

    if not get_user_by_id(user_id):
        return jsonify({'error': 'User not found'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor()
        cursor.execute("SELECT team_id FROM teams WHERE team_id = %s", (team_id,))
        if not cursor.fetchone():
            cursor.close()
            return jsonify({'error': 'Team not found'}), 404

        cursor.execute(
            """
            INSERT INTO favorites (user_id, team_id, created_at)
            VALUES (%s, %s, NOW())
            ON DUPLICATE KEY UPDATE created_at = created_at
            """,
            (user_id, team_id),
        )
        connection.commit()
        cursor.close()
        return jsonify({'message': 'Favorite team saved'}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/users/<int:user_id>/favorites/<int:team_id>', methods=['DELETE'])
def remove_user_favorite(user_id, team_id):
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM favorites WHERE user_id = %s AND team_id = %s",
            (user_id, team_id),
        )
        connection.commit()
        deleted = cursor.rowcount
        cursor.close()
        if deleted == 0:
            return jsonify({'error': 'Favorite team not found'}), 404
        return jsonify({'message': 'Favorite team removed'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/games/<game_identifier>/comments', methods=['GET'])
def get_game_comments(game_identifier):
    internal_game_id = resolve_internal_game_id(game_identifier)
    if not internal_game_id:
        return jsonify({'error': 'Game not found in database'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                gc.comment_id,
                gc.game_id,
                gc.user_id,
                gc.parent_comment_id,
                gc.comment_text,
                gc.created_at,
                COALESCE(u.email, CONCAT('User ', u.user_id)) AS user_name
            FROM game_comments gc
            JOIN users u ON gc.user_id = u.user_id
            WHERE gc.game_id = %s
            ORDER BY gc.created_at ASC
            """,
            (internal_game_id,),
        )
        rows = cursor.fetchall() or []
        cursor.close()
        return jsonify(_make_json_safe(rows)), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/games/<game_identifier>/comments', methods=['POST'])
def post_game_comment(game_identifier):
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    comment_text = (data.get('comment_text') or '').strip()
    parent_comment_id = data.get('parent_comment_id')

    if not user_id or not comment_text:
        return jsonify({'error': 'user_id and comment_text are required'}), 400

    if len(comment_text) > 500:
        return jsonify({'error': 'Comment must be 500 characters or less'}), 400

    if not get_user_by_id(user_id):
        return jsonify({'error': 'User not found'}), 404

    internal_game_id = resolve_internal_game_id(game_identifier)
    if not internal_game_id:
        return jsonify({'error': 'Game not found in database'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        if parent_comment_id:
            cursor.execute(
                "SELECT comment_id FROM game_comments WHERE comment_id = %s AND game_id = %s LIMIT 1",
                (parent_comment_id, internal_game_id),
            )
            if not cursor.fetchone():
                cursor.close()
                return jsonify({'error': 'Parent comment not found for this game'}), 404

        cursor.close()
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO game_comments (user_id, game_id, parent_comment_id, comment_text, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            """,
            (user_id, internal_game_id, parent_comment_id, comment_text),
        )
        connection.commit()
        new_id = cursor.lastrowid
        cursor.close()
        return jsonify({'message': 'Game comment added', 'comment_id': new_id}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/games/<game_identifier>/alerts/<int:user_id>', methods=['GET'])
def get_game_alert_status(game_identifier, user_id):
    internal_game_id = resolve_internal_game_id(game_identifier)
    if not internal_game_id:
        return jsonify({'error': 'Game not found in database'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT alert_rule_id, rule_type
            FROM alert_rules
            WHERE user_id = %s AND game_id = %s AND rule_type = 'game_start'
            LIMIT 1
            """,
            (user_id, internal_game_id),
        )
        row = cursor.fetchone()
        cursor.close()
        return jsonify({'has_alert': bool(row), 'rule_type': 'game_start'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/games/<game_identifier>/alerts', methods=['POST'])
def add_game_alert(game_identifier):
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    if not get_user_by_id(user_id):
        return jsonify({'error': 'User not found'}), 404

    internal_game_id = resolve_internal_game_id(game_identifier)
    if not internal_game_id:
        return jsonify({'error': 'Game not found in database'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT alert_rule_id
            FROM alert_rules
            WHERE user_id = %s AND game_id = %s AND rule_type = 'game_start'
            LIMIT 1
            """,
            (user_id, internal_game_id),
        )
        existing = cursor.fetchone()
        cursor.close()

        if existing:
            return jsonify({'message': 'Game alert already exists'}), 200

        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO alert_rules (user_id, game_id, team_id, rule_type, created_at)
            VALUES (%s, %s, NULL, 'game_start', NOW())
            """,
            (user_id, internal_game_id),
        )
        connection.commit()
        cursor.close()
        return jsonify({'message': 'Game alert saved'}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/games/<game_identifier>/alerts/<int:user_id>', methods=['DELETE'])
def remove_game_alert(game_identifier, user_id):
    internal_game_id = resolve_internal_game_id(game_identifier)
    if not internal_game_id:
        return jsonify({'error': 'Game not found in database'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM alert_rules WHERE user_id = %s AND game_id = %s AND rule_type = 'game_start'",
            (user_id, internal_game_id),
        )
        connection.commit()
        deleted = cursor.rowcount
        cursor.close()
        if deleted == 0:
            return jsonify({'error': 'Game alert not found'}), 404
        return jsonify({'message': 'Game alert removed'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()




def _get_user_game_collection(user_id, collection_type='watchlist'):
    connection = get_db_connection()
    if not connection:
        return None, 'Database connection failed'

    if collection_type == 'watchlist':
        join_sql = "JOIN watchlist item ON item.game_id = g.game_id"
        item_id_sql = "item.watch_id AS item_id"
        where_sql = "item.user_id = %s"
    elif collection_type == 'alerts':
        join_sql = "JOIN alert_rules item ON item.game_id = g.game_id AND item.rule_type = 'game_start'"
        item_id_sql = "item.alert_rule_id AS item_id"
        where_sql = "item.user_id = %s"
    else:
        connection.close()
        return None, 'Invalid collection type'

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            f"""
            SELECT
                {item_id_sql},
                item.created_at AS saved_at,
                g.game_id,
                COALESCE(g.nba_game_id, CAST(g.game_id AS CHAR)) AS game_identifier,
                g.nba_game_id,
                g.game_date,
                g.start_time,
                g.status,
                gc.home_score,
                gc.away_score,
                gc.period,
                gc.clock,
                ht.team_id AS home_team_id,
                ht.name AS home_name,
                ht.city AS home_city,
                ht.abbreviation AS home_abbreviation,
                ht.nba_team_id AS home_nba_team_id,
                ht.logo_url AS home_logo_url,
                COALESCE(hs.wins, 0) AS home_wins,
                COALESCE(hs.losses, 0) AS home_losses,
                at.team_id AS away_team_id,
                at.name AS away_name,
                at.city AS away_city,
                at.abbreviation AS away_abbreviation,
                at.nba_team_id AS away_nba_team_id,
                at.logo_url AS away_logo_url,
                COALESCE(aws.wins, 0) AS away_wins,
                COALESCE(aws.losses, 0) AS away_losses
            FROM games g
            {join_sql}
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            LEFT JOIN team_standings hs ON ht.team_id = hs.team_id
            LEFT JOIN team_standings aws ON at.team_id = aws.team_id
            LEFT JOIN game_cache gc ON g.game_id = gc.game_id
            WHERE {where_sql}
            ORDER BY
                CASE
                    WHEN g.status = 'live' THEN 0
                    WHEN g.status = 'scheduled' THEN 1
                    ELSE 2
                END,
                g.game_date DESC,
                item.created_at DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall() or []
        cursor.close()
        return rows, None
    except Error as e:
        return None, str(e)
    finally:
        connection.close()


def _get_user_comment_replies(user_id):
    connection = get_db_connection()
    if not connection:
        return None, 'Database connection failed'

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                'game' AS source_type,
                reply.comment_id AS reply_id,
                reply.comment_text AS reply_text,
                reply.created_at AS reply_created_at,
                parent.comment_id AS your_comment_id,
                parent.comment_text AS your_comment_text,
                reply.user_id AS replier_user_id,
                COALESCE(reply_user.email, CONCAT('User ', reply.user_id)) AS replier_name,
                g.game_id,
                COALESCE(g.nba_game_id, g.game_id) AS game_identifier,
                g.nba_game_id,
                g.game_date,
                ht.team_id AS home_team_id,
                ht.name AS home_name,
                ht.city AS home_city,
                ht.abbreviation AS home_abbreviation,
                ht.nba_team_id AS home_nba_team_id,
                at.team_id AS away_team_id,
                at.name AS away_name,
                at.city AS away_city,
                at.abbreviation AS away_abbreviation,
                at.nba_team_id AS away_nba_team_id,
                NULL AS question_id,
                NULL AS question_date,
                NULL AS question_text
            FROM game_comments parent
            JOIN game_comments reply ON reply.parent_comment_id = parent.comment_id
            JOIN users reply_user ON reply.user_id = reply_user.user_id
            JOIN games g ON parent.game_id = g.game_id
            JOIN teams ht ON g.home_team_id = ht.team_id
            JOIN teams at ON g.away_team_id = at.team_id
            WHERE parent.user_id = %s
            AND reply.user_id <> parent.user_id

            UNION ALL

            SELECT
                'qotd' AS source_type,
                reply.comment_id AS reply_id,
                reply.comment_text AS reply_text,
                reply.created_at AS reply_created_at,
                parent.comment_id AS your_comment_id,
                parent.comment_text AS your_comment_text,
                reply.user_id AS replier_user_id,
                COALESCE(reply_user.email, CONCAT('User ', reply.user_id)) AS replier_name,
                NULL AS game_id,
                NULL AS game_identifier,
                NULL AS nba_game_id,
                NULL AS game_date,
                NULL AS home_team_id,
                NULL AS home_name,
                NULL AS home_city,
                NULL AS home_abbreviation,
                NULL AS home_nba_team_id,
                NULL AS away_team_id,
                NULL AS away_name,
                NULL AS away_city,
                NULL AS away_abbreviation,
                NULL AS away_nba_team_id,
                q.question_id,
                q.question_date,
                q.question_text
            FROM qotd_comments parent
            JOIN qotd_comments reply ON reply.parent_comment_id = parent.comment_id
            JOIN users reply_user ON reply.user_id = reply_user.user_id
            JOIN qotd_questions q ON parent.question_id = q.question_id
            WHERE parent.user_id = %s
            AND reply.user_id <> parent.user_id

            ORDER BY reply_created_at DESC
            LIMIT 50;
            """,
            (user_id, user_id),
        )
        rows = cursor.fetchall() or []
        cursor.close()
        return rows, None
    except Error as e:
        return None, str(e)
    finally:
        connection.close()


@app.route('/api/users/<int:user_id>/watchlist', methods=['GET'])
def get_user_watchlist(user_id):
    if not get_user_by_id(user_id):
        return jsonify({'error': 'User not found'}), 404

    rows, error = _get_user_game_collection(user_id, 'watchlist')
    if error:
        status = 500 if error == 'Database connection failed' else 500
        return jsonify({'error': error}), status
    return jsonify(_make_json_safe(rows)), 200


@app.route('/api/games/<game_identifier>/watchlist/<int:user_id>', methods=['GET'])
def get_watchlist_status(game_identifier, user_id):
    internal_game_id = resolve_internal_game_id(game_identifier)
    if not internal_game_id:
        return jsonify({'error': 'Game not found in database'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT watch_id
            FROM watchlist
            WHERE user_id = %s AND game_id = %s
            LIMIT 1
            """,
            (user_id, internal_game_id),
        )
        row = cursor.fetchone()
        cursor.close()
        return jsonify({'is_watchlisted': bool(row)}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/games/<game_identifier>/watchlist', methods=['POST'])
def add_game_to_watchlist(game_identifier):
    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')

    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400

    if not get_user_by_id(user_id):
        return jsonify({'error': 'User not found'}), 404

    internal_game_id = resolve_internal_game_id(game_identifier)
    if not internal_game_id:
        return jsonify({'error': 'Game not found in database'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            INSERT INTO watchlist (user_id, game_id, created_at)
            VALUES (%s, %s, NOW())
            ON DUPLICATE KEY UPDATE created_at = created_at
            """,
            (user_id, internal_game_id),
        )
        connection.commit()
        cursor.close()
        return jsonify({'message': 'Game added to watchlist'}), 201
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/games/<game_identifier>/watchlist/<int:user_id>', methods=['DELETE'])
def remove_game_from_watchlist(game_identifier, user_id):
    internal_game_id = resolve_internal_game_id(game_identifier, create_from_live=False)
    if not internal_game_id:
        return jsonify({'error': 'Game not found in database'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM watchlist WHERE user_id = %s AND game_id = %s",
            (user_id, internal_game_id),
        )
        connection.commit()
        deleted = cursor.rowcount
        cursor.close()
        if deleted == 0:
            return jsonify({'error': 'Watchlisted game not found'}), 404
        return jsonify({'message': 'Game removed from watchlist'}), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


@app.route('/api/users/<int:user_id>/alerts', methods=['GET'])
def get_user_alerts(user_id):
    if not get_user_by_id(user_id):
        return jsonify({'error': 'User not found'}), 404

    rows, error = _get_user_game_collection(user_id, 'alerts')
    if error:
        return jsonify({'error': error}), 500
    return jsonify(_make_json_safe(rows)), 200


@app.route('/api/users/<int:user_id>/comment-replies', methods=['GET'])
def get_user_comment_replies(user_id):
    if not get_user_by_id(user_id):
        return jsonify({'error': 'User not found'}), 404

    rows, error = _get_user_comment_replies(user_id)
    if error:
        return jsonify({'error': error}), 500
    return jsonify(_make_json_safe(rows)), 200


@app.route('/api/users/<int:user_id>/myfeed', methods=['GET'])
def get_user_myfeed(user_id):
    if not get_user_by_id(user_id):
        return jsonify({'error': 'User not found'}), 404

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT
                f.favorite_id,
                f.team_id,
                t.name,
                t.city,
                t.abbreviation,
                t.nba_team_id,
                t.logo_url,
                COALESCE(ts.wins, 0) AS wins,
                COALESCE(ts.losses, 0) AS losses,
                f.created_at
            FROM favorites f
            JOIN teams t ON f.team_id = t.team_id
            LEFT JOIN team_standings ts ON t.team_id = ts.team_id
            WHERE f.user_id = %s
            ORDER BY f.created_at DESC;
            """,
            (user_id,),
        )
        favorites = cursor.fetchall() or []
        cursor.close()
    except Error as e:
        connection.close()
        return jsonify({'error': str(e)}), 500
    finally:
        try:
            connection.close()
        except Exception:
            pass

    watchlist_rows, watchlist_error = _get_user_game_collection(user_id, 'watchlist')
    if watchlist_error:
        return jsonify({'error': watchlist_error}), 500

    alert_rows, alert_error = _get_user_game_collection(user_id, 'alerts')
    if alert_error:
        return jsonify({'error': alert_error}), 500

    reply_rows, reply_error = _get_user_comment_replies(user_id)
    if reply_error:
        return jsonify({'error': reply_error}), 500

    return jsonify(_make_json_safe({
        'favorites': favorites,
        'watchlist': watchlist_rows,
        'alerts': alert_rows,
        'comment_replies': reply_rows,
    })), 200


# ================= HEALTH CHECK =================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'API is running'})


# ================= START SERVER =================

# ================= SERVE HTML FILES =================


@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    return send_from_directory(".", filename)

if __name__ == '__main__':

    print("Starting Flask API server on http://localhost:8000")

    print("\nBasketball Endpoints:")
    print("GET /api/teams")
    print("GET /api/teams/{id}")
    print("GET /api/teams/{id}/players")

    print("\nLive NBA:")
    print("GET /api/games/live")
    print("GET /api/nba/teams/{id}/roster")

    print("\nQOTD:")
    print("GET /api/qotd/<date>")
    print("GET /api/qotd/<question_id>/comments")
    print("POST /api/qotd/comment")
    print("POST /api/qotd/vote")

    app.run(debug=True, port=8000)
    
