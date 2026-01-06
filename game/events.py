import random
import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Union, Any, TYPE_CHECKING
from .models import Alliance, Terrain, format_tribute_list
from .combat import CombatResolver

# Prevent circular import during runtime
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
            max_size=data.get('tributes_needed', 1), # Simple events characterised by having a fixed size
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
                    actor.take_damage(value)
                else:
                    # TODO: Add more state updates
                    pass

        # 2. Process Deaths
        dead_names = []
        for index in self.kills:
            if index < len(actors):
                victim = actors[index]
                victim.take_damage(999) # Force death
                dead_names.append(victim.name)

        # 3. Format Text
        text = self.text_template
        for i, actor in enumerate(actors):
            idx = i + 1 
            
            # Basic Name: {t1} -> "Katniss"
            text = text.replace(f"{{t{idx}}}", actor.name)
            
            # Pronoun Replacements
            if hasattr(actor, 'he_she'): 
                text = text.replace(f"{{he{idx}}}", actor.he_she)
                text = text.replace(f"{{him{idx}}}", actor.him_her)
                text = text.replace(f"{{his{idx}}}", actor.his_her)

                # Checks for {He1}, {Him1}, {His1}
                text = text.replace(f"{{He{idx}}}", actor.he_she.capitalize())
                text = text.replace(f"{{Him{idx}}}", actor.him_her.capitalize())
                text = text.replace(f"{{His{idx}}}", actor.his_her.capitalize())
            
        return text


class ScavengeEvent(GameEvent):
    """
    Complex Event: Searching for items.
    """
    def __init__(self):
        super().__init__("Scavenge", tags=["scavenge"], min_size=1, max_size=1)

    def execute(self, alliance, terrain, game_engine_ref=None):
        tribute = alliance.members[0]
        
        # TODO: High intelligence finds better loot?
        # Pure random from the engine's item pool
        if not game_engine_ref or not game_engine_ref.item_pool:
            return f"{tribute.name} searches for food but finds nothing."

        found_item = random.choice(game_engine_ref.item_pool)
        tribute.inventory.append(found_item)
        
        # Check Proficiency
        if found_item.name in tribute.proficient_items:
            return f"{tribute.name} finds a {found_item.name}. {tribute.he_she.capitalize()} looks deadly with it!"
            
        return f"{tribute.name} finds a {found_item.name}."


class AmicableDisbandEvent(GameEvent):
    """
    Complex Event: Breaking up a group.
    """
    def __init__(self):
        super().__init__("Disband", tags=["social"], min_size=2, max_size=10)

    def execute(self, alliance, terrain, game_engine_ref=None):
        # ITEM DISTRIBUTION LOGIC
        all_items = []
        
        # 1. Pool all items (Personal + Shared)
        for member in alliance.members:
            all_items.extend(member.inventory)
            member.inventory = []  # Clear temporarily
            
        if hasattr(alliance, 'shared_inventory'):
            all_items.extend(alliance.shared_inventory)
            alliance.shared_inventory = []

        # 2. Redistribute based on Proficiency
        remaining_items = []
        
        # Shuffle members to ensure fair chance for duplicate proficiency items
        shuffled_members = list(alliance.members)
        random.shuffle(shuffled_members)

        for item in all_items:
            assigned = False
            for m in shuffled_members:
                # If member is proficient and we haven't assigned this item yet
                if item.name in m.proficient_items:
                    m.inventory.append(item)
                    assigned = True
                    break # Item goes to the first specialist found
            
            if not assigned:
                remaining_items.append(item)

        # 3. Distribute remaining items evenly
        random.shuffle(remaining_items)
        member_index = 0
        while remaining_items:
            item = remaining_items.pop()
            alliance.members[member_index].inventory.append(item)
            # Cycle through members (0, 1, 2, 0, 1...)
            member_index = (member_index + 1) % len(alliance.members)

        # DISBAND LOGIC
        # The engine loop will need to check if the alliance is empty after this
        new_alliances = alliance.disband()
        
        alliance.members = [] 
        
        if game_engine_ref:
            game_engine_ref.pending_new_alliances.extend(new_alliances)
            
        names = format_tribute_list([a.members[0] for a in new_alliances])
        return f"{names} decide to split. They divide their supplies evenly and go their separate ways."


class FormAllianceEvent(GameEvent):
    """
    Complex Event: Merges two groups into one.
    """
    def __init__(self):
        super().__init__("Form Alliance", tags=["social"], min_size=1, max_size=5, weight=8)

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref:
            return "The wind blows."

        # 1. Enforce Minimum 2 Alliances Rule
        # We count how many groups are currently active (alive)
        active_alliances_count = len([a for a in game_engine_ref.alliances if a.is_active])
        
        # If we currently have 2 groups, merging them makes 1. So we need > 2 to merge.
        if active_alliances_count <= 2:
             names = format_tribute_list(alliance.members)
             verb = 'look' if len(alliance.members) > 1 else 'looks'
             return f"{names} {verb} for allies, but decides trust is too dangerous right now."

        # 2. Find a target group to merge with
        # Must be active, not the current group, and combined size shouldn't exceed 6
        potential_friends = [
            a for a in game_engine_ref.alliances 
            if a != alliance and a.is_active and (len(a.members) + len(alliance.members) <= 6)
        ]

        if not potential_friends:
            names = format_tribute_list(alliance.members)
            verb = 'look' if len(alliance.members) > 1 else 'looks'
            return f"{names} {verb} for allies but finds no one."

        # 3. Pick a friend
        friend_alliance = random.choice(potential_friends)

        # 4. Create the Merged Alliance
        # Combine lists but ensure no specific tribute object appears twice
        seen_ids = set()
        new_members = []
        
        for member in (alliance.members + friend_alliance.members):
            if id(member) not in seen_ids:
                new_members.append(member)
                seen_ids.add(id(member))
        
        new_alliance = Alliance(new_members)
        
        # 5. Update Engine
        game_engine_ref.pending_new_alliances.append(new_alliance)
        
        # 6. Clear old alliances so they become inactive (and don't act again this turn)
        # We need the names before we clear them
        names_a = format_tribute_list(alliance.members)
        names_b = format_tribute_list(friend_alliance.members)
        
        # Clear old alliances
        alliance.members = [] 
        friend_alliance.members = []

        return f"An alliance is formed! " \
               f"{('The group of' + names_a) if len(names_a) > 2 else names_a} " \
               f"joins forces with {('the group of' + names_b) if len(names_b) > 2 else names_b}."


class CombatEvent(GameEvent):
    """
    Complex Event: Triggers a battle between two groups.
    """
    def __init__(self) -> None:
        super().__init__("Ambush", tags=["combat"], min_size=1, max_size=10, weight=5)
        self.resolver = CombatResolver()

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref:
            return "The wind howls."

        # 1. Filter Targets
        potential_targets = []
        
        # Get IDs of attackers to prevent self-targeting logic
        attacker_ids = {id(t) for t in alliance.members}

        for a in game_engine_ref.alliances:
            if a == alliance: continue
            if not a.is_active: continue
            
            enemy_ids = {id(t) for t in a.members}
            
            # If the sets share any members (intersection is not empty), skip this fight
            if not attacker_ids.isdisjoint(enemy_ids):
                continue
                
            potential_targets.append(a)

        if not potential_targets:
            return f"{format_tribute_list(alliance.members)} {'hunt' if len(alliance.members) > 1 else 'hunts'} for enemies but finds no one."

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
        self.events.append(FormAllianceEvent())
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