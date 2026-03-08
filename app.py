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
    try:
        from nba_api.stats.static import teams
        from nba_api.live.nba.endpoints import scoreboard
        
        # Get team info from static data
        nba_teams = teams.get_teams()
        team = next((t for t in nba_teams if t['id'] == team_id), None)
        
        if not team:
            return jsonify({'error': 'Team not found'}), 404
        
        # Get current W-L record from today's games
        games = scoreboard.ScoreBoard()
        games_data = games.get_dict()["scoreboard"]["games"]
        
        wins = 0
        losses = 0
        
        # Find this team in any of today's games to get current record
        for game in games_data:
            home = game.get('homeTeam', {})
            away = game.get('awayTeam', {})
            
            if home.get('teamId') == team_id:
                wins = home.get('wins', 0)
                losses = home.get('losses', 0)
                break
            elif away.get('teamId') == team_id:
                wins = away.get('wins', 0)
                losses = away.get('losses', 0)
                break
        
        response = {
            'id': team_id,
            'full_name': team['full_name'],
            'abbreviation': team['abbreviation'],
            'city': team['city'],
            'name': team['nickname'],
            'wins': wins,
            'losses': losses
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        print(f"Error fetching team details: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/teams/<int:team_id>/players', methods=['GET'])
def get_team_players(team_id):
    try:
        from nba_api.stats.endpoints import commonteamroster
        
        # Get team roster
        roster = commonteamroster.CommonTeamRoster(team_id=team_id, season='2025-26')
        roster_data = roster.get_dict()['resultSets'][0]['rowSet']
        
        players = []
        for player in roster_data:
            # Indices: 3=PLAYER, 6=NUM, 7=POSITION, 8=HEIGHT
            jersey_num = player[6] if player[6] else '-'
            players.append({
                'id': player[12] if len(player) > 12 else 0,  # PLAYER_ID
                'name': player[3],  # PLAYER
                'jersey': str(jersey_num),  # NUM  
                'position': player[7] if player[7] else '-',  # POSITION
                'height': player[8] if player[8] else '-'  # HEIGHT (already formatted like "6-4")
            })
        
        # Sort by jersey number
        players.sort(key=lambda x: int(x['jersey']) if x['jersey'].isdigit() else 999)
        
        return jsonify(players), 200
        
    except Exception as e:
        print(f"Error fetching roster: {e}")
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
        
        transformed_game = {
            'game_id': game.get('gameId'),
            'gameId': game.get('gameId'),  # Add camelCase for frontend
            'gameStatus': game.get('gameStatus'),
            'status': 'Live' if game.get('gameStatus') == 2 else ('Final' if game.get('gameStatus') == 3 else 'Upcoming'),
            'game_time': game.get('gameStatusText', 'TBD'),
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


# ================= NBA ROSTER API =================

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
                u.username AS user_name,
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
                u.username
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
            stats = team_data.get('statistics', {})
            return {
                'points': stats.get('points', 0),
                'fgm': stats.get('fieldGoalsMade', 0),
                'fga': stats.get('fieldGoalsAttempted', 0),
                'fg_pct': stats.get('fieldGoalsPercentage', 0),
                'fg3m': stats.get('threePointersMade', 0),
                'fg3a': stats.get('threePointersAttempted', 0),
                'fg3_pct': stats.get('threePointersPercentage', 0),
                'ftm': stats.get('freeThrowsMade', 0),
                'fta': stats.get('freeThrowsAttempted', 0),
                'ft_pct': stats.get('freeThrowsPercentage', 0),
                'rebounds': stats.get('reboundsTotal', 0),
                'offReb': stats.get('reboundsOffensive', 0),
                'defReb': stats.get('reboundsDefensive', 0),
                'assists': stats.get('assists', 0),
                'steals': stats.get('steals', 0),
                'blocks': stats.get('blocks', 0),
                'turnovers': stats.get('turnoversTotal', 0),
                'fouls': stats.get('foulsPersonal', 0),
                'pointsInPaint': stats.get('pointsInThePaint', 0),
                'fastBreakPoints': stats.get('pointsFastBreak', 0),
                'benchPoints': stats.get('benchPoints', 0),
                'biggestLead': stats.get('biggestLead', 0)
            }
        
        result = {
            'gameId': game.get('gameId', ''),
            'gameStatus': game.get('gameStatus', 1),
            'gameStatusText': game.get('gameStatusText', ''),
            'period': game.get('period', 0),
            'gameClock': game.get('gameClock', ''),
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