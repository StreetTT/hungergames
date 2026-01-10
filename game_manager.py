import sys
import os
import random
import json
import datetime
from collections import Counter

# Ensure we can import the game module
sys.path.append(os.getcwd())

from game.engine import GameEngine
from game.models import Tribute, Terrain, Item
import game.serialiser as serialiser

class GameManager:
    def __init__(self):
        self.roster = []
        self.terrain = None
        self.seed = None
        self.last_result = None
        self.engine = None 

    # --- FORMATTING HELPER ---
    @staticmethod
    def _fmt_cell(text, width):
        """Standardizes cell width with middle truncation."""
        s = str(text)
        if len(s) <= width: 
            return f"{s:<{width}}"
        # Middle Truncate
        head = (width - 3) // 2
        tail = (width - 3) - head

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def print_header(self):
        self.clear_screen()
        print("==========================================")
        print("🏹 HUNGER GAMES SIMULATION MANAGER 🏹")
        print("==========================================")
        if self.roster:
            print(f"👥 Current Roster: {len(self.roster)} Tributes Loaded")
        else:
            print(f"👥 Current Roster: [EMPTY]")
        
        if self.terrain:
            print(f"🌍 Current Terrain: {self.terrain.name}")
        else:
            print(f"🌍 Current Terrain: [EMPTY]")
        
        if self.seed:
            print(f"🎲 Active Seed: {self.seed}")
        print("------------------------------------------")

    def main_menu(self):
        while True:
            self.print_header()
            print("1. Manage Roster (Create/Edit/Load)")
            print("2. Manage Terrain (Create/Edit/Load)")
            print("3. Simulation Settings (Seed)")
            print("4. RUN SIMULATION")
            print("5. Load Replay (Full Game State)")
            print("X. Exit")
            print("------------------------------------------")
            
            choice = input("Select Option: ").upper()
            
            if choice == '1': self.menu_roster()
            elif choice == '2': self.menu_terrain()
            elif choice == '3': self.menu_seed()
            elif choice == '4': self.run_simulation()
            elif choice == '5': self.load_replay()
            elif choice == 'X': sys.exit()

    # ==========================
    # ROSTER MANAGEMENT
    # ==========================
    def menu_roster(self):
        while True:
            self.clear_screen()
            print("==========================================")
            print("👥 ROSTER MANAGEMENT")
            print(f"Current Size: {len(self.roster)}")
            print("==========================================")
            print("1. Create New Roster (Wizard)")
            print("2. Load Roster from File")
            print("3. Generate Random Roster (Quick)")
            print("4. View/Edit Current Roster")
            print("5. Save Current Roster")
            print("B. Back")
            print("------------------------------------------")
            
            c = input("Choice: ").upper()
            if c == '1': self.create_roster_wizard()
            elif c == '2': self.load_roster_file()
            elif c == '3': self.generate_random_roster()
            elif c == '4': self.edit_roster_interactive()
            elif c == '5': self.save_current_roster()
            elif c == 'B': break

    def create_roster_wizard(self):
        self.roster = []
        print("\n--- Creating New Roster ---")
        try:
            count = int(input("How many tributes? "))
        except:
            print("Invalid number.")
            return

        for i in range(count):
            print(f"\n--- Tribute {i+1}/{count} ---")
            self.add_single_tribute()
        print("✅ Roster Created.")

    def add_single_tribute(self):
        name = input("Name: ") or "Unknown"
        dist = int(input("District (1-12): ") or "12")
        gender = input("Gender (M/F/N): ").upper() or "N"
        
        print("Stats (1-10 scale, default 5)")
        stats = {}
        for s in ["strength", "speed", "intel", "defense", "aggression", "stealth"]:
            val = input(f"  {s.capitalize()}: ")
            stats[s] = int(val) if val else 5
            
        t = Tribute(name, dist, gender=gender, stats=stats)
        self.roster.append(t)

    def generate_random_roster(self):
        self.roster = [
            Tribute(f"Tribute {i+1}", random.randint(1,12), gender=random.choice(["M","F"])) 
            for i in range(24)
        ]
        print("✅ Random Roster of 24 Generated.")
        input("Press Enter...")

    def edit_roster_interactive(self):
        if not self.roster:
            print("Roster is empty.")
            input("Press Enter...")
            return

        while True:
            self.clear_screen()
            print(f"👥 EDITING ROSTER ({len(self.roster)} Tributes)")
            
            # Define Widths
            w_id, w_name, w_dist = 3, 20, 4
            w_stat = 3
            
            header = (
                f"{self._fmt_cell('#', w_id)} | {self._fmt_cell('Name', w_name)} | {self._fmt_cell('Dist', w_dist)} | "
                f"{self._fmt_cell('Str', w_stat)} | {self._fmt_cell('Int', w_stat)} | {self._fmt_cell('Spd', w_stat)} | {self._fmt_cell('Agg', w_stat)} | {self._fmt_cell('Stl', w_stat)} | {self._fmt_cell('Def', w_stat)} |"
            )
            print(header)
            print("-" * len(header))
            
            for idx, t in enumerate(self.roster):
                line = (
                    f"{self._fmt_cell(idx+1, w_id)} | {self._fmt_cell(t.name, w_name)} | {self._fmt_cell(t.district, w_dist)} | "
                    f"{self._fmt_cell(t.stats['strength'], w_stat)} | {self._fmt_cell(t.stats['intel'], w_stat)} | {self._fmt_cell(t.stats['speed'], w_stat)} | "
                    f"{self._fmt_cell(t.stats['aggression'], w_stat)} | {self._fmt_cell(t.stats['stealth'], w_stat)} | {self._fmt_cell(t.stats['defense'], w_stat)} |"
                )
                print(line)
            
            print("-" * len(header))
            print("Enter ID to edit, 'A' to Add, 'D [ID]' to Delete, or 'B' to Back")
            cmd = input("Command: ").strip().upper()
            
            if cmd == 'B': break
            elif cmd == 'A': 
                self.add_single_tribute()
            elif cmd.startswith('D '):
                try:
                    idx = int(cmd.split()[1]) - 1
                    if 0 <= idx < len(self.roster):
                        removed = self.roster.pop(idx)
                        print(f"🗑️ Removed {removed.name}")
                        input("Press Enter...")
                except: pass
            else:
                try:
                    idx = int(cmd) - 1
                    if 0 <= idx < len(self.roster):
                        self.edit_tribute_detail(self.roster[idx])
                except: pass

    def edit_tribute_detail(self, t):
        while True:
            self.clear_screen()
            print(f"✏️ EDITING: {t.name}")
            print("1. Name       :", t.name)
            print("2. District   :", t.district)
            print("3. Gender     :", t.gender)
            print("4. Stats      :", t.stats)
            print("5. Proficiencies:", t.proficient_items)
            print("B. Back")
            
            c = input("Edit which field? ").upper()
            if c == '1': t.name = input(f"New Name [{t.name}]: ") or t.name
            elif c == '2': t.district = int(input(f"New District [{t.district}]: ") or t.district)
            elif c == '3': t.gender = input(f"New Gender [{t.gender}]: ").upper() or t.gender
            elif c == '4':
                for s in t.stats:
                    val = input(f"  {s.capitalize()} [{t.stats[s]}]: ")
                    if val: t.stats[s] = int(val)
            elif c == '5':
                val = input("Enter comma-separated items (e.g. Bow, Axe): ")
                if val: t.proficient_items = [x.strip() for x in val.split(",")]
            elif c == 'B': break

    def load_roster_file(self):
        files = [f for f in os.listdir(serialiser.TRIBUTES_DIR) if f.endswith('.json')]
        if not files:
            print("No saved rosters found.")
            input("Press Enter...")
            return

        print("\nAvailable Rosters:")
        for idx, f in enumerate(files):
            print(f"{idx+1}. {f}")
        
        try:
            sel = int(input("Select file number: ")) - 1
            path = os.path.join(serialiser.TRIBUTES_DIR, files[sel])
            loaded = serialiser.load_tributes_from_json(path)
            if loaded:
                self.roster = loaded
                print(f"✅ Loaded {len(loaded)} tributes.")
        except Exception as e:
            print(f"Error loading: {e}")
        input("Press Enter...")

    def save_current_roster(self):
        if not self.roster: return
        name = input("Enter name for this roster preset: ")
        serialiser.save_tributes_preset(self.roster, name)
        print(f"✅ Saved to {name}.json")
        input("Press Enter...")

    # ==========================
    # TERRAIN MANAGEMENT
    # ==========================
    def menu_terrain(self):
        while True:
            self.clear_screen()
            print("==========================================")
            print("🌍 TERRAIN MANAGEMENT")
            if self.terrain:
                print(f"Current: {self.terrain.name}")
            print("==========================================")
            print("1. Create New Terrain")
            print("2. Load Terrain from File")
            print("3. View/Edit Current Terrain")
            print("4. Save Current Terrain")
            print("B. Back")
            print("------------------------------------------")
            
            c = input("Choice: ").upper()
            if c == '1': self.create_terrain_wizard()
            elif c == '2': self.load_terrain_file()
            elif c == '3': self.edit_terrain_interactive()
            elif c == '4': self.save_current_terrain()
            elif c == 'B': break

    def create_terrain_wizard(self):
        print("\n--- Create Terrain ---")
        name = input("Arena Name: ")
        
        print("Set Multipliers (1.0 is normal, 2.0 is double chance, 0.0 is never)")
        mults = {}
        for tag in ["forest", "water", "combat", "scavenge", "cold", "fire"]:
            val = input(f"{tag.capitalize()} multiplier [1.0]: ")
            if val:
                mults[tag] = float(val)
        
        print("Note: Items will be randomized based on seed.")
        self.terrain = Terrain(name, mults, finite_items=[], infinite_items=[])
        print("✅ Terrain Configured.")
        input("Press Enter...")

    def edit_terrain_interactive(self):
        if not self.terrain:
            print("No terrain loaded.")
            input("Press Enter...")
            return

        while True:
            self.clear_screen()
            print(f"🌍 EDITING TERRAIN: {self.terrain.name}")
            
            w_tag, w_mult = 20, 10
            header = f"{self._fmt_cell('Tag', w_tag)} | {self._fmt_cell('Multiplier', w_mult)}"
            print("-" * len(header))
            print(header)
            print("-" * len(header))
            
            # Show standard tags + any custom ones
            tags = set(["forest", "water", "combat", "scavenge", "cold", "fire", "night"])
            tags.update(self.terrain.tag_multipliers.keys())
            
            for tag in sorted(list(tags)):
                val = self.terrain.tag_multipliers.get(tag, 1.0)
                print(f"{self._fmt_cell(tag, w_tag)} | {self._fmt_cell(val, w_mult)}")
            
            print("-" * len(header))
            print("1. Rename Arena")
            print("2. Edit Multiplier")
            print("3. Clear Item Pools (Force Re-roll on sim)")
            print("B. Back")
            
            c = input("Choice: ").upper()
            if c == '1':
                self.terrain.name = input("New Name: ")
            elif c == '2':
                tag = input("Enter tag name (e.g. water): ").lower()
                try:
                    val = float(input("Enter multiplier (e.g. 1.5): "))
                    self.terrain.tag_multipliers[tag] = val
                except:
                    print("Invalid number.")
                    input("...")
            elif c == '3':
                self.terrain.finite_items = []
                self.terrain.infinite_items = []
                print("Item pools cleared. They will be regenerated based on Seed when Sim runs.")
                input("...")
            elif c == 'B':
                break

    def load_terrain_file(self):
        files = [f for f in os.listdir(serialiser.TERRAINS_DIR) if f.endswith('.json')]
        if not files:
            print("No saved terrains found.")
            input("Press Enter...")
            return

        print("\nAvailable Terrains:")
        for idx, f in enumerate(files):
            print(f"{idx+1}. {f}")
        
        try:
            sel = int(input("Select file number: ")) - 1
            path = os.path.join(serialiser.TERRAINS_DIR, files[sel])
            self.terrain = serialiser.load_terrain_from_json(path)
            assert self.terrain is not None, "Failed to load terrain."
            print(f"✅ Loaded {self.terrain.name}.")
        except Exception as e:
            print(f"Error: {e}")
        input("Press Enter...")

    def save_current_terrain(self):
        if not self.terrain: return
        name = input("Enter filename for this terrain: ")
        serialiser.save_terrain_preset(self.terrain, name)
        print("✅ Terrain saved.")
        input("Press Enter...")

    # ==========================
    # SIMULATION
    # ==========================
    def menu_seed(self):
        val = input("Enter Seed (leave blank for random): ")
        if val:
            try:
                self.seed = int(val)
            except:
                print("Invalid seed. Using random...")
                self.seed = random.randint(1, 999999)
        else:
            self.seed = random.randint(1, 999999)
        print(f"Seed set to: {self.seed}")

    def run_simulation(self):
        if not self.roster or not self.terrain:
            print("❌ Error: You need both a Roster and Terrain to run.")
            input("Press Enter...")
            return

        if not self.seed:
            self.seed = random.randint(1, 999999)

        # Important: Set seed before engine/terrain init finalization
        random.seed(self.seed)

        print(f"\n🚀 STARTING SIMULATION [Seed: {self.seed}]...")
        
        # Re-initialize terrain if it relies on random generation to ensure seed applies
        sim_terrain = Terrain(
            self.terrain.name, 
            self.terrain.tag_multipliers, 
            finite_items=[],   
            infinite_items=[]  
        )

        # Clone Roster to avoid modifying the master list in menu
        sim_roster = [Tribute.from_dict(t.to_dict()) for t in self.roster]

        self.engine = GameEngine(sim_roster, sim_terrain, rng_seed=self.seed)
        self.last_result = self.engine.simulate()
        
        print(f"\n🏆 WINNER: {self.last_result['meta']['winner']}")
        
        # Options
        while True:
            print("\n[POST GAME]")
            print("1. View Summary")
            print("2. Save Replay Package (Loadable Game State)")
            print("3. Save Text Report (Readable Breakdown)")
            print("4. Return to Menu")
            
            c = input("Choice: ")
            if c == '1': self.view_summary()
            elif c == '2': self.save_replay()
            elif c == '3': self.save_text_report()
            elif c == '4': break

    def view_summary(self):
        if not self.last_result or not self.engine: return
        
        winner_name = self.last_result['meta']['winner']
        winner_obj = next((t for t in self.engine.tributes if t.name == winner_name), None)
        
        print("\n--- 🏆 GAME SUMMARY ---")
        print(f"Winner:      {winner_name}")
        if winner_obj:
            print(f"Kills:       {len(winner_obj.kills)}")
            inv_str = ", ".join([i.name for i in winner_obj.inventory]) if winner_obj.inventory else "None"
            print(f"End Items:   {inv_str}")
        print(f"Duration:    {self.last_result.get('total_days', 'N/A')} Days")
        input("...")

    def save_replay(self):
        if not self.roster or not self.terrain: return
        gid = serialiser.create_replay_package(self.roster, self.terrain, str(self.seed))
        print(f"✅ Game saved with ID: {gid}")
        print(f"File: saves/{gid}.json")
        input("...")

    def load_replay(self):
        files = [f for f in os.listdir(serialiser.SAVES_DIR) if f.endswith('.json')]
        if not files:
            print("No saves found.")
            input("...")
            return

        print("\nSaved Games:")
        for idx, f in enumerate(files):
            print(f"{idx+1}. {f}")
        
        try:
            sel = int(input("Select save: ")) - 1
            game_id = files[sel].replace(".json", "")
            data = serialiser.load_replay_package(game_id)
            
            if data:
                self.seed = data['meta']['seed']
                self.terrain = Terrain.from_dict(data['terrain'])
                
                # Load tributes
                raw_tributes = data.get('tributes', [])
                self.roster = [Tribute.from_dict(t) for t in raw_tributes]
                
                print(f"✅ Replay Loaded: {game_id}")
                print("You can now Run Simulation to see the exact same outcome.")
        except Exception as e:
            print(f"Error loading replay: {e}")
        input("...")

    def save_text_report(self):
        if not self.last_result: return
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reports/report_{timestamp}.txt"
        os.makedirs("reports", exist_ok=True)
        
        with open(filename, "w", encoding="utf-8") as f:
            # 1. HEADER
            f.write(f"GAME REPORT | Seed: {self.seed} | Winner: {self.last_result['meta']['winner']}\n")
            f.write("="*60 + "\n\n")
            
            # 2. DAY BY DAY
            f.write("--- 📜 DAY BY DAY LOG ---\n")
            
            icon_map = {
                # --- CORE & STATUS ---
                'combat':    "⚔️ ", 
                'death':     "💀 ", 
                'gamemaker': "📢 ", 
                'idle':      "⏳ ",
                'training':  "🎯 ",
                
                # --- ACTIONS ---
                'scavenge':  "🎒 ", 
                'crafting':  "🔨 ", 
                'stealth':   "🥷 ",
                'intel':     "🧠 ",
                'trap':      "🪤 ",
                'sabotage':  "🧨 ",
                'camp':      "⛺ ",
                
                # --- INTERACTIONS ---
                'social':    "💬 ", 
                'trade':     "⚖️ ",
                'romance':   "❤️ ",
                'betrayal':  "🔪 ",
                'conflict':  "😠 ",
                'funny':     "😆 ",
                'sad':       "😢 ",
                
                # --- HEALTH / MEDICAL ---
                'medical':   "💊 ", 
                'accident':  "🤕 ",
                'mental':    "😵 ",
                'sponsor':   "� ",
                
                # --- ENVIRONMENT ---
                'forest':    "�🌲 ", 
                'water':     "💧 ", 
                'weather':   "⛈️ ",
                'cold':      "❄️ ",
                'fire':      "🔥 ",
                'night':     "🌙 ",
                'pve':       "🐺 ",
                'dangerous': "⚠️ ",
                'disaster':  "🌪️ "
            }

            for day in self.last_result['timeline']:
                header = day.get('day_name', f"DAY {day['day_number']}")
                f.write(f"\n[{header}]\n")
                
                for event in day['events']:
                    icon = icon_map.get(event['type'], "• ")
                    f.write(f"  {icon} {event['text']}\n")
                    
                if day['deaths_today']:
                    f.write(f"  💀 DEAD: {', '.join(day['deaths_today'])}\n")
                
                # Alliance Breakdown (No HP)
                if "alliance_snapshot" in day:
                    f.write(f"  📊 ALLIANCE STATUS:\n")
                    for idx, group in enumerate(day["alliance_snapshot"]):
                        members_str = [f"{m['name']} {([{', '.join(m['inventory'])}]) if m['inventory'] else ''}" for m in group["members"]]
                        # We specifically DO NOT show health here as requested
                        shared_str = f" | Shared: {', '.join(group['shared_inventory'])}" if group['shared_inventory'] else ""
                        f.write(f"    Group {idx+1}: {', '.join(members_str)}{shared_str}\n")

            # 3. BREAKDOWN SECTION
            f.write("\n" + "="*60 + "\n")
            f.write("📊 GAME BREAKDOWN\n")
            f.write("="*60 + "\n")

            # Kill Log
            f.write("\n--- 🔪 KILL LOG ---\n")
            has_kills = False
            for t in self.engine.tributes:
                if t.kills:
                    has_kills = True
                    f.write(f"{self._fmt_cell(t.name, 25)} killed: {', '.join(t.kills)}\n")
            if not has_kills: f.write("No kills recorded.\n")

            # Alliance History (Filtered from Events)
            f.write("\n--- 🤝 ALLIANCE HISTORY ---\n")
            social_events = ["Form Alliance", "Disband", "Betrayal", "Defection"]
            for day in self.last_result['timeline']:
                for e in day['events']:
                    # We check if the event ID (e.g., 'Form Alliance') matches our interest
                    if e.get('id') in social_events or e.get('type') == 'betrayal':
                        f.write(f"Day {day['day_number']}: {e['text']}\n")

            # Event Frequency
            tag_counts = Counter()
            id_counts = Counter()
            
            for day in self.last_result['timeline']:
                for e in day['events']:
                    tag_counts[e.get('type', 'misc')] += 1
                    eid = e.get('id')
                    if eid: id_counts[eid] += 1
            
            f.write("\n--- 🏷️ EVENT FREQUENCY (Tags) ---\n")
            for tag, count in tag_counts.most_common():
                f.write(f"{self._fmt_cell(tag, 25)} : {count}\n")

            f.write("\n--- 🌍 EVENT FREQUENCY (IDs) ---\n")
            for eid, count in id_counts.most_common():
                f.write(f"{self._fmt_cell(eid, 35)} : {count}\n")

        print(f"✅ Report written to {filename}")
        input("...")

if __name__ == "__main__":
    gm = GameManager()
    gm.main_menu()