"""
Basketball Web App Backend - Flask API
Connects to hoopwatch MySQL database and serves team/player data
"""

import os
import datetime
import re
from dotenv import load_dotenv

# Load environment variables from a local .env file (if present)
load_dotenv()

from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error

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
    "password": os.environ.get("MYSQL_PASSWORD", "AmoDodoMyBaby797$"),  # set in env if needed
    # Support either MYSQL_DATABASE or MYSQL_DB
    "database": os.environ.get("MYSQL_DATABASE") or os.environ.get("MYSQL_DB") or "hoopwatch",
}


def get_db_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Database connection error: {e}")
        return None


# ================= NBA API FUNCTIONS =================

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


    from nba_api.stats.static import teams

    nba_teams = teams.get_teams()

    connection = get_db_connection()
    cursor = connection.cursor()

    for team in nba_teams:

        cursor.execute("""
        INSERT INTO teams (team_id, name, city, abbreviation)
        VALUES (%s,%s,%s,%s)
        """, (
            team["id"],          # NBA TEAM ID
            team["full_name"],
            team["city"],
            team["abbreviation"]
        ))


def _get_table_columns(connection, table_name):
    cur = connection.cursor()
    cur.execute(f"SHOW COLUMNS FROM {table_name}")
    cols = cur.fetchall()
    cur.close()
    # SHOW COLUMNS columns: Field, Type, Null, Key, Default, Extra
    return {c[0]: {"type": c[1], "null": c[2], "key": c[3], "default": c[4], "extra": c[5]} for c in cols}


def sync_teams():
    """Insert/refresh NBA teams into the local MySQL teams table.

    IMPORTANT: In our schema, teams.team_id is an internal AUTO_INCREMENT id.
    The NBA id should be stored in teams.nba_team_id (if that column exists).
    If the schema instead uses team_id as the NBA id (no auto_increment), we support that too.
    """
    nba_teams = teams.get_teams()

    connection = get_db_connection()
    if not connection:
        return

    cols = _get_table_columns(connection, "teams")
    has_auto_team_id = "team_id" in cols and "auto_increment" in str(cols["team_id"]["extra"]).lower()

    cursor = connection.cursor()

    for team in nba_teams:
        nba_id = int(team["id"])
        full_name = team.get("full_name") or team.get("name") or ""
        abbr = team.get("abbreviation") or ""
        city = team.get("city") or ""
        conf = None
        logo = f"https://cdn.nba.com/logos/nba/{nba_id}/primary/L/logo.svg"

        fields = []
        values = []
        updates = []

        def add(field, value):
            if field in cols:
                fields.append(field)
                values.append(value)
                updates.append(f"{field}=VALUES({field})")

        # If team_id is NOT auto_increment, it's probably meant to be the NBA id
        if "team_id" in cols and not has_auto_team_id:
            add("team_id", nba_id)

        # Preferred: store NBA id in nba_team_id
        add("nba_team_id", str(nba_id))

        # Common columns
        add("name", full_name)
        add("abbreviation", abbr)
        add("city", city)
        add("logo_url", logo)

        # conference is often NOT NULL in schema, so ensure a value if column exists
        if "conference" in cols:
            add("conference", conf or "East")

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


