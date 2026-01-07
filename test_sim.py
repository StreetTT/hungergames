import random
import sys
import os

# Ensure we can import the game module from the current directory
sys.path.append(os.getcwd())

from game.engine import GameEngine
from game.models import Tribute, Terrain, Item

def run_test_sim():
    # 1. Setup Data
    seed = 42 # Fixed seed for reproducibility

    roster = [
        # District 1 (Luxury)
        Tribute("Marvel", 1, gender="M", proficient_items=["Spear"], stats={"strength": 8, "aggression": 7}),
        Tribute("Glimmer", 1, gender="F", proficient_items=["Bow"], stats={"speed": 7, "aggression": 6}),
        
        # District 2 (Masonry - Career)
        Tribute("Cato", 2, gender="M", proficient_items=["Sword"], stats={"strength": 9, "aggression": 9, "defense": 7}),
        Tribute("Clove", 2, gender="F", proficient_items=["Knife"], stats={"speed": 8, "stealth": 6, "aggression": 8}),
        
        # District 3 (Technology)
        Tribute("Beetee", 3, gender="M", proficient_items=["Wire"], stats={"intel": 10, "strength": 3}),
        Tribute("Wiress", 3, gender="F", proficient_items=["Tech"], stats={"intel": 9, "strength": 2}),
        
        # District 4 (Fishing - Career)
        Tribute("Finnick", 4, gender="M", proficient_items=["Trident"], stats={"strength": 7, "speed": 8, "aggression": 6}),
        Tribute("Mags", 4, gender="F", proficient_items=["Fishing Gear"], stats={"intel": 8, "speed": 2}),
        
        # District 5 (Power)
        Tribute("Foxface", 5, gender="F", proficient_items=["Apple"], stats={"stealth": 10, "intel": 9, "speed": 7}),
        Tribute("Hyde", 5, gender="M", proficient_items=["Knife"], stats={"stealth": 6, "intel": 6}),
        
        # District 6 (Transportation)
        Tribute("Jason", 6, gender="M", proficient_items=["Camouflage"], stats={"speed": 6, "stealth": 7}),
        Tribute("Kara", 6, gender="F", proficient_items=["Rope"], stats={"speed": 7, "defense": 5}),
        
        # District 7 (Lumber)
        Tribute("Johanna", 7, gender="F", proficient_items=["Axe"], stats={"strength": 7, "aggression": 8, "defense": 6}),
        Tribute("Blight", 7, gender="M", proficient_items=["Axe"], stats={"strength": 8, "speed": 4}),
        
        # District 8 (Textiles)
        Tribute("Cecelia", 8, gender="F", proficient_items=["Needle"], stats={"intel": 6, "defense": 4}),
        Tribute("Woof", 8, gender="M", proficient_items=["Fabric"], stats={"strength": 3, "defense": 2}),
        
        # District 9 (Grain)
        Tribute("Grain Boy", 9, gender="M", proficient_items=["Sickle"], stats={"strength": 6, "speed": 6}),
        Tribute("Grain Girl", 9, gender="F", proficient_items=["Sickle"], stats={"strength": 5, "speed": 7}),
        
        # District 10 (Livestock)
        Tribute("Sokka", 10, gender="M", proficient_items=["Boomerang"], stats={"intel": 8, "aggression": 4, "speed": 6}),
        Tribute("Toph", 10, gender="F", proficient_items=["Rock"], stats={"strength": 9, "intel": 4, "stealth": 1}),
        
        # District 11 (Agriculture)
        Tribute("Thresh", 11, gender="M", proficient_items=["Rock"], stats={"strength": 10, "aggression": 5, "speed": 4}),
        Tribute("Rue", 11, gender="F", proficient_items=["Slingshot"], stats={"stealth": 10, "speed": 9, "strength": 2}),
        
        # District 12 (Mining)
        Tribute("Katniss", 12, gender="F", proficient_items=["Bow"], stats={"strength": 6, "speed": 8, "intel": 7}),
        Tribute("Peeta", 12, gender="M", proficient_items=["Rock"], stats={"strength": 8, "defense": 6, "intel": 5})
    ]

    # Create Terrain (Empty item lists so Engine knows to populate them)
    finite_loot = [
        # --- Custom Unique Items (Objects) ---
        Item("Golden Cornucopia Sword", "weapon", {"strength": 6, "aggression": 3}),
        Item("Experimental Medkit", "medical", {"health": 50}),
        
        # --- Standard Library Items (Strings) ---
        # The Engine will convert these into full objects automatically
        "Trident",
        "Bow",
        "Axe",
        "Spear",
        "Mace",
        "Sickle", 
        "Boomerang", # Engine will generate a generic fallback for this since it's not in Library
        "Sais",
        "Night Vision",
        "Clean Water",
        "Explosive",
        "Land Mine"
    ]

    # INFINITE ITEMS (The "Factory")
    infinite_loot = [
        # --- Standard Library Items (Strings) ---
        "Rock",
        "Apple",
        "Camo Paint",
        "Bandages",
        
        # --- Custom Infinite Item (Object) ---
        # Maybe this arena has poisonous fog everywhere?
        Item("Gas Mask", "misc", {"defense": 1})
    ]

    terrain = Terrain(
        name="Mixed Input Arena",
        tag_multipliers={
            "forest": 1.2, 
            "water": 1.5,
            "scavenge": 1.0, 
            "combat": 1.1
        },
        finite_items=finite_loot,  
        infinite_items=infinite_loot
    )

    # 2. Initialize Engine
    # This will trigger _init_item_pool() inside the engine
    print("--- ⚙️ INITIALIZING ENGINE ---")
    engine = GameEngine(roster, terrain, rng_seed=seed)
    
    # 🕵️‍♂️ VERIFICATION: Print the item pools to prove injection worked
    print("\n--- 🛠️ DEBUG: Item Pool Generation ---")
    print(f"Finite Items (Deck): {{i.name: for i in engine.terrain.finite_items}}")
    print(f"Infinite Items (Factory): {[i.name for i in engine.terrain.infinite_items]}")
    print("--------------------------------------\n")

    # 3. Simulate
    print(f"Seed: {seed}")
    print(f"Tributes: {[t.name for t in roster]}")
    print("Simulating...")
    
    result = engine.simulate()

    # 4. Print Results (Using your requested format)
    print("\n--- 📜 GAME LOG ---")
    
    for day in result['timeline']:
        print(f"\n[DAY {day['day_number']}]")
        
        # Print Events
        for event in day['events']:
            # Add icons for readability
            if event['type'] == 'combat':
                icon = "⚔️ " 
            elif event['type'] == 'gamemaker':
                icon = "📢 "
            elif event['type'] == 'scavenge':
                icon = "🎒 "
            elif event['type'] == 'social':
                icon = "🤝 "
            else:
                icon = "🌲 "
                
            print(f"  {icon} {event['text']}")
        
        # Print Deaths
        if day['deaths_today']:
            print(f"  💀 DEAD: {', '.join(day['deaths_today'])}")

    print("\n-----------------------")
    print(f"🏆 WINNER: {result['meta']['winner']}")
    print("-----------------------")

if __name__ == "__main__":
    run_test_sim()