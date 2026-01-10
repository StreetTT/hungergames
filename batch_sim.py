import sys
import os
import random
import datetime
import copy
import json
from collections import Counter

# Ensure we can import the game module
sys.path.append(os.getcwd())

from game.engine import GameEngine
from game.models import Tribute, Terrain, Item
import game.serialiser as serialiser

# ==========================================
# 0. INSTRUMENTATION
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
            "id": event_id,
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
            event_id=event.name
        )

# ==========================================
# 1. CONFIGURATION
# ==========================================

# TOGGLES
USE_FIXED_SEED = False      # False = New RNG seed every game
USE_FIXED_TERRAIN = False   # False = Cycle through terrain types    # If True, attempts to load tributes/fiction_games.json

# SETTINGS
NUM_RUNS = 50               # Total games to simulate
FIXED_SEED = 42             # Used only if USE_FIXED_SEED is True
REPORT_DIR = "reports"      # Folder to save text files

# ==========================================
# 2. DATA SETUP
# ==========================================

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
    elif mode == 1:
        name = "Volcanic Forge"
        multipliers = {"fire": 3.0, "water": 0.0, "combat": 2.0, "scavenge": 0.5}
    elif mode == 2:
        name = "Frozen Wasteland"
        multipliers = {"cold": 3.0, "water": 2.0, "forest": 0.5, "fire": 0.1}
        
    # Pass EMPTY lists to force Engine to load FULL items.json
    return Terrain(name, multipliers, finite_items=[], infinite_items=[])

# ==========================================
# 3. REPORTING SYSTEM
# ==========================================

