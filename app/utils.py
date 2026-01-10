from copy import deepcopy
from typing import Any, Optional, Union
from flask import jsonify
from config import SAVES_DIR, TERRAINS_DIR, TRIBUTES_DIR

DIR_MAP = {
    "tributes" : TRIBUTES_DIR,
    "terrains" : TERRAINS_DIR,
    "saves"    : SAVES_DIR
}

# region JSON Responses

def success_response(data=None, message="Success", status=200):
    """
    Standardized JSON success response.
    Format: {"status": "success", "message": "...", "data": ...}
    """
    response = {
        "status": "success",
        "message": message,
        "data": data
    }
    return jsonify(response), status

def error_response(message="An error occurred", status=400, details=None):
    """
    Standardized JSON error response.
    Format: {"status": "error", "message": "...", "details": ...}
    """
    response = {
        "status": "error",
        "message": message
    }
    if details:
        response["details"] = details
    return jsonify(response), status

# endRegion
# region sanitisers

def sanitise_game_data(game_data: dict[str, Any]):
    """
    Removes sensitive data (Seeds, HP values) before sending to frontend.
    """
    clean_data = deepcopy(game_data)
    
    # 1. Hide Seed
    if 'meta' in clean_data and 'seed' in clean_data['meta']:
        del clean_data['meta']['seed']
    
    # 2. Hide Numeric HP
    for day in clean_data.get('timeline', []):
        if 'alliance_snapshot' in day:
            for alliance in day['alliance_snapshot']:
                for member in alliance['members']:
                    # Remove exact health
                    if 'health' in member:
                        del member['health']
                    
    return clean_data

def sanitise_string(s: str) -> str:
    return s

# endRegion