import sys
import os
import random
import datetime
from collections import Counter
import json

# Ensure we can import the game module
sys.path.append(os.getcwd())

from game.engine import GameEngine
from game.models import Tribute, Terrain, Item

# ==========================================
# 0. INSTRUMENTATION (Subclassing GameEngine)
# ==========================================

class InstrumentedGameEngine(GameEngine):
    """
    A subclass of GameEngine that intercepts event logging to capture
    the specific Event ID (e.g., 'scavenge_berries') instead of just the generic type.
    """
    def _log_event(self, text, type_tag, tributes=None, image_url=None, event_id=None):
        if tributes is None: tributes = []
        
        # Append the event to the log with the extra 'id' field
        self.current_day_log["events"].append({
            "text": text,
            "type": type_tag,
            "id": event_id,        # <--- The new field we want to track
            "tributes_involved": tributes,
            "image": image_url
        })

    def _run_and_log_event(self, event, alliance):
        # Replicates the logic from GameEngine._run_and_log_event 
        # but extracts the event.name (ID) and passes it to _log_event.
        
        participants = [t.name for t in alliance.members]
        leader_img = alliance.members[0].image_url if alliance.members else None
        
        # Execute the event logic
        text = event.execute(alliance, self.terrain, game_engine_ref=self)
        
        # Log it with the ID
        self._log_event(
            text=text or "",
            type_tag=event.tags[0] if event.tags else "misc",
            tributes=participants,
            image_url=leader_img,
            event_id=event.name    # <--- Capturing the ID (event.name holds the JSON ID)
        )

# ==========================================
# 1. CONFIGURATION
# ==========================================

# TOGGLES
USE_FIXED_SEED = False      # False = New RNG seed every game
USE_FIXED_TERRAIN = False   # False = Cycle through terrain types

# SETTINGS
NUM_RUNS = 50               # Total games to simulate
FIXED_SEED = 42             # Used only if USE_FIXED_SEED is True
REPORT_DIR = "reports"      # Folder to save text files

# ==========================================
# 2. DATA POOLS (For Variance)
# ==========================================

# We pick a random subset of these for each game to keep things fresh
STANDARD_LOOT = ["Sword", "Bow", "Mace", "Spear", "Axe", "Trident", "Medkit", "Backpack", "Water", "Food", "Rope", "Camo Paint"]
VOLCANO_LOOT = ["Obsidian Knife", "Magma Spear", "Medkit", "Ash Mask", "Fireproof Vest", "Rock", "Sulfur", "Burn Salve"]
FROZEN_LOOT = ["Ice Pick", "Fur Coat", "Matches", "Snowshoes", "Dried Meat", "Vodka", "Thermal Blanket", "Hatchet"]

def get_roster():
    """Returns a fresh list of tributes for each run."""
    return [
        Tribute(name="Marvel", district=1, gender="M", proficient_items=["Spear"], stats={"strength": 8, "aggression": 7, "speed": 6}),
        Tribute(name="Glimmer", district=1, gender="F", proficient_items=["Bow"], stats={"speed": 7, "aggression": 6, "intel": 5}),
        Tribute(name="Cato", district=2, gender="M", proficient_items=["Sword"], stats={"strength": 9, "aggression": 9, "defense": 7}),
        Tribute(name="Clove", district=2, gender="F", proficient_items=["Knife"], stats={"speed": 8, "stealth": 6, "aggression": 8}),
        Tribute(name="Beetee", district=3, gender="M", proficient_items=["Wire"], stats={"intel": 10, "strength": 3, "defense": 4}),
        Tribute(name="Wiress", district=3, gender="F", proficient_items=["Tech"], stats={"intel": 9, "strength": 2, "stealth": 5}),
        Tribute(name="Finnick", district=4, gender="M", proficient_items=["Trident"], stats={"strength": 7, "speed": 8, "aggression": 6}),
        Tribute(name="Mags", district=4, gender="F", proficient_items=["Fishing Gear"], stats={"intel": 8, "speed": 2, "stealth": 6}),
        Tribute(name="Foxface", district=5, gender="F", proficient_items=["Apple"], stats={"stealth": 10, "intel": 9, "speed": 7}),
        Tribute(name="Hyde", district=5, gender="M", proficient_items=["Knife"], stats={"stealth": 6, "intel": 6, "aggression": 5}),
        Tribute(name="Johanna", district=7, gender="F", proficient_items=["Axe"], stats={"strength": 7, "aggression": 8, "defense": 6}),
        Tribute(name="Blight", district=7, gender="M", proficient_items=["Axe"], stats={"strength": 8, "speed": 4, "defense": 5}),
        Tribute(name="Thresh", district=11, gender="M", proficient_items=["Rock"], stats={"strength": 10, "aggression": 5, "speed": 4}),
        Tribute(name="Rue", district=11, gender="F", proficient_items=["Slingshot"], stats={"stealth": 10, "speed": 9, "strength": 2}),
        Tribute(name="Katniss", district=12, gender="F", proficient_items=["Bow"], stats={"strength": 6, "speed": 8, "intel": 7}),
        Tribute(name="Peeta", district=12, gender="M", proficient_items=["Rock"], stats={"strength": 8, "defense": 6, "intel": 5}),
    ]

