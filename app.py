"""
Basketball Web App Backend - Flask API
Connects to hoopwatch MySQL database and serves team/player data
"""

import os
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
CORS(app)

# ================= DATABASE CONFIG =================

db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'AmoDodoMyBaby797$',  # Change if needed
    'database': 'hoopwatch'
}

def get_db_connection():
    """Create and return a MySQL database connection"""
    try:
        connection = mysql.connector.connect(**db_config)
        return connection
    except Error as e:
        print(f"Database connection error: {e}")
        return None


# ================= STATIC ROUTES =================

@app.route('/database/Logos/<path:filename>')
def team_logos(filename):
    return send_from_directory(os.path.join(app.root_path, 'database', 'Logos'), filename)

@app.route('/assets/<path:filename>')
def assets(filename):
    return send_from_directory(app.root_path, filename)


# ================= BASKETBALL API =================

@app.route('/api/teams', methods=['GET'])
def get_teams():
    sort_by = request.args.get('sort', 'name')

    sort_options = {
        'name': 't.name',
        'conference': 't.conference, t.name',
        'wins': 'COALESCE(ts.wins, 0) DESC, t.name',
        'losses': 'COALESCE(ts.losses, 0) DESC, t.name'
    }
    order_clause = sort_options.get(sort_by, 't.name')

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
        cursor = connection.cursor(dictionary=True)
        query = f"""
            SELECT 
                t.team_id as id,
                t.name,
                t.city,
                t.conference,
                COALESCE(ts.wins, 0) as wins,
                COALESCE(ts.losses, 0) as losses
            FROM teams t
            LEFT JOIN team_standings ts ON t.team_id = ts.team_id
            ORDER BY {order_clause}
        """
        cursor.execute(query)
        teams = cursor.fetchall()
        cursor.close()
        return jsonify(teams), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


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


# ================= QOTD API =================

# 🔹 Get question by date
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
@app.route('/api/qotd/<int:question_id>/comments', methods=['GET'])
def get_qotd_comments(question_id):

    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500

    try:
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

        return jsonify(comments), 200
    except Error as e:
        return jsonify({'error': str(e)}), 500
    finally:
        connection.close()


# 🔹 Post comment or reply
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


# ================= HEALTH CHECK =================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'API is running'}), 200


# ================= START SERVER =================

if __name__ == '__main__':
    print("Starting Flask API server on http://localhost:8000")
    print("Basketball Endpoints:")
    print("  GET /api/teams")
    print("  GET /api/teams/{id}")
    print("  GET /api/teams/{id}/players")
    print("QOTD Endpoints:")
    print("  GET /api/qotd/<date>")
    print("  GET /api/qotd/<question_id>/comments")
    print("  POST /api/qotd/comment")

    app.run(debug=True, port=8000)