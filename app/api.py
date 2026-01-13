from os.path import exists, join
from os import listdir
from random import randint, seed
from uuid import uuid4
from json import load, JSONDecodeError
from flask import Blueprint, request
from game.engine import GameEngine
from game.models import Tribute, Terrain
import game.serialiser as serialiser
from .utils import *

api_bp = Blueprint('api', __name__)


def fetch_object_files(type: str, filename: Optional[str]=None):
    # Check directory is valid and exists
    dir = DIR_MAP.get(type)
    if not dir: raise Exception('Directory type is invalid.')
    if not exists(dir):
        if filename: raise Exception('File not found.')
        else: return []

    if filename: # Fetch 1 json file
        pathStr = join(dir, filename)
        try:
            with open(pathStr, 'r') as f:
                data = load(f)
            return data
        except Exception as e: raise e
    
    try: # Fetch all json file in directory
        presets = []
        files = [f for f in listdir(dir) if f.endswith('.json')]
        for f in files:
            pathStr = join(dir, f)
            try:
                with open(pathStr, 'r') as json_file:
                    data = load(json_file)
                    presets.append({
                        "filename": f,
                        "name": data.get('preset_name', f.replace('.json', '')),
                        "count": len(data.get('tributes', []))
                    })
            except JSONDecodeError: continue # Skip broken files 
    except Exception as e: raise e
    return presets

@api_bp.route('/config', methods=['GET'])
def get_game_config():
    """Returns game constants from the Models."""
    return success_response({
        "stats": {
            "min": Tribute.MIN_STAT,
            "max": Tribute.MAX_STAT
        },
        "multipliers": {
            "min": Terrain.MIN_MULT,
            "max": Terrain.MAX_MULT
        }
    }, "Config loaded")

@api_bp.route('/items', methods=['GET'])
def items():
    """Returns list of valid items for tags/autocomplete."""
    # Assuming items.json is in game/data/items.json
    try:
        path = join(DATA_DIR, 'items.json')
        data = serialiser.load_json(path)
        item_names = sorted([i['name'] for i in data]) if data else []
        return success_response(item_names, "Items loaded")
            
    except Exception as e:
        return error_response(f"Could not load items: {e}", 500)


@api_bp.route('/roster/<filename>', methods=["GET", "POST", "PATCH"])
@api_bp.route('/rosters', methods=["GET"])
def rosters(filename: Optional[str]=None):
    if not filename:
        if request.method == "GET": # Fetch all rosters
            try:
                presets = fetch_object_files('tributes')
            except Exception as e:
                return error_response(f"Error listing rosters: {str(e)}", 500)
            return success_response(presets, "Roster presets retrieved")
        elif request.method == "POST": # Create new roster
            return error_response("Route not Implemented.", 501)
        
    elif filename:
        # Check filename is valid
        filename = sanitise_string(filename)
        if not filename:
            return error_response("Invalid filename provided.", 400)
        
        if request.method == "GET": # Fetch 1 roster
            try:
                data = fetch_object_files('rosters', filename)
            except Exception as e:
                return error_response(f"Error loading roster: {str(e)}", 500)
            return success_response(data, "Roster loaded")
        elif request.method == "PATCH": # Update existing roster
            return error_response("Route not Implemented.", 501)
    
    return error_response("Route not allowed.", 405)


@api_bp.route('/terrain/<filename>', methods=["GET", "POST", "PATCH"])
@api_bp.route('/terrains', methods=["GET"])
def terrains(filename: Optional[str]=None):
    if not filename:
        if request.method == "GET": # Fetch all terrains
            try:
                presets = fetch_object_files('terrains')
            except Exception as e:
                return error_response(f"Error listing terrains: {str(e)}", 500)
            return success_response(presets, "Terrain presets retrieved")
        elif request.method == "POST": # Create new terrain
            return error_response("Route not Implemented.", 501)
    
    elif filename:
        # Check filename is valid
        filename = sanitise_string(filename)
        if not filename:
            return error_response("Invalid filename provided.", 400)
        
        if request.method == "GET": # Fetch 1 terrain
            try:
                data = fetch_object_files('terrains', filename)
            except Exception as e:
                return error_response(f"Error loading terrain: {str(e)}", 500)
            return success_response(data, "Terrain loaded")
        elif request.method == "PATCH": # Update existing roster
            return error_response("Route not Implemented.", 501)
    
    return error_response("Route not allowed.", 405)

@api_bp.route('/simulate/<game_id>', methods=['POST'])
def run_simulation(game_id):
    if game_id: # Simulate Specific Game
        # Check input
        game_id = sanitise_string(game_id)
        if not game_id:
            return error_response("Invalid game ID provided.", 400)
        
        # Load
        raw_data = serialiser.load_simulation_result(game_id)
        if not raw_data:
            return error_response("Game not found.", 404)
            
        # Sanitize
        safe_data = sanitise_game_data(raw_data)
                        
        return success_response(safe_data, "Game data retrieved.")

    if not game_id: # Simulate Game
        data = request.json
        if not data:
            return error_response("Invalid JSON data provided.", 400)
        
        try:
            # 1. Setup Data
            roster = [Tribute.from_dict(t) for t in data.get('tributes', [])]
            terrain_data = data.get('terrain', {})
            
            # 2. Server-Side Seed
            game_seed = randint(1, 999999999)
            
            # Set seed for any random operations during reconstruction
            seed(game_seed)
            terrain = Terrain.from_dict(terrain_data)
            
            # Reset seed so combat is consistent regardless of terrain generation steps
            seed(game_seed)
            
            # 3. Run Engine
            engine = GameEngine(roster, terrain, rng_seed=game_seed)
            result = engine.simulate()
            
            # 4. Package Result
            game_id = uuid4().hex[:8]
            full_package = {
                "meta": result['meta'],
                "terrain": terrain.to_dict(),
                "tributes": [t.to_dict() for t in roster],
                "timeline": result['timeline'],
                "stats": {
                    "total_days": result.get('total_days', 0),
                    "winner": result['meta']['winner']
                }
            }
            full_package['meta']['game_id'] = game_id
            full_package['meta']['seed'] = game_seed
            
            # 6. Save Result
            if serialiser.save_simulation_result(game_id, full_package):
                return success_response({"game_id": game_id}, "Simulation completed successfully.")
            else:
                return error_response("Failed to save simulation results.", 500)

        except Exception as e:
            return error_response(str(e), 500)
        
    return error_response("Route not allowed.", 405)