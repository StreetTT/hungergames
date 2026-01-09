import json
import os
import uuid
from .models import Tribute, Terrain
from typing import Optional, Union, Any 

# Directory configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVES_DIR = os.path.join(BASE_DIR, 'saves')
TRIBUTES_DIR = os.path.join(BASE_DIR, 'tributes')
TERRAINS_DIR = os.path.join(BASE_DIR, 'terrains')

# Ensure directories exist
os.makedirs(SAVES_DIR, exist_ok=True)
os.makedirs(TRIBUTES_DIR, exist_ok=True)
os.makedirs(TERRAINS_DIR, exist_ok=True)

def save_json(filepath: str, data: dict):
    """Generic JSON saver to reduce open() repetition."""
    with open(filepath, "w") as f:
        json.dump(data, f, indent=4)

def load_json(filepath: str):
    """Generic JSON loader."""
    if not os.path.exists(filepath): return None
    with open(filepath, "r") as f:
        return json.load(f)

# region Replay Package

def create_replay_package(tributes: list[Tribute], terrain: Terrain, rng_seed: str) -> str:
    """
    Bundles the Tributes, Terrain, and RNG Seed into a single JSON file.
    Returns: The unique game_id (str)
    """
    game_id = str(uuid.uuid4())[:8]  # Short unique ID, e.g., "a1b2c3d4"
    
    package = {
        "meta": { "version": "1.1.1", "game_id": game_id, "seed": rng_seed },
        "terrain": terrain.to_dict(),
        "tributes": [t.to_dict() for t in tributes]
    }

    save_json(os.path.join(SAVES_DIR, f"{game_id}.json"), package)
    return game_id

def load_replay_package(game_id: str) -> Optional[dict[str,Any]]:
    """
    Loads a specific game configuration by ID.
    Returns: Dictionary containing seed, tribute_data, and terrain_data.
    """
    return load_json(os.path.join(SAVES_DIR, f"{game_id}.json"))

# endRegion
# region Tributes

def save_tributes_preset(tributes: list[Tribute], name: str) -> str:
    """
    Saves a list of characters to a reusable JSON file.
    """
    clean_name = "".join(x for x in name if x.isalnum() or x in " _-")
    file_path = os.path.join(TRIBUTES_DIR, f"{clean_name}.json")
    
    data = {
        "preset_name": name,
        "tributes": [t.to_dict() for t in tributes]
    }

    save_json(file_path, data)    
    return file_path

def load_tributes_from_json(json_file_path: str)-> Optional[list[Tribute]]:
    """
    Parses a user-uploaded JSON file into a list of Tribute objects.
    """
    data = load_json(json_file_path)
    if data is None:
        return None
    
    tributes = []
    # Handle both full save files and simple tributes presets
    raw_list = data.get('tributes') or []
    
    for t_data in raw_list:
        # Note: We use the from_dict static method we defined in models.py
        tributes.append(Tribute.from_dict(t_data))
        
    return tributes

# endRegion
# region Terrain

def save_terrain_preset(terrain: Terrain, name: str):
    """Saves a Terrain configuration to a reusable JSON file."""
    clean_name = "".join(x for x in name if x.isalnum() or x in " _-")
    file_path = os.path.join(TERRAINS_DIR, f"{clean_name}.json")
    
    # We save the dictionary representation
    data = terrain.to_dict()
    
    save_json(file_path, data)
    return file_path

def load_terrain_from_json(json_file_path: str) -> Optional[Terrain]:
    """Parses a JSON file into a Terrain object."""
    data = load_json(json_file_path)
        
    # data is expected to be the dict from Terrain.to_dict()
    # e.g. {"name": "Desert", "tag_multipliers": {...}}
    return Terrain.from_dict(data)

# endRegion