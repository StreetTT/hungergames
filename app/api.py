from flask import Blueprint, request
from utils import *
api_bp = Blueprint('api', __name__)

@api_bp.route('/rosters/<filename>', method=["GET", "POST", "PATCH"])
def rosters(filename: str):
    return error_response("Route not allowed.", 405)

@api_bp.route('/terrains/<filename>', method=["GET", "POST", "PATCH"])
def terrains(filename: str):
    return error_response("Route not allowed.", 405)

@api_bp.route('/simulate/<game_id>', methods=['POST'])
def run_simulation(game_id):
    return error_response("Route not allowed.", 405)