def generate_varied_terrain(index) -> Terrain:
    """
    Generates a Terrain object with VARIANCE.
    The item pools will change slightly every time this is called.
    """
    # 0 = Standard, 1 = Volcano, 2 = Frozen
    mode = index % 3 
    
    if mode == 0:
        name = "Standard Arena"
        multipliers = {"forest": 1.0, "water": 1.0, "combat": 1.0, "scavenge": 1.0}
        pool = STANDARD_LOOT
        infinite = ["Rock", "Stick", "Mud"]
    elif mode == 1:
        name = "Volcanic Forge"
        multipliers = {"fire": 3.0, "water": 0.0, "combat": 2.0, "scavenge": 0.5}
        pool = VOLCANO_LOOT
        infinite = ["Ash", "Rock"]
    else:
        name = "Frozen Wasteland"
        multipliers = {"cold": 3.0, "water": 2.0, "forest": 0.5, "fire": 0.1}
        pool = FROZEN_LOOT
        infinite = ["Snowball", "Icicle"]

    # --- VARIANCE LOGIC ---
    # Randomly select 4-6 items for the Finite Pool
    finite_names = random.sample(pool, k=random.randint(4, min(len(pool), 7)))
    
    # Randomly select 1-2 items for Infinite Pool to make resources scarce/abundant
    infinite_names = random.sample(infinite, k=random.randint(1, len(infinite)))

    # ==========================================
    # HELPER: ITEM RESOLUTION
    # ==========================================
    ITEM_LOOKUP = {}
    def load_item_lookup():
        """Loads item stats so we can create real objects."""
        if ITEM_LOOKUP: return

        # 1. Try loading from JSON (Repo Structure)
        path = os.path.join("game", "data", "items.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                data = json.load(f)
                for d in data:
                    ITEM_LOOKUP[d['name']] = d
            return

    def get_item_obj(name):
            """Converts a string name into a full Item object."""
            if not ITEM_LOOKUP: load_item_lookup()
            
            data = ITEM_LOOKUP.get(name)
            if data:
                return Item(data['name'], data['kind'], data.get('bonuses'))
            
            # Generic fallback if not found
            return Item(name, "misc")

    finite_objs = [get_item_obj(n) for n in finite_names]
    infinite_objs = [get_item_obj(n) for n in infinite_names]

    return Terrain(
        name=name,
        tag_multipliers=multipliers,
        finite_items=finite_objs,
        infinite_items=infinite_objs
    )

# ==========================================
# 3. REPORTING SYSTEM
# ==========================================

class BatchReport:
    def __init__(self):
        self.game_logs = [] # Stores short summary of each game
        self.total_games = 0
        self.winners = Counter()
        self.districts_won = Counter()
        self.total_kills = Counter()
        self.event_tag_counts = Counter() # Tracks Generic Types (e.g. 'scavenge', 'combat')
        self.event_id_counts = Counter()  # Tracks Specific IDs (e.g. 'scavenge_berries')
        self.winning_items = Counter()
        self.longest_game = 0
        self.shortest_game = 999
        self.total_days = 0

    def add_result(self, engine, run_id, seed, terrain_name):
        self.total_games += 1
        
        # 1. Winner Stats
        alive = engine.get_alive_tributes()
        if alive:
            winner = alive[0]
            w_name = winner.name
            w_dist = winner.district
            w_items = [i.name for i in winner.inventory]
        else:
            w_name = "Nobody"
            w_dist = "N/A"
            w_items = []

        self.winners[w_name] += 1
        self.districts_won[w_dist] += 1
        
        # 2. Game Length
        days = engine.day
        self.total_days += days
        if days > self.longest_game: self.longest_game = days
        if days < self.shortest_game: self.shortest_game = days

        # 3. Global Stats
        for day in engine.game_log['timeline']:
            for event in day['events']:
                # Track Tag (Always present)
                etype = event.get('type', 'unknown')
                self.event_tag_counts[etype] += 1
                
                # Track ID (Only present if InstrumentedGameEngine captured it)
                eid = event.get('id')
                if eid:
                    self.event_id_counts[eid] += 1

        for t in engine.tributes:
            self.total_kills[t.name] += len(t.kills)
            if t.alive:
                for item in t.inventory:
                    self.winning_items[item.name] += 1
        
        # 4. Detailed Single-Game Log
        self.game_logs.append({
            "id": run_id,
            "seed": seed,
            "terrain": terrain_name,
            "days": days,
            "winner": w_name,
            "loadout": w_items,
            "kill_leader": max(engine.tributes, key=lambda t: len(t.kills)).name
        })

    def save_to_file(self):
        if not os.path.exists(REPORT_DIR):
            os.makedirs(REPORT_DIR)
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{REPORT_DIR}/sim_report_{timestamp}.txt"
        
        with open(filename, "w", encoding="utf-8") as f:
            f.write("="*60 + "\n")
            f.write(f"📊 BATCH SIMULATION REPORT\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Total Games: {self.total_games}\n")
            f.write("="*60 + "\n\n")

            f.write(f"--- ⏱️ DURATION ---\n")
            f.write(f"Avg Length:    {self.total_days / self.total_games:.1f} days\n")
            f.write(f"Shortest:      {self.shortest_game} days\n")
            f.write(f"Longest:       {self.longest_game} days\n\n")

            f.write(f"--- 🏆 TOP WINNERS ---\n")
            for name, wins in self.winners.most_common(10):
                pct = (wins / self.total_games) * 100
                f.write(f"{name:<15} {wins} wins ({pct:.1f}%)\n")
            
            f.write(f"\n--- 💀 DEADLIEST TRIBUTES ---\n")
            for name, kills in self.total_kills.most_common(10):
                f.write(f"{name:<15} {kills} kills\n")

            f.write(f"\n--- 🎒 BEST ITEMS (Held by Winners) ---\n")
            for item, count in self.winning_items.most_common(10):
                f.write(f"{item:<15} Used {count} times\n")
            
            f.write(f"\n--- 🏷️ EVENT TAG BREAKDOWN (Generic Types) ---\n")
            f.write(f"{'Tag':<20} | {'Count'}\n")
            f.write("-" * 30 + "\n")
            for tag, count in self.event_tag_counts.most_common():
                f.write(f"{tag:<20} | {count}\n")
                
            f.write(f"\n--- 🌍 SPECIFIC EVENT ID FREQUENCY ---\n")
            f.write(f"{'Event ID':<35} | {'Count'}\n")
            f.write("-" * 45 + "\n")
            for eid, count in self.event_id_counts.most_common():
                f.write(f"{eid:<35} | {count}\n")

            f.write("\n" + "="*60 + "\n")
            f.write("📜 FULL GAME BREAKDOWN\n")
            f.write("="*60 + "\n")
            f.write(f"{'ID':<4} | {'Seed':<8} | {'Days':<4} | {'Winner':<12} | {'Terrain':<20} | {'Loadout'}\n")
            f.write("-" * 100 + "\n")
            
            for log in self.game_logs:
                items_str = ", ".join(log['loadout']) if log['loadout'] else "None"
                f.write(f"{log['id']:<4} | {log['seed']:<8} | {log['days']:<4} | {log['winner']:<12} | {log['terrain']:<20} | {items_str}\n")
        
        print(f"\n✅ Report saved to: {filename}")

# ==========================================
# 4. MAIN LOOP
# ==========================================

def run_batch():
    report = BatchReport()
    
    print(f"🚀 Starting Batch Sim: {NUM_RUNS} runs...")
    
    for i in range(NUM_RUNS):
        # 1. Setup Terrain (Standard, Volcano, or Frozen)
        # If FIXED_TERRAIN is on, we always pass 0 (Standard)
        t_index = 0 if USE_FIXED_TERRAIN else i
        terrain = generate_varied_terrain(t_index)
        
        # 2. Setup Seed
        seed = FIXED_SEED if USE_FIXED_SEED else random.randint(1, 999999)

        # 3. Init Engine (Using the INSTRUMENTED version)
        roster = get_roster() 
        engine = InstrumentedGameEngine(roster, terrain, rng_seed=seed)
        
        # 4. Run Sim
        engine.simulate()
        
        # 5. Record Data
        report.add_result(engine, i+1, seed, terrain.name)
        
        # Progress Bar
        sys.stdout.write(f"\rProcessing: {i+1}/{NUM_RUNS} | Map: {terrain.name} | Winner: {engine.game_log['meta']['winner']}")
        sys.stdout.flush()

    # Save to file
    report.save_to_file()

if __name__ == "__main__":
    run_batch()