def sync_standings():


    standings = leaguestandings.LeagueStandings()
    data = standings.get_dict()

    rows = data["resultSets"][0]["rowSet"]

    connection = get_db_connection()
    cursor = connection.cursor()

    for team in rows:

        team_id = team[2]

        wins = int(team[8]) if str(team[8]).isdigit() else 0
        losses = int(team[9]) if str(team[9]).isdigit() else 0

        # check team exists first
        cursor.execute("SELECT team_id FROM teams WHERE team_id=%s", (team_id,))
        exists = cursor.fetchone()

        if not exists:
            continue

        cursor.execute("""
        INSERT INTO team_standings (team_id, wins, losses)
        VALUES (%s,%s,%s)
        ON DUPLICATE KEY UPDATE
            wins=%s,
            losses=%s
        """, (team_id, wins, losses, wins, losses))

    connection.commit()
    cursor.close()
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

    # Standings map keyed by NBA team id
    standings_map = {}

    if not standings_map:
        try:
            standings = leaguestandings.LeagueStandings().get_dict()
            headers = standings["resultSets"][0]["headers"]
            rows = standings["resultSets"][0]["rowSet"]

            def hidx(*candidates):
                for c in candidates:
                    if c in headers:
                        return headers.index(c)
                return None

            team_id_idx = hidx("TeamID", "TEAM_ID")
            wins_idx = hidx("WINS", "W")
            losses_idx = hidx("LOSSES", "L")
            conf_idx = hidx("Conference", "CONFERENCE")

            for row in rows:
                tid = int(row[team_id_idx]) if team_id_idx is not None else None
                if tid is None:
                    continue
                conf = row[conf_idx] if conf_idx is not None else None
                conf_norm = "East" if str(conf).lower().startswith("e") else ("West" if conf else None)
                standings_map[tid] = {
                    "wins": int(row[wins_idx]) if wins_idx is not None else 0,
                    "losses": int(row[losses_idx]) if losses_idx is not None else 0,
                    "conference": conf_norm,
                }
        except Exception as e:
            print("nba_api standings fetch failed:", e)

    teams_out = []
    for t in db_teams:
        internal_id = int(t["team_id"])
        nba_id = nba_id_for_row(t)

        record = standings_map.get(nba_id, {"wins": 0, "losses": 0, "conference": None})
        logo = t.get("logo_url") or (f"https://cdn.nba.com/logos/nba/{nba_id}/primary/L/logo.svg" if nba_id else "")

        teams_out.append({
            "id": internal_id,
            "nba_team_id": nba_id,
            "name": t.get("name"),
            "city": t.get("city"),
            "abbreviation": t.get("abbreviation"),
            "wins": record["wins"],
            "losses": record["losses"],
            "conference": t.get("conference") or record["conference"],
            "logo_url": logo,
        })

    return jsonify(teams_out)


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
        if "arena_name" in teams_cols:
            select_parts.append("t.arena_name AS arena_name")

        join_sql = ""
        if has_team_locations:
            join_sql = " LEFT JOIN team_locations tl ON tl.team_id = t.team_id "
            if "city" not in teams_cols:
                select_parts.append("tl.city AS city")
            if "arena_name" not in teams_cols:
                select_parts.append("tl.arena_name AS arena_name")

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

        # standings
        wins = 0
        losses = 0
        conf_from_standings = None
    

        if wins == 0 and losses == 0:
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
    """Return a team's roster with headshot URLs.

    `team_id` is the INTERNAL DB id. We map it to the NBA team id using teams.nba_team_id or abbreviation.
    Primary source: data.nba.net roster (usually most reliable).
    Fallback: nba_api CommonTeamRoster (requires NBA team id).
    """
    try:
        import requests
        today = datetime.date.today()
        season_start = today.year if today.month >= 10 else today.year - 1
        season_end = season_start + 1

        # Map team abbreviations to data.nba.net team slugs
        abbr_to_slug = {
            "ATL": "hawks", "BOS": "celtics", "BKN": "nets", "CHA": "hornets", "CHI": "bulls",
            "CLE": "cavaliers", "DAL": "mavericks", "DEN": "nuggets", "DET": "pistons",
            "GSW": "warriors", "HOU": "rockets", "IND": "pacers", "LAC": "clippers", "LAL": "lakers",
            "MEM": "grizzlies", "MIA": "heat", "MIL": "bucks", "MIN": "timberwolves", "NOP": "pelicans",
            "NYK": "knicks", "OKC": "thunder", "ORL": "magic", "PHI": "sixers", "PHX": "suns",
            "POR": "blazers", "SAC": "kings", "SAS": "spurs", "TOR": "raptors", "UTA": "jazz", "WAS": "wizards",
        }

        # Get abbreviation + nba_team_id from DB if possible
        abbr = None
        nba_id = None
        try:
            conn = get_db_connection()
            if conn:
                cur = conn.cursor()
                # try both schema styles
                cur.execute("SHOW COLUMNS FROM teams")
                cols = [c[0] for c in cur.fetchall()]
                if "nba_team_id" in cols:
                    cur.execute("SELECT abbreviation, nba_team_id FROM teams WHERE team_id=%s", (team_id,))
                    row = cur.fetchone()
                    if not row:
                        # If the user passed an NBA team id, resolve it to our row.
                        cur.execute("SELECT abbreviation, nba_team_id FROM teams WHERE nba_team_id=%s", (team_id,))
                        row = cur.fetchone()
                    if row:
                        abbr = row[0]
                        raw = row[1]
                        if raw is not None and str(raw).strip().isdigit():
                            nba_id = int(str(raw).strip())
                else:
                    cur.execute("SELECT abbreviation FROM teams WHERE team_id=%s", (team_id,))
                    row = cur.fetchone()
                    if row:
                        abbr = row[0]
                cur.close()
                conn.close()
        except Exception:
            pass

        # If we still don't have nba_id, map by abbreviation using nba_api static teams
        if nba_id is None:
            nba_list = teams.get_teams()
            abbr_map = {str(t.get("abbreviation", "")).upper(): int(t["id"]) for t in nba_list if t.get("abbreviation")}
            if abbr:
                nba_id = abbr_map.get(str(abbr).upper())

        if not abbr:
            # last resort: try to map internal id to NBA id by looking at team details route
            return jsonify({"error": "Team abbreviation not found"}), 404

        slug = abbr_to_slug.get(str(abbr).upper())

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

