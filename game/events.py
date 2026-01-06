import random
import json
import os
from abc import ABC, abstractmethod
from .models import Alliance, Terrain
from .combat import CombatResolver
from typing import Optional, Union, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import GameEngine

class GameEvent(ABC):
    """
    Abstract Base Class for all things that happen in the arena.
    """
    def __init__(self, 
                 name: str, 
                 tags: list[str], 
                 min_size: int=1, 
                 max_size: int=10, 
                 weight: float=10) -> None:
        self.name = name
        self.tags = tags  # List: ['water', 'forest', 'combat']
        self.min_size = min_size
        self.max_size = max_size
        self.base_weight = weight

    def check_conditions(self, alliance: Alliance, terrain: Terrain) -> bool:
        """
        Returns True if this event CAN happen to this group.
        """
        # 1. Group Size Check
        if not (self.min_size <= len(alliance.members) <= self.max_size):
            return False
            
        # 2. Terrain Compatibility
        # If an event is tagged "water" but terrain multiplier for "water" is 0, impossible.
        if terrain.get_multiplier(self.tags) == 0:
            return False
            
        return True

    def get_adjusted_weight(self, terrain: Terrain) -> float:
        """
        Calculates probability based on Terrain settings.
        """
        return self.base_weight * terrain.get_multiplier(self.tags)

    @abstractmethod
    def execute(self, alliance: Alliance, terrain: Terrain, game_engine_ref: Optional["GameEngine"]=None):
        """
        Performs the event logic.
        Returns: String (The log text to display)
        """
        pass


class SimpleEvent(GameEvent):
    """
    Data-driven events loaded from JSON.
    Example: "{T1} trips on a root."
    """
    def __init__(self, data: dict[str,Any]) -> None:
        super().__init__(
            name=data.get('id', 'simple_event'),
            tags=data.get('tags', []),
            min_size=data.get('tributes_needed', 1),
            max_size=data.get('tributes_needed', 1), # Usually fixed size
            weight=data.get('weight', 10)
        )
        self.text_template: str = data['text']
        self.effects: dict[str, float] = data.get('effects', {}) # e.g., {'health': -10}
        self.kills: list[int] = data.get('kills', [])     # List of indices [0, 1] who die

    def execute(self, alliance, terrain, game_engine_ref=None):
        actors = alliance.members
        
        # 1. Apply State Changes
        for stat, value in self.effects.items():
            for actor in actors:
                # If stat is 'health', modify it
                if stat == 'health':
                    actor.take_damage(abs(value)) # abs() to handle negative json input
                else:
                    # TODO: Add more state updates
                    pass

        # 2. Process Deaths (if defined in JSON)
        dead_names = []
        for index in self.kills:
            if index < len(actors):
                victim = actors[index]
                victim.take_damage(999) # Force death
                dead_names.append(victim.name)

        # 3. Format Text
        # Replaces {t1}, {t2} with names
        text = self.text_template
        for i, actor in enumerate(actors):
            placeholder = f"{{t{i+1}}}" # {t1}, {t2}...
            text = text.replace(placeholder, actor.name)
            
        return text
    
class ScavengeEvent(GameEvent):
    """
    Complex Event: Searching for items.
    """
    def __init__(self):
        super().__init__("Scavenge", tags=["scavenge"], min_size=1, max_size=1)

    def execute(self, alliance, terrain, game_engine_ref=None):
        tribute = alliance.members[0]
        
        # Logic: High intelligence finds better loot?
        # For now, pure random from the engine's item pool
        if not game_engine_ref or not game_engine_ref.item_pool:
            return f"{tribute.name} searches for food but finds nothing."

        found_item = random.choice(game_engine_ref.item_pool)
        tribute.inventory.append(found_item)
        
        # Check Proficiency
        # Remember: proficient_items is a list now
        if found_item.name in tribute.proficient_items:
            return f"{tribute.name} finds a {found_item.name}. They look deadly with it!"
            
        return f"{tribute.name} finds a {found_item.name}."

class AmicableDisbandEvent(GameEvent):
    """
    Complex Event: Breaking up a group.
    """
    def __init__(self):
        super().__init__("Disband", tags=["social"], min_size=2, max_size=10)

    def execute(self, alliance, terrain, game_engine_ref=None):
        
        # The engine loop will need to check if the alliance is empty after this
        new_alliances = alliance.disband()
        
        # We need to register these new alliances back to the engine
        if game_engine_ref:
            game_engine_ref.pending_new_alliances.extend(new_alliances)
            
        names = ", ".join([a.members[0].name for a in new_alliances])
        return f"The group decides to split up. {names} go their separate ways."

class CombatEvent(GameEvent):
    """
    Complex Event: Triggers a battle between two groups.
    """
    def __init__(self) -> None:
        super().__init__("Ambush", tags=["combat"], min_size=1, max_size=10, weight=5)
        self.resolver = CombatResolver()

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref:
            return "The wind howls. (Error: No Engine Ref)"

        # 1. Find a target group
        potential_targets = [
            a for a in game_engine_ref.alliances 
            if a != alliance and a.is_active
        ]

        if not potential_targets:
            return f"{alliance.members[0].name} hunts for enemies but finds no one."

        # Pick a random enemy group
        enemy_alliance = random.choice(potential_targets)

        # 2. Resolve Fight
        # Current 'alliance' is the Attacker (initator)
        result_text = self.resolver.resolve_fight(
            attackers=alliance.members, 
            defenders=enemy_alliance.members, 
            terrain=terrain
        )

        return result_text

class EventManager:
    """
    The Brain that picks events.
    """
    def __init__(self) -> None:
        self.events = []
        
        # 1. Load Hardcoded Complex Events
        self.events.append(ScavengeEvent())
        self.events.append(AmicableDisbandEvent())
        self.events.append(CombatEvent()) 
        
        # 2. Load JSON Events
        self.load_json_events()

    def load_json_events(self) -> None:
        """Loads simple text events from data/events.json"""
        path = os.path.join(os.path.dirname(__file__), 'data', 'events.json')
        if not os.path.exists(path):
            print("Warning: No events.json found.")
            return

        with open(path, 'r') as f:
            data = json.load(f)
            
        for e_data in data:
            self.events.append(SimpleEvent(e_data))

    def select_event(self, alliance: Alliance, terrain: Terrain) -> Optional[GameEvent]:
        """
        Weighted Random Selection based on Terrain and Group Size.
        """
        valid_events = []
        weights = []
        
        for event in self.events:
            if event.check_conditions(alliance, terrain):
                w = event.get_adjusted_weight(terrain)
                if w > 0:
                    valid_events.append(event)
                    weights.append(w)
                    
        if not valid_events:
            return None # Should handle "Uneventful day" elsewhere
            
        return random.choices(valid_events, weights=weights, k=1)[0]