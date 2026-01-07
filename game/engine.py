import random
from .models import Tribute, Alliance, Item, Terrain, format_tribute_list
from .events import EventManager, ForceSplitEvent, ExtinctionPreventionEvent, BloodbathEvent, FeastEvent
from typing import Optional, Union, Any 

class GameEngine:
    # --- MASTER ITEM LIBRARY ---
    ITEM_LIBRARY = [
        # -- Weapons (Melee) --
        {"item": Item("Sword", "weapon", {"strength": 3}), "qty": 2},
        {"item": Item("Mace", "weapon", {"strength": 5, "speed": -2}), "qty": 1},
        {"item": Item("Sickle", "weapon", {"strength": 3, "speed": 1}), "qty": 1},
        {"item": Item("Sais", "weapon", {"strength": 2, "speed": 3, "defense": 1}), "qty": 1},
        {"item": Item("Hatchet", "weapon", {"strength": 3}), "qty": 2},
        {"item": Item("Trident", "weapon", {"strength": 4, "speed": 1}), "qty": 1},
        {"item": Item("Axe", "weapon", {"strength": 4, "speed": -1}), "qty": 1},
        {"item": Item("Knife", "weapon", {"strength": 1, "speed": 3, "stealth": 1}), "qty": None}, 
        
        # -- Weapons (Ranged/Special) --
        {"item": Item("Bow", "weapon", {"strength": 2, "speed": 2}), "qty": 1},
        {"item": Item("Slingshot", "weapon", {"strength": 1, "speed": 2}), "qty": None},
        {"item": Item("Blow Dart", "weapon", {"strength": 1, "stealth": 4}), "qty": 1},
        {"item": Item("Explosive", "weapon", {"strength": 10, "aggression": 2}), "qty": 1},
        {"item": Item("Land Mine", "weapon", {"strength": 10, "stealth": 5}), "qty": 1},
        {"item": Item("Molotov", "weapon", {"strength": 6, "aggression": 3}), "qty": 2},
        {"item": Item("Wooden Spear", "weapon", {"strength": 2, "speed": 1}), "qty": None},

        # -- Survival / Food --
        {"item": Item("Apple", "food", {"health": 5}), "qty": None},
        {"item": Item("Fruit", "food", {"health": 5}), "qty": None},
        {"item": Item("Bread", "food", {"health": 10}), "qty": None},
        {"item": Item("Fresh Food", "food", {"health": 15}), "qty": 5},
        {"item": Item("Water", "food", {"health": 5, "speed": 1}), "qty": None},
        {"item": Item("Clean Water", "food", {"health": 10, "speed": 1}), "qty": 5},
        
        # -- Medical --
        {"item": Item("Medkit", "medical", {"health": 20}), "qty": 5},
        {"item": Item("Medical Supplies", "medical", {"health": 25, "injured": -1}), "qty": 3},
        {"item": Item("Bandages", "medical", {"health": 10}), "qty": None},
        
        # -- Gear / Misc --
        {"item": Item("Camo Paint", "misc", {"stealth": 3}), "qty": None},
        {"item": Item("Night Vision", "misc", {"stealth": 1, "intel": 2}), "qty": 1},
        {"item": Item("Rope", "misc", {"speed": 1}), "qty": None},
        {"item": Item("Fishing Gear", "misc", {"intel": 1}), "qty": 1}
    ]

    def __init__(self, roster_data: Union[list[dict[str, Any]],list[Tribute]], terrain_config: Union[dict[str, Any], Terrain], rng_seed: int) -> None:
        """
        roster_data: List of dicts (from serialized JSON)
        terrain_config: Dict (from serialized JSON)
        rng_seed: Integer
        """
        # 1. Setup Randomness
        self.seed = rng_seed
        random.seed(self.seed)
        
        # 2. Initialize Roster
        from .models import Tribute, Terrain # Local import to avoid circular dep
        
        self.tributes = []
        # Handle both raw dicts or existing Objects
        raw_list = roster_data if isinstance(roster_data, list) else []
        for t_data in raw_list:
            if isinstance(t_data, dict):
                self.tributes.append(Tribute.from_dict(t_data))
            else:
                self.tributes.append(t_data)

        # 3. Initialize Terrain
        if isinstance(terrain_config, dict):
            self.terrain = Terrain.from_dict(terrain_config)
        else:
            self.terrain = terrain_config

        # 4. Initialize Systems
        self.event_manager = EventManager()

        # 5. RESOLVE ITEMS
        # This converts any strings in the terrain lists into actual Item objects
        self._resolve_terrain_items()

        # 6. Initialize Item Pool (If empty)
        if not self.terrain.finite_items and not self.terrain.infinite_items:
            self._init_default_pool()
        
        # 7. Inject Missing Proficiencies
        self._inject_proficiencies()

        # 8. Game State & Alliances
        self.day = -1
        
        # Tracking for Feast
        self.initial_tribute_count = len(self.tributes)
        self.feast_happened = False
        
        self.game_log = {
            "meta": {"seed": self.seed, "winner": None},
            "timeline": []
        }
        self.alliances = [Alliance([t]) for t in self.tributes]
        self.pending_new_alliances = [] 

    def _resolve_terrain_items(self) -> None:
        """
        Scans Terrain item lists. If it finds a string, it replaces it 
        with a fresh Item object from the Master Library.
        If the string isn't in the library, it creates a generic Item.
        """
        # Create a lookup map for fast access
        lookup = {entry["item"].name: entry["item"] for entry in self.ITEM_LIBRARY}

        def resolve_list(item_list):
            resolved = []
            for entry in item_list:
                if isinstance(entry, Item):
                    # Already an object, keep it
                    resolved.append(entry)
                elif isinstance(entry, str):
                    # It's a name, look it up
                    if entry in lookup:
                        # Clone the prototype
                        proto = lookup[entry]
                        resolved.append(Item(proto.name, proto.kind, proto.bonuses))
                    else:
                        # Unknown item, create generic
                        print(f"[Engine] Warning: Resolving unknown item '{entry}' as generic.")
                        resolved.append(Item(entry, "misc"))
            return resolved

        self.terrain.finite_items = resolve_list(self.terrain.finite_items)
        self.terrain.infinite_items = resolve_list(self.terrain.infinite_items)

    def _init_default_pool(self) -> None:
        """
        Populates the Terrain with defaults from the Master Library if the terrain was empty.
        """
        for entry in self.ITEM_LIBRARY:
            proto = entry["item"]
            qty = entry["qty"]
            
            if qty is None:
                self.terrain.infinite_items.append(Item(proto.name, proto.kind, proto.bonuses))
            else:
                for _ in range(qty):
                    # Create distinct objects for finite items
                    self.terrain.finite_items.append(Item(proto.name, proto.kind, proto.bonuses))

    def _inject_proficiencies(self) -> None:
        """
        Ensures that if a tribute needs a specific item, it exists in the game.
        """
        lookup = {entry["item"].name: entry["item"] for entry in self.ITEM_LIBRARY}
        
        # 1. Identify all unique items needed by current tributes
        needed_items = set()
        for t in self.tributes:
            for p_item in t.proficient_items:
                needed_items.add(p_item)

        # 2. Check existence
        for item_name in sorted(list(needed_items)):
            # Check Infinite
            if any(isinstance(i, Item) and((i.name == item_name)) for i in self.terrain.infinite_items):
                continue
            
            # Check Finite
            if any(isinstance(i, Item) and((i.name == item_name)) for i in self.terrain.finite_items):
                continue

            # Inject
            if item_name in lookup:
                print(f"[GameMaker] Injecting 1x {item_name} for proficiency balance.")
                proto = lookup[item_name]
                self.terrain.finite_items.append(Item(proto.name, proto.kind, proto.bonuses))
            else:
                print(f"[GameMaker] Tribute proficient in '{item_name}' (Unknown). Creating generic version.")
                self.terrain.finite_items.append(Item(item_name, "weapon", {"strength": 2}))

    def get_alive_tributes(self) -> list[Tribute]:
        return [t for t in self.tributes if t.alive]

    def simulate(self) -> dict[str, Any]:
        """
        Runs the entire game until one winner remains.
        Returns: The full game_log dictionary.
        """
        while len(self.get_alive_tributes()) > 1:
            self.day += 1
            self.run_day()
            
            # Safety break for infinite loops
            if self.day > 50:
                self._resolve_sudden_death()
                break

        # Determine Winner
        survivors = self.get_alive_tributes()
        if len(survivors) >= 1: self.game_log["meta"]["winner"] = survivors[0].name
        else: self.game_log["meta"]["winner"] = "Nobody"
        return self.game_log

    def _resolve_sudden_death(self) -> None:
        survivors = self.get_alive_tributes()
        if len(survivors) <= 1: return
        winner = random.choice(survivors)
        day_log = { "day_number": self.day, "day_name": "SUDDEN DEATH", "events": [], "deaths_today": [], "alliance_snapshot": [] }
        for t in survivors:
            if t != winner:
                t.alive = False
                t.health = 0
                day_log["deaths_today"].append(t.name)
                day_log["events"].append({
                    "text": f"The Gamemakers trigger a localized disaster. {t.name} is consumed.",
                    "type": "gamemaker",
                    "tributes_involved": [t.name],
                    "image": t.image_url
                })
        day_log["events"].append({
            "text": f"{winner.name} is the only survivor of the disaster!",
            "type": "gamemaker",
            "tributes_involved": [winner.name],
            "image": winner.image_url
        })
        self.game_log["timeline"].append(day_log)

    def run_day(self) -> None:
        """
        Processes one in-game day.
        """
        day_log = {
            "day_number": self.day,
            "events": [],
            "deaths_today": [],
            "alliance_snapshot": [] 
        }
        
        # 1. Shuffle execution order
        random.shuffle(self.alliances)
        
        # 2. Iterate through Groups
        # We copy the list because self.alliances might change during the loop (disbands/merges)
        current_groups = list(self.alliances)
        processed_tributes = set() # Track who has acted to prevent double turns
        
        # --- SPECIAL EVENTS ---
        forced_event_class = None
        
        # 1. Bloodbath (Day 0)
        if self.day == 0:
            day_log["day_name"] = 'THE BLOODBATH'
            forced_event_class = BloodbathEvent
            # Optional: Log the start of bloodbath
            day_log["events"].append({
                "text": "The Tributes stand on their podiums, the horn sounds. The Bloodbath begins!",
                "type": "gamemaker",
                "tributes_involved": [],
                "image": None
            })
            
        # 2. Feast (Population drops to a quarter, e.g. 25% remaining)
        # Check if we hit the threshold
        elif not self.feast_happened:
            current_pop = len(self.get_alive_tributes())
            threshold = int(self.initial_tribute_count * 0.25)
            
            if current_pop <= threshold:
                day_log["day_name"] = 'THE FEAST'
                forced_event_class = FeastEvent
                self.feast_happened = True
                day_log["events"].append({
                    "text": "The Gamemakers announce a Feast at the Cornucopia! A chance for precious supplies.",
                    "type": "gamemaker",
                    "tributes_involved": [],
                    "image": None
                })
        
        for alliance in current_groups:
            # Skip if group was dissolved/merged by a previous event this turn
            if not alliance.is_active:
                continue
                
            # Skip if any member already acted
            if any(t.name in processed_tributes for t in alliance.members):
                continue

            # Mark them as processed
            for t in alliance.members:
                processed_tributes.add(t.name)

            # We capture the names because the event might chnage the group state
            snapshot_members = list(alliance.members)
            snapshot_names = [t.name for t in snapshot_members]
            leader_image = snapshot_members[0].image_url if snapshot_members else None

            # --- THE CORE EVENT TRIGGER ---
            if forced_event_class:
                # Force the special event logic
                event = forced_event_class()
            else:
                # Standard Logic
                event = self.event_manager.select_event(alliance, self.terrain, self.day)
            
            if event:
                # Execution might clear alliance.members (e.g. FormAlliance)
                text = event.execute(alliance, self.terrain, game_engine_ref=self)
                
                # Log the event using the SNAPSHOT data
                day_log["events"].append({
                    "text": text,
                    "type": event.tags[0] if event.tags else "misc",
                    "tributes_involved": snapshot_names, 
                    "image": leader_image # Display leader's face
                })
            else:
                # Fallback if no event matches (rare)
                day_log["events"].append({
                    "text": f"{format_tribute_list(snapshot_members)} {'sleeps' if len(snapshot_members) == 1 else 'sleep'} through the day.",
                    "type": "idle",
                    "tributes_involved": snapshot_names,
                    "image": leader_image
                })

        # 3. Process Alliance Changes
        self._update_alliances()

        # Consolidate Solo Inventories
        for alliance in self.alliances:
            if len(alliance.members) == 1 and hasattr(alliance, 'shared_inventory') and alliance.shared_inventory:
                member = alliance.members[0]
                member.inventory.extend(alliance.shared_inventory)
                alliance.shared_inventory = []

        # Force Split
        if len(self.alliances) == 1 and len(self.alliances[0].members) > 1:
            target_alliance = self.alliances[0]
            member_names = [t.name for t in target_alliance.members]
            
            event = ForceSplitEvent()
            text = event.execute(target_alliance, self.terrain, game_engine_ref=self)
            
            day_log["events"].append({
                "text": text,
                "type": "gamemaker",
                "tributes_involved": member_names,
                "image": None
            })

        # Extinction Check
        alive_now = self.get_alive_tributes()
        if not alive_now:
            event = ExtinctionPreventionEvent()
            text = event.execute(Alliance([]), self.terrain, game_engine_ref=self)
            
            # Determine who was revived to log correctly
            survivors = self.get_alive_tributes()
            involved = [s.name for s in survivors]
            img = survivors[0].image_url if survivors else None
            day_log["events"].append({ "text": text, "type": "gamemaker", "tributes_involved": involved, "image": img })

        # Process Status Effects
        # This handles chronic "bleeding out" over time
        for t in self.tributes:
            if not t.alive: continue
            
            # Poison Logic
            if t.poisoned:
                t.change_health(-14) # Heavy DOT
                if not t.alive:
                    day_log["events"].append({
                        "text": f"{t.name} succumbs to the poison coursing through their veins.",
                        "type": "death",
                        "tributes_involved": [t.name],
                        "image": t.image_url
                    })
            
            # Injury Logic (Bleeding)
            if t.alive and t.injured:
                t.change_health(-7) # Standard DOT
                if not t.alive:
                    day_log["events"].append({
                        "text": f"{t.name}'s untreated wounds prove fatal. They bleed out.",
                        "type": "death",
                        "tributes_involved": [t.name],
                        "image": t.image_url
                    })

        # 4. Tally Deaths
        alive_now = self.get_alive_tributes()
        dead_this_turn = [t.name for t in self.tributes if not t.alive and t.name not in self._get_previously_dead()]
        day_log["deaths_today"] = dead_this_turn
        
        # 5. Snapshot
        snapshot = []
        for alliance in self.alliances:
            if not alliance.is_active: continue
            
            group_data = {
                "members": [],
                "shared_inventory": [i.name for i in getattr(alliance, 'shared_inventory', [])]
            }
            
            for t in alliance.members:
                # Gather detailed info per member
                member_status = []
                if t.injured: member_status.append("Injured")
                if t.poisoned: member_status.append("Poisoned")
                
                member_data = {
                    "name": t.name,
                    "health": round(t.health, 1),
                    "inventory": [i.name for i in t.inventory],
                    "status_effects": member_status
                }
                group_data["members"].append(member_data)
            
            snapshot.append(group_data)
        
        day_log["alliance_snapshot"] = snapshot
        
        self.game_log["timeline"].append(day_log)

    def _update_alliances(self) -> None:
        """
        Clean up empty alliances and add newly formed ones.
        """
        # 1. Remove groups where everyone is dead
        self.alliances = [a for a in self.alliances if a.is_active]
        
        # 2. Add new groups formed by Disband/Merge events
        if self.pending_new_alliances:
            self.alliances.extend(self.pending_new_alliances)
            self.pending_new_alliances = []

    def _get_previously_dead(self) -> list[str]:
        """Helper to find who was already dead before today."""
        # Look at previous days in timeline
        dead = []
        for day in self.game_log["timeline"]:
            dead.extend(day["deaths_today"])
        return dead