class BatchReport:
    def __init__(self):
        self.game_logs = [] 
        self.total_games = 0
        self.winners = Counter()
        self.districts_won = Counter()
        self.total_kills = Counter()
        self.event_tag_counts = Counter() 
        self.event_id_counts = Counter()
        self.winning_items = Counter()
        self.total_days = 0
        self.longest_game = 0
        self.shortest_game = 999

    def add_result(self, engine, run_id, seed, terrain_name):
        self.total_games += 1
        
        # Winner Info
        alive = engine.get_alive_tributes()
        if alive:
            winner = alive[0]
            w_name = winner.name
            w_dist = winner.district
        else:
            w_name = "Nobody"
            w_dist = "N/A"
        
        self.winners[w_name] += 1
        self.total_days += engine.day
        self.districts_won[w_dist] += 1
        if engine.day > self.longest_game: self.longest_game = engine.day
        if engine.day < self.shortest_game: self.shortest_game = engine.day
        
        # Events (Specials Logic: Bloodbath/Feast only count once per game)
        events_this_game = set()
        for day in engine.game_log['timeline']:
            for event in day['events']:
                # Tags
                etype = event.get('type', 'unknown')
                self.event_tag_counts[etype] += 1
                
                # IDs
                eid = event.get('id')
                if eid:
                    if eid in ["Bloodbath", "The Feast"]:
                        if eid not in events_this_game:
                            self.event_id_counts[eid] += 1
                            events_this_game.add(eid)
                    else:
                        self.event_id_counts[eid] += 1

        # Kills & Items
        kill_leader = "None"
        max_kills = -1
        for t in engine.tributes:
            self.total_kills[t.name] += len(t.kills)
            if len(t.kills) > max_kills:
                max_kills = len(t.kills)
                kill_leader = t.name

        self.game_logs.append({
            "id": run_id,
            "seed": seed,
            "days": engine.day,
            "winner": w_name,
            "terrain": terrain_name,
            "district": w_dist,
            "kill_leader": kill_leader
        })

    def save_to_file(self):
        if not os.path.exists(REPORT_DIR): os.makedirs(REPORT_DIR)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{REPORT_DIR}/sim_report_{timestamp}.txt"
        
        # --- FORMATTING HELPER ---
        def fmt(text, width):
            s = str(text)
            if len(s) <= width: 
                return f"{s:<{width}}"
            # Middle Truncate
            head = (width - 3) // 2
            tail = (width - 3) - head
            return f"{s[:head]}...{s[-tail:]}"

        with open(filename, "w", encoding="utf-8") as f:
            f.write("="*100 + "\n")
            f.write(f"📊 BATCH SIMULATION REPORT\n")
            f.write(f"Generated: {timestamp}\n")
            f.write(f"Total Games: {self.total_games}\n")
            f.write("="*100 + "\n\n")

            f.write(f"--- ⏱️ DURATION ---\n")
            f.write(f"Avg Length:    {self.total_days / self.total_games:.1f} days\n")
            f.write(f"Shortest:      {self.shortest_game} days\n")
            f.write(f"Longest:       {self.longest_game} days\n\n")

            f.write(f"--- 🏆 ALL WINNERS ---\n")
            for name, wins in self.winners.most_common():
                pct = (wins / self.total_games) * 100
                f.write(f"{fmt(name, 25)} {wins} wins ({pct:.1f}%)\n")
            
            f.write(f"\n--- 💀 DEADLIEST TRIBUTES ---\n")
            for name, kills in self.total_kills.most_common(10):
                f.write(f"{fmt(name, 25)} {kills} kills\n")

            f.write(f"\n--- 🏷️ EVENT BREAKDOWN (Tags) ---\n")
            for tag, count in self.event_tag_counts.most_common():
                f.write(f"{fmt(tag, 25)} {count}\n")

            f.write(f"\n--- 🌍 EVENT BREAKDOWN (IDs) ---\n")
            for eid, count in self.event_id_counts.most_common():
                f.write(f"{fmt(eid, 35)} {count}\n")

            f.write("\n" + "="*145 + "\n")
            f.write("📜 FULL GAMES BREAKDOWN\n")
            f.write("="*145 + "\n")
            
            # DEFINE COLUMN WIDTHS
            w_id, w_seed, w_day, w_win, w_dist, w_terr = 4, 8, 4, 20, 6, 20
            
            # Header
            header = (
                f"{fmt('ID', w_id)} | {fmt('Seed', w_seed)} | {fmt('Day', w_day)} | "
                f"{fmt('Winner', w_win)} | {fmt('Dist', w_dist)} | {fmt('Terrain', w_terr)} |"
            )
            f.write(header + "\n")
            f.write("-" * len(header) + "\n")
            
            for log in self.game_logs:
                
                row = (
                    f"{fmt(log['id'], w_id)} | {fmt(log['seed'], w_seed)} | {fmt(log['days'], w_day)} | "
                    f"{fmt(log['winner'], w_win)} | {fmt(log['district'], w_dist)} | {fmt(log['terrain'], w_terr)} | "
                )
                f.write(row + "\n")
        
        print(f"\n✅ Report saved to: {filename}")

# ==========================================
# 4. MAIN LOOP
# ==========================================

def run_batch():
    report = BatchReport()
    print(f"🚀 Starting Batch Sim: {NUM_RUNS} runs...")
    
    for i in range(NUM_RUNS):
        # 1. SETUP SEED FIRST
        if USE_FIXED_SEED:
            current_seed = FIXED_SEED
        else:
            current_seed = random.randint(1, 999999)
            
        random.seed(current_seed)
        
        # 2. GENERATE TERRAIN
        t_index = 0 if USE_FIXED_TERRAIN else i
        base_terrain = generate_varied_terrain(t_index)
        
        # 3. DEEP COPY
        sim_terrain = copy.deepcopy(base_terrain)
        sim_roster = get_roster()
        
        # 4. RE-APPLY SEED (Safety)
        random.seed(current_seed)
        
        # 5. RUN
        engine = InstrumentedGameEngine(sim_roster, sim_terrain, rng_seed=current_seed) #type: ignore
        engine.simulate()
        
        report.add_result(engine, i+1, current_seed, sim_terrain.name)
        sys.stdout.write(f"\rRun {i+1}/{NUM_RUNS} | Winner: {engine.game_log['meta']['winner']}")
        sys.stdout.flush()

    report.save_to_file()

if __name__ == "__main__":
    run_batch()