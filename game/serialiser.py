import json
import os
import uuid
from .models import Tribute, Terrain
from typing import Optional, Union, Any 

# Directory configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVES_DIR = os.path.join(BASE_DIR, 'saves')
ROSTERS_DIR = os.path.join(BASE_DIR, 'rosters')
TERRAINS_DIR = os.path.join(BASE_DIR, 'terrains')

# Ensure directories exist
os.makedirs(SAVES_DIR, exist_ok=True)
os.makedirs(ROSTERS_DIR, exist_ok=True)
os.makedirs(TERRAINS_DIR, exist_ok=True)

# region Replay Package

def create_replay_package(roster, terrain: Terrain, rng_seed: str) -> str:
    """
    Bundles the Roster, Terrain, and RNG Seed into a single JSON file.
    Returns: The unique game_id (str)
    """
    game_id = str(uuid.uuid4())[:8]  # Short unique ID, e.g., "a1b2c3d4"
    
    package = {
        "meta": {
            "version": "1.0",
            "game_id": game_id,
            "seed": rng_seed
        },
        "terrain": terrain.to_dict(),
        # Convert list of Tribute objects to list of dicts
        "roster": [t.to_dict() for t in roster]
    }
    
    file_path = os.path.join(SAVES_DIR, f"{game_id}.json")
    
    with open(file_path, "w") as f:
        json.dump(package, f, indent=4)
        
    return game_id

def load_replay_package(game_id: str) -> Optional[dict[str,Any]]:
    """
    Loads a specific game configuration by ID.
    Returns: Dictionary containing seed, roster_data, and terrain_data.
    """
    file_path = os.path.join(SAVES_DIR, f"{game_id}.json")
    
    if not os.path.exists(file_path):
        return None
        
    with open(file_path, "r") as f:
        data = json.load(f)
        
    return data

# endRegion
# region Roster

def save_roster_preset(roster, name: str) -> str:
    """
    Saves a list of characters to a reusable JSON file.
    """
    clean_name = "".join(x for x in name if x.isalnum() or x in " _-")
    file_path = os.path.join(ROSTERS_DIR, f"{clean_name}.json")
    
    data = {
        "preset_name": name,
        "tributes": [t.to_dict() for t in roster]
    }
    
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
    
    return file_path

def load_roster_from_json(json_file_path)-> list[dict[str,Any]]:
    """
    Parses a user-uploaded JSON file into a list of Tribute objects.
    """
    with open(json_file_path, "r") as f:
        data = json.load(f)
    
    tributes = []
    # Handle both full save files and simple roster presets
    raw_list = data.get('roster') or data.get('tributes') or []
    
    for t_data in raw_list:
        # Note: We use the from_dict static method we defined in models.py
        tributes.append(Tribute.from_dict(t_data))
        
    return tributes

# endRegion
# region Terrain

def save_terrain_preset(terrain, name):
    """Saves a Terrain configuration to a reusable JSON file."""
    clean_name = "".join(x for x in name if x.isalnum() or x in " _-")
    file_path = os.path.join(TERRAINS_DIR, f"{clean_name}.json")
    
    # We save the dictionary representation
    data = terrain.to_dict()
    
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)
        
    return file_path

def load_terrain_from_json(json_file_path):
    """Parses a JSON file into a Terrain object."""
    with open(json_file_path, "r") as f:
        data = json.load(f)
        
    # data is expected to be the dict from Terrain.to_dict()
    # e.g. {"name": "Desert", "tag_multipliers": {...}}
    return Terrain.from_dict(data)

# endRegion