@app.route('/api/games/live', methods=['GET'])
def get_live_games():
    games = fetch_live_games()
    
    # Transform the data for frontend
    transformed_games = []
    for game in games:
        cache_game(game)
        
        home = game.get('homeTeam', {})
        away = game.get('awayTeam', {})

        home_team_id = home.get('teamId')
        arena_name = get_arena_by_nba_team_id(home_team_id)
        
        transformed_game = {
            'game_id': game.get('gameId'),
            'gameId': game.get('gameId'),  # Add camelCase for frontend
            'gameStatus': game.get('gameStatus'),
            'status': 'Live' if game.get('gameStatus') == 2 else ('Final' if game.get('gameStatus') == 3 else 'Upcoming'),
            'game_time': game.get('gameStatusText', 'TBD'),
            'arena_name': arena_name or 'Arena TBD',
            'home_team': {
                'id': home.get('teamId'),
                'full_name': f"{home.get('teamCity', '')} {home.get('teamName', '')}".strip(),
                'abbreviation': home.get('teamTricode', ''),
                'wins': home.get('wins', 0),
                'losses': home.get('losses', 0)
            },
            'away_team': {
                'id': away.get('teamId'),
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
@app.route('/api/games/<game_id>', methods=['GET'])
def get_game_detail(game_id):
    """Get detailed game information including box score"""
    from nba_api.live.nba.endpoints import boxscore
    
    try:
        box = boxscore.BoxScore(game_id=game_id)
        data = box.get_dict()
        
        game = data.get('game', {})
        
        # Extract basic game info
        home_team = game.get('homeTeam', {})
        away_team = game.get('awayTeam', {})

                # Look up arena using the HOME team's NBA team id
        arena_name = "Arena TBD"
        try:
            home_nba_team_id = str(home_team.get('teamId', ''))
            connection = get_db_connection()
            if connection:
                cursor = connection.cursor(dictionary=True)
                cursor.execute("""
                    SELECT arena_name
                    FROM teams
                    WHERE nba_team_id = %s
                """, (home_nba_team_id,))
                row = cursor.fetchone()
                if row and row.get("arena_name"):
                    arena_name = row["arena_name"]
                cursor.close()
                connection.close()
        except Exception as e:
            print("Arena lookup failed:", e)
        
        # Helper function to convert ISO duration to minutes
        def parse_minutes(iso_duration):
            if not iso_duration or iso_duration == 'PT00M00.00S':
                return '0:00'
            # Parse PT06M47.00S format
            import re
            match = re.match(r'PT(\d+)M([\d.]+)S', iso_duration)
            if match:
                mins = int(match.group(1))
                secs = int(float(match.group(2)))
                return f'{mins}:{secs:02d}'
            return '0:00'
        
        # Process player stats
        def process_players(team_data):
            players = []
            for player in team_data.get('players', []):
                if player.get('played') == '1':  # Only include players who played
                    stats = player.get('statistics', {})
                    players.append({
                        'name': player.get('name', ''),
                        'nameI': player.get('nameI', ''),
                        'position': player.get('position', ''),
                        'jerseyNum': player.get('jerseyNum', ''),
                        'starter': player.get('starter', '') == '1',
                        'minutes': parse_minutes(stats.get('minutes', 'PT00M00.00S')),
                        'points': stats.get('points', 0),
                        'rebounds': stats.get('reboundsTotal', 0),
                        'assists': stats.get('assists', 0),
                        'steals': stats.get('steals', 0),
                        'blocks': stats.get('blocks', 0),
                        'turnovers': stats.get('turnovers', 0),
                        'fouls': stats.get('foulsPersonal', 0),
                        'fgm': stats.get('fieldGoalsMade', 0),
                        'fga': stats.get('fieldGoalsAttempted', 0),
                        'fg_pct': stats.get('fieldGoalsPercentage', 0),
                        'fg3m': stats.get('threePointersMade', 0),
                        'fg3a': stats.get('threePointersAttempted', 0),
                        'fg3_pct': stats.get('threePointersPercentage', 0),
                        'ftm': stats.get('freeThrowsMade', 0),
                        'fta': stats.get('freeThrowsAttempted', 0),
                        'ft_pct': stats.get('freeThrowsPercentage', 0),
                        'plusMinus': stats.get('plusMinusPoints', 0)
                    })
            return players
        
        # Process team stats
        def process_team_stats(team_data):
            stats = team_data.get('statistics', {}) or {}
            players = team_data.get('players', []) or []

            # Start with team-level stats if present
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
                'biggestLead': int(stats.get('biggestLead') or 0)
            }

            # If core stats are zero/incomplete, rebuild them from player stats
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

            return team_stats

        result = {
            'gameId': game.get('gameId', ''),
            'gameStatus': game.get('gameStatus', 1),
            'gameStatusText': game.get('gameStatusText', ''),
            'period': game.get('period', 0),
            'gameClock': game.get('gameClock', ''),
            'arena_name': arena_name,
            'homeTeam': {
                'teamId': home_team.get('teamId', 0),
                'teamName': home_team.get('teamName', ''),
                'teamCity': home_team.get('teamCity', ''),
                'teamTricode': home_team.get('teamTricode', ''),
                'score': home_team.get('score', 0),
                'periods': home_team.get('periods', []),
                'players': process_players(home_team),
                'statistics': process_team_stats(home_team)
            },
            'awayTeam': {
                'teamId': away_team.get('teamId', 0),
                'teamName': away_team.get('teamName', ''),
                'teamCity': away_team.get('teamCity', ''),
                'teamTricode': away_team.get('teamTricode', ''),
                'score': away_team.get('score', 0),
                'periods': away_team.get('periods', []),
                'players': process_players(away_team),
                'statistics': process_team_stats(away_team)
            }
        }

        return jsonify(result)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    

@app.route('/api/nba/teams/<int:team_id>/roster')
def get_roster(team_id):

    roster = fetch_team_roster(team_id)

    return jsonify(roster)


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


