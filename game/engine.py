import random
from .models import Tribute, Alliance, Item, Terrain
from .events import EventManager
from typing import Optional, Union, Any 

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

        # 2. Initialize Objects
        # This safety check ensures we are working with Objects.
        from .models import Tribute, Terrain # Local import to avoid circular dep
        
        self.tributes = []
        for t_data in roster_data:
            if isinstance(t_data, dict):
                self.tributes.append(Tribute.from_dict(t_data))
            else:
                self.tributes.append(t_data)

        if isinstance(terrain_config, dict):
            self.terrain = Terrain.from_dict(terrain_config)
        else:
            self.terrain = terrain_config

        # 3. Game State
        self.day = 0
        self.game_log = {
            "meta": {"seed": self.seed, "winner": None},
            "timeline": []
        }
        
        # 4. Systems
        self.event_manager = EventManager()
        self.item_pool = self._init_item_pool()
        
        # 5. Alliance Management
        # Everyone starts in a solo alliance
        self.alliances = [Alliance([t]) for t in self.tributes]
        self.pending_new_alliances = [] # Queue for groups formed during turns

    def _init_item_pool(self) -> list[Item]:
        """Creates the default loot table."""
        return [
            Item("Apple", "food", {"health": 5}),
            Item("Sword", "weapon", {"strength": 2}),
            Item("Medkit", "medical", {"health": 20}),
            Item("Bow", "weapon", {"strength": 1, "speed": 1}),
            Item("Camo Paint", "misc", {"stealth": 3})
        ]

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
                break

        # Determine Winner
        survivors = self.get_alive_tributes()
        if survivors:
            self.game_log["meta"]["winner"] = survivors[0].name
        else:
            self.game_log["meta"]["winner"] = "Nobody (Everyone died)"

        return self.game_log

    def run_day(self) -> None:
        """
        Processes one in-game day.
        """
        day_log = {
            "day_number": self.day,
            "events": [],
            "deaths_today": []
        }
        
        # 1. Shuffle execution order so same people don't always go first
        random.shuffle(self.alliances)
        
        # 2. Iterate through Groups
        # We copy the list because self.alliances might change during the loop (disbands/merges)
        current_groups = list(self.alliances)
        processed_tributes = set() # Track who has acted to prevent double turns
        
        for alliance in current_groups:
            # Skip if group was dissolved/merged by a previous event this turn
            if not alliance.is_active:
                continue
                
            # Skip if any member already acted (merged into another group)
            if any(t.name in processed_tributes for t in alliance.members):
                continue

            # Mark them as processed
            for t in alliance.members:
                processed_tributes.add(t.name)

            # --- THE CORE EVENT TRIGGER ---
            event = self.event_manager.select_event(alliance, self.terrain)
            
            if event:
                text = event.execute(alliance, self.terrain, game_engine_ref=self)
                
                # Log the event
                day_log["events"].append({
                    "text": text,
                    "type": event.tags[0] if event.tags else "misc",
                    "tributes_involved": [t.name for t in alliance.members],
                    "image": alliance.members[0].image_url # Display leader's face
                })
            else:
                # Fallback if no event matches (rare)
                day_log["events"].append({
                    "text": f"{alliance.members[0].name} sleeps through the day.",
                    "type": "idle",
                    "tributes_involved": [t.name for t in alliance.members],
                    "image": alliance.members[0].image_url
                })

        # 3. Process Alliance Changes (Merges/Splits)
        self._update_alliances()

        # 4. Tally Deaths
        alive_now = self.get_alive_tributes()
        
        dead_this_turn = [t.name for t in self.tributes if not t.alive and t.name not in self._get_previously_dead()]
        day_log["deaths_today"] = dead_this_turn
        
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