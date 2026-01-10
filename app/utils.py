from typing import Any, Optional, Union
from flask import jsonify
from config import SAVES_DIR, TERRAINS_DIR, TRIBUTES_DIR

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
