"""
Basketball Web App Backend - Flask API
Connects to hoopwatch MySQL database and serves team/player data
"""

import os

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
CORS(app)

# MySQL connection configuration
db_config = {
    'host': 'localhost',
    'user': 'root',        # Change if needed
    'password': 'SGabriel79$',        # Change if needed
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

# ============ API ENDPOINTS ============

@app.route('/database/Logos/<path:filename>')
def team_logos(filename):
    """Serve team logo images from database/Logos."""
    return send_from_directory(os.path.join(app.root_path, 'database', 'Logos'), filename)

@app.route('/assets/<path:filename>')
def assets(filename):
    """Serve static assets from the project root."""
    return send_from_directory(app.root_path, filename)

@app.route('/api/teams', methods=['GET'])
def get_teams():
    """
    GET /api/teams?sort=name|conference|wins|losses
    Returns: List of all teams with name, city, conference, wins, losses
    """
    from flask import request
    sort_by = request.args.get('sort', 'name')
    
    # Map sort parameter to SQL column
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
                tl.city,
                t.conference,
                ts.wins,
                ts.losses
            FROM teams t
            LEFT JOIN team_locations tl ON t.team_id = tl.team_id
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
    """
    GET /api/teams/{id}
    Returns: Team name, city, arena, wins, losses
    """
    connection = get_db_connection()
    if not connection:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        cursor = connection.cursor(dictionary=True)
        query = """
            SELECT 
                t.team_id as id,
                t.name,
                tl.city,
                tl.arena_name as arena,
                ts.wins,
                ts.losses
            FROM teams t
            LEFT JOIN team_locations tl ON t.team_id = tl.team_id
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
    """
    GET /api/teams/{id}/players
    Returns: List of players for the team with name, position, jersey, height
    """
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

# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({'status': 'API is running'}), 200

if __name__ == '__main__':
    print("Starting Flask API server on http://localhost:8000")
    print("Available endpoints:")
    print("  GET /api/teams")
    print("  GET /api/teams/{id}")
    print("  GET /api/teams/{id}/players")
    app.run(debug=True, port=8000)
