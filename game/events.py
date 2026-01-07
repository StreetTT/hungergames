import random
import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Union, Any, TYPE_CHECKING
from .models import Alliance, Terrain, Item, format_tribute_list
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

    def get_adjusted_weight(self, terrain: Terrain, day: int = 1) -> float:
        """
        Calculates probability based on Terrain settings.
        Accepts 'day' for time-based scaling logic.
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
    Supports: Stats, Health, Status, Item Gain/Loss, and Item Requirements.
    Now supports decoupling 'tributes_needed' (for text) from group size.
    """
    def __init__(self, data: dict[str,Any]) -> None:
        # The number of people used in the text/logic (e.g. {t1}, {t2})
        self.tributes_needed = data.get('tributes_needed', 1)
        
        # Group size constraints
        # Default min/max match tributes_needed for backward compatibility (strict matching)
        # JSON can override these to allow 1-person events in 5-person groups.
        min_s = data.get('min_size', self.tributes_needed)
        max_s = data.get('max_size', self.tributes_needed)

        super().__init__(
            name=data.get('id', 'simple_event'),
            tags=data.get('tags', []),
            min_size=min_s,
            max_size=max_s,
            weight=data.get('weight', 10)
        )
        self.text_template: str = data['text']
        
        # Stat/Health/Status Changes
        self.effects: dict[str, float] = data.get('effects', {}) 
        
        # Death Logic
        self.kills: list[int] = data.get('kills', [])
        
        # Item Logic
        self.requires_item: Optional[str] = data.get('requires_item', None) # Name of item needed to trigger
        self.gain_items: list[str] = data.get('gain_items', [])             # Names of items to receive
        self.lose_items: list[str] = data.get('lose_items', [])             # Names of items to remove

    def check_conditions(self, alliance: Alliance, terrain: Terrain) -> bool:
        # 1. Standard checks (size vs min_size/max_size, terrain)
        if not super().check_conditions(alliance, terrain):
            return False
            
        # 2. Item Requirement Check
        if self.requires_item:
            # Check shared inventory
            in_shared = any(i.name == self.requires_item for i in alliance.shared_inventory)
            if in_shared:
                return True
                
            # Check personal inventories
            for member in alliance.members:
                if any(i.name == self.requires_item for i in member.inventory):
                    return True
            
            return False
                
        return True

    def execute(self, alliance, terrain, game_engine_ref=None):
        # --- 1. SELECT ACTIVE ACTORS ---
        all_members = list(alliance.members)
        random.shuffle(all_members)
        
        active_actors = []

        # Special Case: If Item Required, {t1} MUST be someone who has the item.
        if self.requires_item:
            # Check if it's in shared inventory
            in_shared = any(i.name == self.requires_item for i in alliance.shared_inventory)
            
            if in_shared:
                # Anyone can use it
                active_actors.append(all_members.pop(0))
            else:
                # Must find someone who has it personally
                candidate_t1 = next((m for m in all_members if any(i.name == self.requires_item for i in m.inventory)), None)
                if candidate_t1:
                    active_actors.append(candidate_t1)
                    all_members.remove(candidate_t1) # Remove so they aren't picked as t2
                else:
                    # Fallback (shouldn't happen due to check_conditions)
                    active_actors.append(all_members.pop(0))
        else:
            # No item req, just pick random first person
            active_actors.append(all_members.pop(0))

        # Fill remaining roles
        needed_rem = self.tributes_needed - 1
        if needed_rem > 0:
            # We use min() to ensure we don't crash if group size < needed (shouldn't happen due to logic)
            count = min(len(all_members), needed_rem)
            active_actors.extend(all_members[:count])

        # IMPORTANT: All subsequent logic (Effects, Kills, Text) applies ONLY to active_actors
        actors = active_actors
        
        # --- 2. APPLY EFFECTS ---
        for stat, value in self.effects.items():
            for actor in actors:
                if stat == 'health':
                    if value < 0: actor.change_health(-abs(value))
                    else: actor.health = min(actor.max_health, actor.health + value)
                        
                elif stat in ['strength', 'intel', 'speed', 'defense', 'aggression', 'stealth']:
                    if hasattr(actor, 'stats'):
                        current = actor.stats.get(stat, 5)
                        actor.stats[stat] = min(max(1, current + value), 10)

                elif stat in ['poisoned', 'injured']:
                    is_active = (value > 0)
                    if hasattr(actor, stat):
                        setattr(actor, stat, is_active)

        # --- 3. ITEM LOSS ---
        for item_name in self.lose_items:
            # Try personal inventory of the main actor first
            target = actors[0] if actors else None
            found = False
            
            if target:
                match = next((i for i in target.inventory if i.name == item_name), None)
                if match:
                    target.inventory.remove(match)
                    found = True
            
            # If not found personally, check shared inventory
            if not found:
                match_shared = next((i for i in alliance.shared_inventory if i.name == item_name), None)
                if match_shared:
                    alliance.shared_inventory.remove(match_shared)

        # --- 4. ITEM GAIN ---
        if self.gain_items and game_engine_ref:
            # We access items via the terrain object in the engine
            from .models import Item
            
            for item_name in self.gain_items:
                new_item = None
                
                # Check Infinite/Finite Pools
                infinite_match = next((i for i in game_engine_ref.terrain.infinite_items if i.name == item_name), None)
                if infinite_match:
                     new_item = Item(infinite_match.name, infinite_match.kind, infinite_match.bonuses)
                else:
                    finite_idx = -1
                    for idx, i in enumerate(game_engine_ref.terrain.finite_items):
                        if i.name == item_name:
                            finite_idx = idx
                            break
                    if finite_idx != -1:
                        # Pop it from the arena!
                        new_item = game_engine_ref.terrain.finite_items.pop(finite_idx)
                    else:
                        # C. Generic Generation
                        new_item = Item(item_name, "misc")

                if new_item and actors:
                    # Logic: If solo, keep it. If group, chance to share.
                    selfish_chance = min(0, (0.03 * actors[0].stats.get('stealth',5)) - 0.05)
                    if len(alliance.members) == 1 or random.random() < selfish_chance:
                        if actors: actors[0].inventory.append(new_item)
                    else:
                        # Shared inventory
                        alliance.shared_inventory.append(new_item)

        # --- 5. PROCESS DEATHS ---
        dead_names = []
        for index in self.kills:
            if index < len(actors):
                victim = actors[index]
                victim.change_health(-999) 
                dead_names.append(victim.name)

        # --- 6. FORMAT TEXT ---
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
    Complex Event: Searching for items (Finite vs Infinite).
    """
    def __init__(self):
        super().__init__("Scavenge", tags=["scavenge"], min_size=1, max_size=1)

    def execute(self, alliance, terrain, game_engine_ref=None):
        tribute = alliance.members[0]
        # TODO: High intelligence finds better loot?
        
        # We need the terrain to access items
        if not terrain:
            return f"{tribute.name} looks for supplies but finds nothing."

        found_item = None
        
        # 1. Try to find a Rare/Finite Item (20% Chance if any exist)
        if terrain.finite_items and random.random() < 0.20:
            # Randomly pick an index so we can POP it (remove from game)
            idx = random.randrange(len(terrain.finite_items))
            found_item = terrain.finite_items.pop(idx)
            
        # 2. Fallback to Common/Infinite Items
        elif terrain.infinite_items:
            # Create a COPY (Factory Mode)
            prototype = random.choice(terrain.infinite_items)
            found_item = Item(prototype.name, prototype.kind, prototype.bonuses)
            
        else:
            return f"{tribute.name} searches frantically but the arena has been picked clean."

        if found_item:
            if len(alliance.members) == 1: tribute.inventory.append(found_item)
            else : alliance.shared_inventory.append(found_item)
            
            if found_item.name in tribute.proficient_items:
                return f"{tribute.name} uncovers a {found_item.name}. They smile wickedly."
                
            return f"{tribute.name} scavenges and finds a {found_item.name}."
            
        return f"{tribute.name} finds nothing of use."

class AmicableDisbandEvent(GameEvent):
    """
    Complex Event: Breaking up a group.
    """
    def __init__(self):
        super().__init__("Disband", tags=["social"], min_size=2, max_size=10)

    def execute(self, alliance, terrain, game_engine_ref=None):
        # ITEM DISTRIBUTION LOGIC
        all_items = []
        
        # 1. Pool all items (Personal)
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

        # Logic: Deduplicate members, merge inventories
        seen_ids = set()
        new_members = []
        
        for member in (alliance.members + friend_alliance.members):
            if id(member) not in seen_ids:
                new_members.append(member)
                seen_ids.add(id(member))
        
        new_alliance = Alliance(new_members)
        
        # 5. MERGE SHARED INVENTORIES
        if hasattr(alliance, 'shared_inventory'):
            new_alliance.shared_inventory.extend(alliance.shared_inventory)
        if hasattr(friend_alliance, 'shared_inventory'):
            new_alliance.shared_inventory.extend(friend_alliance.shared_inventory)
        
        # 6. Update Engine
        game_engine_ref.pending_new_alliances.append(new_alliance)
        
        # 6. Clear old alliances so they become inactive (and don't act again this turn)
        # We need the names before we clear them
        names_a = format_tribute_list(alliance.members)
        names_b = format_tribute_list(friend_alliance.members)
        
        # Clear old alliances
        alliance.members = [] 
        friend_alliance.members = []

        return f"An alliance is formed! " \
               f"{('The group of ' + names_a) if len(alliance.members) > 2 else names_a} " \
               f"joins forces with {('the group of ' + names_b) if len(friend_alliance.members) > 2 else names_b}."


class CombatEvent(GameEvent):
    """
    Complex Event: Triggers a battle between two groups.
    """
    def __init__(self) -> None:
        super().__init__("Ambush", tags=["combat"], min_size=1, max_size=10, weight=5)
        self.resolver = CombatResolver()

    def get_adjusted_weight(self, terrain: Terrain, day: int = 1) -> float:
        """
        Increases likelihood of combat by 10% per day to ensure the game resolves.
        """
        base_w = super().get_adjusted_weight(terrain, day)
        time_multiplier = 1.0 + (day * 0.5)
        return base_w * time_multiplier

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

        result_text = self.resolver.resolve_fight(
            attacker_alliance=alliance, 
            defender_alliance=enemy_alliance, 
            terrain=terrain
        )

        return result_text

class ForceSplitEvent(GameEvent):
    """
    Special Event: Forces the final group to disband.
    """
    def __init__(self):
        super().__init__("Force Split", ["gamemaker"], min_size=2, max_size=99)

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Error"
        
        # Distribute shared inventory
        if hasattr(alliance, 'shared_inventory') and alliance.shared_inventory:
            for item in alliance.shared_inventory:
                random.choice(alliance.members).inventory.append(item)
            alliance.shared_inventory = []

        names = format_tribute_list(alliance.members)
        
        # Perform disband
        new_solos = alliance.disband()
        
        # Update engine directly
        game_engine_ref.alliances = new_solos
        
        return f"Only {names} remain. The Gamemakers announce that there can be only one victor, forcing the alliance to turn on each other!"

class ExtinctionPreventionEvent(GameEvent):
    """
    Special Event: Revives a tribute if everyone died.
    """
    def __init__(self):
        super().__init__("Extinction Prevention", ["gamemaker"], min_size=0, max_size=0)

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Error"
        
        # Find recently dead
        recently_dead_objs = [t for t in game_engine_ref.tributes if not t.alive and t.name not in game_engine_ref._get_previously_dead()]
        
        if recently_dead_objs:
            survivor = max(recently_dead_objs, key=lambda t: t.stats.get('defense', 0) + random.random())
            survivor.alive = True
            survivor.health = 1
            return f"Against all odds, {survivor.name} clings to life, refusing to die!"
        
        return "Everyone is dead."

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

    def select_event(self, alliance: Alliance, terrain: Terrain, day: int = 1) -> Optional[GameEvent]:
        """
        Weighted Random Selection based on Terrain and Group Size.
        """
        valid_events = []
        weights = []
        
        for event in self.events:
            if event.check_conditions(alliance, terrain):
                w = event.get_adjusted_weight(terrain, day)
                if w > 0:
                    valid_events.append(event)
                    weights.append(w)
                    
        if not valid_events:
            return None # Should handle "Uneventful day" elsewhere
            
        return random.choices(valid_events, weights=weights, k=1)[0]