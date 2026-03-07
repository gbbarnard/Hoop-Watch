"""
Basketball Web App Backend - Flask API
Connects to hoopwatch MySQL database and serves team/player data
"""

import os
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
    'host': 'localhost',
    'user': 'root',
    'password': 'Junopull123$',  # consider using environment variable
    'database': 'hoopwatch'
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

    connection = get_db_connection()
    if not connection:
        return

    cursor = connection.cursor()

    try:

        game_id = game["gameId"]
        home_team = game["homeTeam"]["teamId"]
        away_team = game["awayTeam"]["teamId"]

        # Ensure game exists
        cursor.execute("""
        INSERT INTO games (game_id, home_team_id, away_team_id)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE home_team_id = home_team_id
        """, (game_id, home_team, away_team))

        clock = game.get("gameClock") or "0:00"

        # Cache scores
        cursor.execute("""
        INSERT INTO game_cache
        (game_id, home_score, away_score, period, clock, fetched_at)
        VALUES (%s,%s,%s,%s,%s,NOW())
        ON DUPLICATE KEY UPDATE
            home_score=%s,
            away_score=%s,
            period=%s,
            clock=%s,
            fetched_at=NOW()
        """, (
            game_id,
            game["homeTeam"]["score"],
            game["awayTeam"]["score"],
            game["period"],
            clock,
            game["homeTeam"]["score"],
            game["awayTeam"]["score"],
            game["period"],
            clock
        ))

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

def sync_teams():

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
    return send_from_directory(os.path.join(app.root_path, 'database', 'Logos'), filename)


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

    # fetch teams from DB
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT team_id, name, city, abbreviation FROM teams")
    db_teams = cursor.fetchall()

    cursor.close()
    connection.close()

    # fetch NBA standings
    standings = leaguestandings.LeagueStandings().get_dict()

    headers = standings["resultSets"][0]["headers"]
    rows = standings["resultSets"][0]["rowSet"]

    # find correct column indexes
    team_id_idx = headers.index("TeamID")
    wins_idx = headers.index("WINS")
    losses_idx = headers.index("LOSSES")

    standings_map = {}

    for row in rows:

        team_id = row[team_id_idx]
        wins = int(row[wins_idx])
        losses = int(row[losses_idx])

        standings_map[team_id] = {
            "wins": wins,
            "losses": losses
        }

    teams = []

    for team in db_teams:

        record = standings_map.get(team["team_id"], {"wins":0,"losses":0})

        teams.append({
            "id": team["team_id"],
            "name": team["name"],
            "city": team["city"],
            "abbreviation": team["abbreviation"],
            "wins": record["wins"],
            "losses": record["losses"]
        })

    return jsonify(teams)

@app.route('/api/teams/<int:team_id>', methods=['GET'])
def get_team_details(team_id):

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:

        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                t.team_id as id,
                t.name,
                t.city,
                t.arena_name as arena,
                COALESCE(ts.wins, 0) as wins,
                COALESCE(ts.losses, 0) as losses
            FROM teams t
            LEFT JOIN team_standings ts ON t.team_id = ts.team_id
            WHERE t.team_id = %s
        """

        cursor.execute(query, (team_id,))
        team = cursor.fetchone()

        cursor.close()

        if not team:
            return jsonify({'error': 'Team not found'}), 404

        return jsonify(team), 200

    except Error as e:

        return jsonify({'error': str(e)}), 500

    finally:
        connection.close()


@app.route('/api/teams/<int:team_id>/players', methods=['GET'])
def get_team_players(team_id):

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:

        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT 
                player_id as id,
                CONCAT(first_name, ' ', last_name) as name,
                position,
                jersey_number as jersey,
                CONCAT(height_in, '"') as height
            FROM players
            WHERE team_id = %s AND is_active = TRUE
            ORDER BY jersey_number
        """

        cursor.execute(query, (team_id,))
        players = cursor.fetchall()

        cursor.close()

        return jsonify(players), 200

    except Error as e:

        return jsonify({'error': str(e)}), 500

    finally:
        connection.close()


# ================= LIVE NBA GAMES =================

@app.route('/api/games/live', methods=['GET'])
def get_live_games():

    games = fetch_live_games()

    for game in games:
        cache_game(game)

    return jsonify(games)


# ================= NBA ROSTER API =================

@app.route('/api/nba/teams/<int:team_id>/roster')
def get_roster(team_id):

    roster = fetch_team_roster(team_id)

    return jsonify(roster)


# ================= QOTD API =================

@app.route('/api/qotd/<date>', methods=['GET'])
def get_qotd_by_date(date):

    connection = get_db_connection()
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
    cursor = connection.cursor(dictionary=True)

    cursor.execute("""
        SELECT c.comment_id,
               c.question_id,
               c.user_id,
               c.parent_comment_id,
               c.comment_text,
               c.created_at,
               u.username as user_name
        FROM qotd_comments c
        JOIN users u ON c.user_id = u.user_id
        WHERE c.question_id = %s
        ORDER BY c.created_at ASC
    """, (question_id,))

    comments = cursor.fetchall()

    cursor.close()
    connection.close()

    return jsonify(comments)


@app.route('/api/qotd/comment', methods=['POST'])
def post_qotd_comment():

    data = request.json

    connection = get_db_connection()
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
    connection.close()

    return jsonify({'message': 'Comment added'}), 201


# ================= HEALTH CHECK =================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'API is running'})


# ================= START SERVER =================

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

    app.run(debug=True, port=8000)