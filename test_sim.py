import random
import sys
import os

# Ensure we can import the game module from the current directory
sys.path.append(os.getcwd())

from game.engine import GameEngine
from game.models import Tribute, Terrain, Item

def run_test_sim():

    seed = 42 # Fixed seed for reproducibility
    # ==========================================
    # 1. SETUP ROSTER (24 TRIBUTES)
    # ==========================================
    roster = [
        # District 1
        Tribute("Marvel", 1, gender="M", proficient_items=["Spear"], stats={"strength": 8, "aggression": 7, "speed": 6}),
        Tribute("Glimmer", 1, gender="F", proficient_items=["Bow"], stats={"speed": 7, "aggression": 6, "intel": 5}),
        # District 2
        Tribute("Cato", 2, gender="M", proficient_items=["Sword"], stats={"strength": 9, "aggression": 9, "defense": 7}),
        Tribute("Clove", 2, gender="F", proficient_items=["Knife"], stats={"speed": 8, "stealth": 6, "aggression": 8}),
        # District 3
        Tribute("Beetee", 3, gender="M", proficient_items=["Wire"], stats={"intel": 10, "strength": 3, "defense": 4}),
        Tribute("Wiress", 3, gender="F", proficient_items=["Tech"], stats={"intel": 9, "strength": 2, "stealth": 5}),
        # District 4
        Tribute("Finnick", 4, gender="M", proficient_items=["Trident"], stats={"strength": 7, "speed": 8, "aggression": 6}),
        Tribute("Mags", 4, gender="F", proficient_items=["Fishing Gear"], stats={"intel": 8, "speed": 2, "stealth": 6}),
        # District 5
        Tribute("Foxface", 5, gender="F", proficient_items=["Apple"], stats={"stealth": 10, "intel": 9, "speed": 7}),
        Tribute("Hyde", 5, gender="M", proficient_items=["Knife"], stats={"stealth": 6, "intel": 6, "aggression": 5}),
        # District 6
        Tribute("Jason", 6, gender="M", proficient_items=["Camouflage"], stats={"speed": 6, "stealth": 7, "intel": 5}),
        Tribute("Kara", 6, gender="F", proficient_items=["Rope"], stats={"speed": 7, "defense": 5, "intel": 6}),
        # District 7
        Tribute("Johanna", 7, gender="F", proficient_items=["Axe"], stats={"strength": 7, "aggression": 8, "defense": 6}),
        Tribute("Blight", 7, gender="M", proficient_items=["Axe"], stats={"strength": 8, "speed": 4, "defense": 5}),
        # District 8
        Tribute("Cecelia", 8, gender="F", proficient_items=["Needle"], stats={"intel": 6, "defense": 4, "speed": 5}),
        Tribute("Woof", 8, gender="M", proficient_items=["Fabric"], stats={"strength": 3, "defense": 2, "intel": 4}),
        # District 9
        Tribute("Grain Boy", 9, gender="M", proficient_items=["Sickle"], stats={"strength": 6, "speed": 6, "aggression": 5}),
        Tribute("Grain Girl", 9, gender="F", proficient_items=["Sickle"], stats={"strength": 5, "speed": 7, "stealth": 6}),
        # District 10
        Tribute("Sokka", 10, gender="M", proficient_items=["Boomerang"], stats={"intel": 8, "aggression": 4, "speed": 6}),
        Tribute("Toph", 10, gender="F", proficient_items=["Rock"], stats={"strength": 9, "intel": 4, "stealth": 1}),
        # District 11
        Tribute("Thresh", 11, gender="M", proficient_items=["Rock"], stats={"strength": 10, "aggression": 5, "speed": 4}),
        Tribute("Rue", 11, gender="F", proficient_items=["Slingshot"], stats={"stealth": 10, "speed": 9, "strength": 2}),
        # District 12
        Tribute("Katniss", 12, gender="F", proficient_items=["Bow"], stats={"strength": 6, "speed": 8, "intel": 7}),
        Tribute("Peeta", 12, gender="M", proficient_items=["Rock"], stats={"strength": 8, "defense": 6, "intel": 5})
    ]

    # ==========================================
    # 2. SETUP TERRAIN
    # ==========================================
    finite_loot = [
        # Custom Objects
        Item("Golden Cornucopia Sword", "weapon", {"strength": 6, "aggression": 3}),
        Item("Experimental Medkit", "medical", {"health": 50}),
        # Strings (Will be resolved by Engine)
        "Trident", "Bow", "Axe", "Spear", "Mace", "Sickle", 
        "Boomerang", "Sais", "Night Vision", "Clean Water", 
        "Explosive", "Land Mine" "Medical Supplies", "Medical Supplies", 
        "Medical Supplies", "Medical Supplies", "Medical Supplies", "Medical Supplies"
    ]

    infinite_loot = [
        "Rock", "Apple", "Camo Paint", "Bandages",
        Item("Gas Mask", "misc", {"defense": 1})
    ]

    terrain = Terrain(
        name="Mixed Input Arena",
        tag_multipliers={"forest": 1.2, "water": 1.5, "scavenge": 1.0, "combat": 1.1},
        finite_items=finite_loot,
        infinite_items=infinite_loot
    )

    # ==========================================
    # 3. INITIALIZE & RUN
    # ==========================================
    print(f"--- ⚙️ INITIALIZING ENGINE with {len(roster)} Tributes ---")
    engine = GameEngine(roster, terrain, rng_seed=seed)
    
    print(f"Seed: {seed}")
    print("Simulating...")
    result = engine.simulate()

    # 4. PRINT RESULTS
    print("\n--- 📜 GAME LOG ---")
    
    for day in result['timeline']:
        dayHeadding = day.get('day_name', f"DAY {day['day_number']}")
        print(f"\n[{dayHeadding}]")
        
        # A. EVENTS
        for event in day['events']:
            # Extended Icon Map for new Event Types
            icon_map = {
                # Core
                'combat': "⚔️ ", 
                'death': "💀 ", 
                'gamemaker': "📢 ", 
                'idle': "⏳ ",
                
                # Actions
                'scavenge': "🎒 ", 
                'crafting': "🔨 ", 
                'training': "🎯 ",
                'stealth': "🥷 ",
                'intel': "🧠 ",
                
                # Interactions
                'social': "💬 ", 
                'trade': "⚖️ ",
                'romance': "❤️ ",
                'betrayal': "🔪 ",
                'conflict': "😠 ",
                'funny': "😆 ",
                'sad': "😢 ",
                
                # Health/Status
                'medical': "💊 ", 
                'accident': "🤕 ",
                'mental': "😵‍💫 ",
                'sponsor': "🎁 ",
                
                # Environment
                'forest': "🌲 ", 
                'water': "💧 ", 
                'weather': "⛈️ ",
                'pve': "🐺 ",
                'dangerous': "⚠️ "
            }
            
            # Default to "🌲" if the tag isn't found
            icon = icon_map.get(event['type'], "🌲 ")
            
            # Print the event line
            print(f"  {icon} {event['text']}")
        
        # B. DEATHS
        if day['deaths_today']:
            print(f"  💀 DEAD: {', '.join(day['deaths_today'])}")

        # C. ALLIANCE BREAKDOWN
        if "alliance_snapshot" in day:
            print(f"  📊 STATUS REPORT:")
            for idx, group in enumerate(day["alliance_snapshot"]):
                members_str = []
                for m in group["members"]:
                    # Create status flags string e.g. "(Injured)"
                    status_txt = f" ({', '.join(m['status_effects'])})" if m['status_effects'] else ""
                    # Inventory string
                    inv_txt = f"[{', '.join(m['inventory'])}]" if m['inventory'] else "[]"
                    
                    members_str.append(f"{m['name']} {m['health']}HP{status_txt} {inv_txt}")
                
                # Format shared inventory
                shared_str = ""
                if group["shared_inventory"]:
                    shared_str = f" | 📦 SHARED: {', '.join(group['shared_inventory'])}"
                    
                print(f"    Group {idx+1}: {', '.join(members_str)}{shared_str}")

    print("\n-----------------------")
    print(f"🏆 WINNER: {result['meta']['winner']}")
    print("-----------------------")

if __name__ == "__main__":
    run_test_sim()