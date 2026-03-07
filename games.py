from flask import Blueprint, jsonify
from services.nba_service import get_live_games

games_bp = Blueprint("games", __name__)

@games_bp.route("/api/games/live")
def live_games():

    games = get_live_games()

    return jsonify(games)