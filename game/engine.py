import json
import os
import random
from .models import Tribute, Alliance, Item, Terrain
from .events import *
from typing import Optional, Union, Any 
from .utils import format_tribute_list

class GameEngine:
    def __init__(self, roster_data: Union[list[dict[str, Any]],list[Tribute]], terrain_config: Union[dict[str, Any], Terrain], rng_seed: int) -> None:
        """
        roster_data: List of dicts (from serialized JSON)
        terrain_config: Dict (from serialized JSON)
        rng_seed: Integer
        """
        # 1. Setup Randomness
        self.seed = rng_seed
        random.seed(self.seed)
        
        # 2. Initialize Item Library
        self.ITEM_LIBRARY = self._load_item_library()

        # 3. Initialize Roster 
        from .models import Tribute, Terrain # Local import to avoid circular dep
        
        self.tributes = []
        # Handle both raw dicts or existing Objects
        raw_list = roster_data if isinstance(roster_data, list) else []
        for t_data in raw_list:
            if isinstance(t_data, dict):
                self.tributes.append(Tribute.from_dict(t_data))
            else:
                self.tributes.append(t_data)

        # 4. Initialize Terrain
        if isinstance(terrain_config, dict):
            self.terrain = Terrain.from_dict(terrain_config)
        else:
            self.terrain = terrain_config

        # 5. Initialize Systems
        self.event_manager = EventManager()

        # 6. RESOLVE ITEMS
        # This converts any strings in the terrain lists into actual Item objects
        self._resolve_terrain_items()

        # 7. Initialize Item Pool (If empty)
        if not self.terrain.finite_items and not self.terrain.infinite_items:
            self._init_default_pool()
        
        # 8. Inject Missing Proficiencies
        self._inject_proficiencies()

        # 9. Game State & Alliances
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

    def _load_item_library(self):
        """Loads master item list from JSON."""
        path = os.path.join(os.path.dirname(__file__), 'data', 'items.json')
        # Fallback or create generic if missing, otherwise load:
        with open(path, 'r') as f:
            data = json.load(f)
        # Convert dicts to objects immediately for easier handling
        return [{"item": Item(d['name'], d['kind'], d.get('bonuses')), "qty": d.get('qty')} for d in data]

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
                proto = lookup[item_name]
                self.terrain.finite_items.append(Item(proto.name, proto.kind, proto.bonuses))
            else:
                self.terrain.finite_items.append(Item(item_name, "weapon", {"strength": 2}))

    def get_alive_tributes(self) -> list[Tribute]:
        return [t for t in self.tributes if t.alive]

    def _resolve_sudden_death(self) -> None:
        survivors = self.get_alive_tributes()
        if len(survivors) <= 1: return
        winner = random.choice(survivors)
        self.current_day_log = { "day_number": self.day, "day_name": "SUDDEN DEATH", "events": [], "deaths_today": [], "alliance_snapshot": [] }
        victims = []
        for t in survivors:
            if t != winner:
                t.alive = False
                t.health = 0
                victims.append(t)
        self.current_day_log["deaths_today"] = [t.name for t in victims]
        self._log_event(
            text=f"The Gamemakers trigger a localized disaster. {format_tribute_list(victims)} {'is' if len(victims) == 1 else 'are'} consumed.",
            type_tag="gamemaker",
            tributes=[t.name for t in victims],
            image_url=None
        )
        self._log_event(
            text=f"{winner.name} is the only survivor of the disaster!",
            type_tag="gamemaker",
            tributes=[winner.name],
            image_url=winner.image_url
        )
        self.game_log["timeline"].append(self.current_day_log)
    
    def simulate(self) -> dict[str, Any]:
        """
        Runs the entire game until one winner remains.
        Returns: The full game_log dictionary.
        """
        while len(self.get_alive_tributes()) > 1:
            self.day += 1
            self.run_day()
            
            # Safety break for infinite loops
            if self.day > 59:
                self._resolve_sudden_death()
                break

        # Determine Winner
        survivors = self.get_alive_tributes()
        if len(survivors) >= 1: self.game_log["meta"]["winner"] = survivors[0].name
        else: self.game_log["meta"]["winner"] = "Nobody"
        self.game_log["total_days"] = self.day
        
        return self.game_log

    def _perform_self_care(self) -> None:
        """
        Allows tributes to automatically use items from inventory to heal statuses
        (Injury, Poison, Low Health) before starting the day.
        """
        for alliance in self.alliances:
            if not alliance.is_active: continue
            
            for tribute in alliance.members:
                if not tribute.alive: continue
                
                # Identify Critical Needs
                needs_injury_cure = tribute.injured
                needs_poison_cure = tribute.poisoned
                needs_healing = tribute.health < 40 
                
                if not (needs_injury_cure or needs_poison_cure or needs_healing):
                    continue
                    
                # Search Inventories (Personal First, then Shared)
                inventories = [(tribute.inventory, "personal")]
                inventories.append((alliance.shared_inventory, "shared"))
                    
                item_used = None
                source_list = []
                action = ""
                
                for inv, src_type in inventories:
                    if item_used: break
                    
                    # Iterate through a copy to allow modification if needed (though we break immediately)
                    for item in inv:
                        # 1. Cure Injury (Priority)
                        if needs_injury_cure and item.bonuses.get('injured', 0) < 0:
                            item_used = item
                            source_list = inv
                            tribute.injured = False
                            action = "treats their wounds"
                            break
                        
                        # 2. Cure Poison (Priority)
                        if needs_poison_cure and item.bonuses.get('poisoned', 0) < 0:
                            item_used = item
                            source_list = inv
                            tribute.poisoned = False
                            action = "cures their poisoning"
                            break
                            
                        # 3. Heal Health (Only if item actually heals)
                        if needs_healing and item.bonuses.get('health', 0) >= 5:
                            item_used = item
                            source_list = inv
                            heal_amt = item.bonuses.get('health', 0)
                            tribute.health = min(tribute.max_health, tribute.health + heal_amt)
                            action = f"heals up"
                            break
                
                if item_used:
                    # Consume item
                    source_list.remove(item_used)
                    
                    # Log the smart decision
                    self.current_day_log["events"].append({
                        "text": f"{tribute.name} uses {item_used.name} and {action}.",
                        "type": "medical",
                        "tributes_involved": [tribute.name],
                        "image": tribute.image_url
                    })

    def _start_new_day_log(self):
        self.current_day_log = {
            "day_number": self.day,
            "day_name": f"DAY {self.day}",
            "events": [],
            "deaths_today": [],
            "alliance_snapshot": []
        }
    
    def _get_daily_forced_event(self) -> Optional["SpecialEvent"]:
        """Checks specific day conditions to see if a special event overrides normal logic."""
        # Check Bloodbath Condition (Day 0)
        if self.day == 0:
            self.current_day_log["day_name"] = 'THE BLOODBATH'
            self._log_event(
                text="The Tributes stand on their podiums. The horn sounds!", 
                type_tag="gamemaker"
            )
            return BloodbathEvent()
            
        # Check Feast Condition (e.g. < 25% pop)
        if not self.feast_happened and len(self.get_alive_tributes()) <= (self.initial_tribute_count * 0.25):
            self.feast_happened = True
            self.current_day_log["day_name"] = 'THE FEAST'
            self._log_event(
                text="The Gamemakers announce a Feast!", 
                type_tag="gamemaker"
            )
            return FeastEvent()
            
        return None

    def _execute_alliance_turns(self, forced_event: Optional[SpecialEvent]) -> None:
        """Iterates through alliances and triggers their actions."""
        # Copy list to safely modify alliances during iteration (merges/splits)
        active_groups = list(self.alliances)
        processed_tributes = set()

        for alliance in active_groups:
            if not alliance.is_active: continue
            
            # Prevent double-moves if an alliance merged/split this turn
            if any(t.name in processed_tributes for t in alliance.members): continue
            
            # Mark these tributes as 'acted'
            for t in alliance.members: processed_tributes.add(t.name)

            # Select and Execute
            if forced_event:
                event = forced_event
            else:
                event = self.event_manager.select_event(alliance, self.terrain, self.day)

            # Run the event logic
            if event:
                self._run_and_log_event(event, alliance)
            else:
                self._log_event(
                    text = f"{format_tribute_list(alliance.members)} {'sleeps' if len(alliance.members) == 1 else 'sleep'} through the day.",
                    type_tag = "idle",
                    tributes = [m.name for m in alliance.members],
                    image_url = alliance.members[0].image_url if alliance.members else None
                )

    def _run_and_log_event(self, event: GameEvent, alliance: Alliance):
        # Capture snapshot of who is involved BEFORE the event potentially changes the group
        participants = [t.name for t in alliance.members]
        leader_img = alliance.members[0].image_url if alliance.members else None
        
        text = event.execute(alliance, self.terrain, game_engine_ref=self)
        
        self._log_event(
            text=text or "",
            type_tag=event.tags[0] if event.tags else "misc",
            tributes=participants,
            image_url=leader_img
        )
    
    def _process_status_effects(self):
        """Applies damage from Poison, Wounds, etc."""
        for t in self.tributes:
            if not t.alive: continue
            
            if t.poisoned:
                t.change_health(-14)
                if not t.alive: self._log_event(
                    text=f"{t.name} succumbs to the poison coursing through their veins.",
                    type_tag="death",
                    tributes=[t.name],
                    image_url=t.image_url
                )

            elif t.injured:
                t.change_health(-7)
                if not t.alive: self._log_event(
                    text=f"{t.name}'s untreated wounds prove fatal. They bleed out.",
                    type_tag="death",
                    tributes=[t.name],
                    image_url=t.image_url
                )
    
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
        
        # 3. Consolidate items from single-member alliances
        for alliance in self.alliances:
            if len(alliance.members) == 1 and alliance.shared_inventory:
                member = alliance.members[0]
                member.inventory.extend(alliance.shared_inventory)
                alliance.shared_inventory = []

    def _resolve_gamemaker_events(self) -> None:
        """
        Checks for forced Gamemaker interventions like Force Split or 
        Extinction Prevention.
        """
        # 1. Force Split if too large
        if len(self.alliances) == 1 and len(self.alliances[0].members) > 1:
            target_alliance = self.alliances[0]
            
            event = ForceSplitEvent()
            self._run_and_log_event(event, target_alliance)
        
        # 2. Extinction Prevention
        if not self.get_alive_tributes():
            event = ExtinctionPreventionEvent()
            text = event.execute(Alliance([]), self.terrain, game_engine_ref=self)
            
            # Determine who was revived to log correctly
            survivors = self.get_alive_tributes()
            involved = [s.name for s in survivors]
            img = survivors[0].image_url if survivors else None
            self._log_event(
                text=text, 
                type_tag="gamemaker", 
                tributes=involved, 
                image_url=img
            )

    def _get_previously_dead(self) -> list[str]:
        """Helper to find who was already dead before today."""
        # Look at previous days in timeline
        dead = []
        for day in self.game_log["timeline"]:
            dead.extend(day["deaths_today"])
        return dead

    def _tally_deaths(self) -> None:
        """Counts and logs who died this turn."""
        dead_this_turn = [t.name for t in self.tributes if not t.alive and t.name not in self._get_previously_dead()]
        self.current_day_log["deaths_today"] = dead_this_turn

    def _log_event(self, text: str, type_tag: str, tributes: list[str]=[], image_url: Optional[str]=None) -> None:
        self.current_day_log["events"].append({
            "text": text,
            "type": type_tag,
            "tributes_involved": tributes,
            "image": image_url
        })

    def run_day(self) -> None:
        """
        Orchestrates a single day in the arena.
        """
        # 1. Initialization
        self._start_new_day_log()
        random.shuffle(self.alliances)

        # 2. Pre-Day Phases 
        self._perform_self_care()
        
        # 3. Determine if today is special (Bloodbath, Feast)
        forced_event_type = self._get_daily_forced_event()
        
        # 3. Execution Phase
        self._execute_alliance_turns(forced_event_type)

        # 4. Post-Day Phases
        self._process_status_effects()   # Poison / Bleeding
        self._update_alliances()         # Clean up alliances
        self._resolve_gamemaker_events() # Force Split / Extinction
        self._tally_deaths()             # Count who died today
        self._generate_snapshot()        # Save state for UI

        # 5. Commit to Timeline
        self.game_log["timeline"].append(self.current_day_log)

    def _generate_snapshot(self) -> None:
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
        
        self.current_day_log["alliance_snapshot"] = snapshot
    
    def create_item_from_name(self, item_name: str) -> "Item":
        """
        Creates a fresh Item object from a string name.
        1. Looks up the name in the master ITEM_LIBRARY.
        2. If found, returns a COPY of that item (so stats don't get messed up).
        3. If not found, returns a generic 'misc' item.
        """
        # 1. Search the Master Library
        for entry in self.ITEM_LIBRARY:
            proto = entry["item"]
            if proto.name == item_name:
                return Item(proto.name, proto.kind, proto.bonuses)
        
        # We return a generic item so the event can continue safely.
        return Item(item_name, "misc")