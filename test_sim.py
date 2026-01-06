import json
import random
from game.engine import GameEngine
from game.models import Tribute, Terrain
from game.serialiser import save_terrain_preset, load_terrain_from_json

def create_dummy_roster():
    """Creates 4 test characters for our battle."""
    return [
        Tribute("Katniss", 12, "url_k", {"strength": 4, "speed": 8, "intel": 7, "aggression": 3}, proficient_items=["Bow"], gender='F'),
        Tribute("Peeta", 12, "url_p", {"strength": 8, "defense": 6, "intel": 4, "aggression": 2}, proficient_items=["Rock"], gender='M'),
        Tribute("Cato", 2, "url_c", {"strength": 9, "speed": 6, "defense": 5, "aggression": 9}, proficient_items=["Sword"], gender='N'),
        Tribute("Rue", 11, "url_r", {"strength": 2, "speed": 9, "stealth": 10, "aggression": 1}, proficient_items=["Camo Paint"], gender='F')
    ]

def run_test():
    print("--- 🟢 STARTING SIMULATION TEST ---")

    # 1. Setup Data
    roster = create_dummy_roster()
    
    # Create a "Forest" terrain where water events are rare, forest events are common
    terrain = Terrain("Volcanic", {"fire": 3.0, "water": 0.0})

    # Save it
    save_path = save_terrain_preset(terrain, "MyVolcano")
    print(f"Saved terrain to {save_path}")

    # Load it back
    loaded_terrain = load_terrain_from_json(save_path)
    print(f"Loaded: {loaded_terrain.name} with water mod: {loaded_terrain.tag_multipliers.get('water')}")

    # 2. Initialize Engine
    # We use a fixed seed (1234) so the result is the same every time you run this script.
    # Change the seed to see different outcomes!
    seed = 1234 
    engine = GameEngine(roster, terrain, seed)

    # 3. Run Simulation
    print(f"Seed: {seed}")
    print(f"Tributes: {[t.name for t in roster]}")
    print("Simulating...")
    
    result = engine.simulate()

    # 4. Print Results
    print("\n--- 📜 GAME LOG ---")
    
    for day in result['timeline']:
        print(f"\n[DAY {day['day_number']}]")
        
        # Print Events
        for event in day['events']:
            # Add icons for readability
            icon = "⚔️ " if event['type'] == 'combat' else "🌲"
            print(f"  {icon} {event['text']}")
        
        # Print Deaths
        if day['deaths_today']:
            print(f"  💀 DEAD: {', '.join(day['deaths_today'])}")

    print("\n-----------------------")
    print(f"🏆 WINNER: {result['meta']['winner']}")
    print("-----------------------")

if __name__ == "__main__":
    run_test()