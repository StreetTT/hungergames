import random
import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Union, Any
from .models import Alliance, Terrain, Item
from .combat import CombatResolver
from .utils import format_tribute_list, replace_pronouns, get_tradable_item

class GameEvent(ABC):
    """
    Abstract Base Class for all things that happen in the arena.
    """
    def __init__(self, data: dict[str, Any]={}) -> None:
        self.name: str = data.get('id', 'simple_event')
        self.tags: list[str] = data.get('tags', [])  # List: ['water', 'forest', 'combat']
        self.base_weight: float = data.get('weight', 5)
        self.text_template: str = data.get('text', '')
                
        # Group size constraints
        self.tributes_needed = data.get('tributes_needed', 1)
        self.min_size: int = data.get('min_size', self.tributes_needed)
        self.max_size: int = data.get('max_size', self.tributes_needed)
        
        # Stat/Health/Status Changes
        self.effects: dict[str, float] = data.get('effects', {}) 
        
        # Death Logic
        self.kills: list[int] = data.get('kills', [])
        
        # Item Logic
        self.requires_item: Optional[str] = data.get('requires_item', None) # Name of item needed to trigger
        self.gain_items: list[str] = data.get('gain_items', [])             # Names of items to receive
        self.lose_items: list[str] = data.get('lose_items', [])             # Names of items to remove

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

    # --- SHARED HELPERS ( The "DRY" Logic ) ---

    def resolve_actors(self, alliance: Alliance, count: int, item_req: Optional[str]=None):
        """
        Selects <count> members from the alliance.
        Prioritizes those with 'item_req' if specified.
        """
        candidates = list(alliance.members)
        random.shuffle(candidates)
        
        selected = []
        
        # 1. Filter for Item Requirement
        if item_req:
            # Check shared
            has_shared = any(i.name == item_req for i in alliance.shared_inventory)
            
            if not has_shared:
                # Must find specific member
                holder = next((m for m in candidates if any(i.name == item_req for i in m.inventory)), None)
                if holder:
                    selected.append(holder)
                    candidates.remove(holder)
        
        # 2. Fill remainder
        while len(selected) < count and candidates:
            selected.append(candidates.pop(0))
            
        return selected

    def apply_outcome(self, actors: list["Tribute"], alliance: Alliance, engine, outcome_override:Optional[dict[str, Any]]=None): #type: ignore
        """
        Universal processor for effects defined in JSON.
        outcome_data: { 'effects': {...}, 'gain_items': [...], 'lose_items': [...] }
        """
        if not actors: return

        # Merge defaults with overrides
        effects = outcome_override.get('effects', self.effects) if outcome_override else self.effects
        losses = outcome_override.get('lose_items', self.lose_items) if outcome_override else self.lose_items
        gains = outcome_override.get('gain_items', self.gain_items) if outcome_override else self.gain_items

        # 1. Stat/Health Effects
        for stat, val in effects.items():
            for actor in actors:
                if stat == 'health':
                    actor.change_health(val)
                elif stat in actor.stats:
                    actor.modify_stat(stat, val)
                elif stat in ['poisoned', 'injured']:
                    setattr(actor, stat, (val > 0))

        # 2. Item Loss
        for item_name in losses:
            removed = False
            for actor in actors:
                match = next((i for i in actor.inventory if i.name == item_name), None)
                if match:
                    actor.inventory.remove(match)
                    removed = True
                    break
            if not removed:
                match = next((i for i in alliance.shared_inventory if i.name == item_name), None)
                if match: alliance.shared_inventory.remove(match)

        # 3. Item Gain
        for item_name in gains:
            # Use engine helper if available, else generic
            new_item = engine.create_item_from_name(item_name)
            if new_item:
                if len(alliance.members) == 1: actors[0].inventory.append(new_item)
                else: alliance.shared_inventory.append(new_item)

    def format_text(self, primary_actors, target_actors=None):
        """Uses the robust replace_pronouns from utils.py"""
        text = self.text_template

        # Primary (t1, t2...)
        for i, actor in enumerate(primary_actors):
            text = replace_pronouns(text, actor, f"t{i+1}")
            
        # Targets (e1, e2...)
        if target_actors:
            for i, actor in enumerate(target_actors):
                text = replace_pronouns(text, actor, f"e{i+1}")
        return text
    
    def get_valid_targets(self, current_alliance: Alliance, game_engine) -> list[Alliance]:
        """Returns list of OTHER active alliances."""
        if not game_engine: return []
        return [a for a in game_engine.alliances if a != current_alliance and a.is_active]
    
    def get_skill_check(self, actor_list, target_list, actor_stat, target_stat, variance=10, difficulty_mod=0) -> bool:
        """Rolls (Best Actor Stat) vs (Best Target Stat + Mod)."""
        val_a = max(t.get_effective_stat(actor_stat) for t in actor_list)
        val_b = max(t.get_effective_stat(target_stat) for t in target_list)
        return (val_a + random.randint(1, variance)) > (val_b + difficulty_mod + random.randint(1, variance))

    def attempt_theft(self, thief_alliance: Alliance, victim_alliance: Alliance, amount: int=1) -> list[Item]:
        """Moves items from victim to thief."""
        stolen_items = []
        for _ in range(amount):
            item = None
            # Try victim inventory
            if victim_alliance.members and victim_alliance.members[0].inventory:
                item = victim_alliance.members[0].inventory.pop(0)
            # Try victim shared
            elif victim_alliance.shared_inventory:
                item = victim_alliance.shared_inventory.pop(0)
            
            if item:
                stolen_items.append(item)
                if len(thief_alliance.members) == 1: thief_alliance.members[0].inventory.append(item)
                else: thief_alliance.shared_inventory.append(item)
                    
        return stolen_items

    @abstractmethod
    def execute(self, alliance: Alliance, terrain: Terrain, game_engine_ref: Optional["GameEngine"]=None):
        """
        Performs the event logic.
        Returns: String (The log text to display)
        """
        pass

class SimpleEvent(GameEvent):
    def check_conditions(self, alliance: Alliance, terrain: Terrain) -> bool:
        # 1. Standard checks (size vs min_size/max_size, terrain)
        if not super().check_conditions(alliance, terrain): return False
        # 2. Item Requirement Check
        if self.requires_item:
            # Check shared inventory
            in_shared = any(i.name == self.requires_item for i in alliance.shared_inventory)
            in_personal = any(any(i.name == self.requires_item for i in m.inventory) for m in alliance.members)
            if not (in_shared or in_personal): return False
        return True

    def execute(self, alliance, terrain, game_engine_ref=None):
        # 1. Select
        actors = self.resolve_actors(alliance, self.tributes_needed, self.requires_item)

        # 2. Apply
        self.apply_outcome(actors, alliance, game_engine_ref)
        
        # 3. Process Specific Kills (SimpleEvent specific feature)
        for k_idx in self.kills:
            if k_idx < len(actors):
                actors[k_idx].change_health(-999)
                
        # 4. Text
        return self.format_text(actors)

class ComplexEvent(GameEvent):
    """
    Hard-coded complex events defined in Python.
    """
    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Nothing happens."

class CombatEvent(GameEvent):
    def __init__(self) -> None:
        super().__init__()
        self.name = "Ambush"
        self.tags = ["combat"]
        self.max_size = 10
        self.weight = 15
        self.resolver = CombatResolver()

    def get_adjusted_weight(self, terrain: Terrain, day: int = 1) -> float:        return super().get_adjusted_weight(terrain, day) * (1.0 + (day * 0.05))

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "The wind howls."
        targets = self.get_valid_targets(alliance, game_engine_ref)
        if not targets: return f"{format_tribute_list(alliance.members)} hunts for enemies but finds no one."
        return self.resolver.resolve_fight(alliance, random.choice(targets), terrain, game_engine_ref)

class InterAllianceEvent(GameEvent):
    """
    Handles interactions between two specific groups (Trading, Spying, Stealing, etc.).
    Defined in JSON with "type": "interaction".
    """
    def __init__(self, data: dict[str,Any]={}) -> None:
        super().__init__()
        self.targets_needed = data.get('targets_needed', 1)
        self.target_outcome = {
            'effects': data.get('target_effects', {}),
            'gain_items': data.get('target_gain_items', []),
            'lose_items': data.get('target_lose_items', [])
        }

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Nothing happens."

        # 1. Find Target Alliance
        enemies = self.get_valid_targets(alliance, game_engine_ref)
        if not enemies: return f"{format_tribute_list(alliance.members)} wanders alone."
        target_alliance = random.choice(enemies)
        
        # 2. Select Actors & Targets
        actors = self.resolve_actors(alliance, self.tributes_needed)
        targets = self.resolve_actors(target_alliance, self.targets_needed)
        
        # 3. Apply to Both Sides
        self.apply_outcome(actors, alliance, game_engine_ref)
        self.apply_outcome(targets, target_alliance, game_engine_ref, self.target_outcome)

        # 4. Text (Passes both groups)
        return self.format_text(actors, targets)

class ThiefEvent(InterAllianceEvent):
    """
    Theft Interaction: Success or Fail (No Fight).
    """
    def __init__(self):
        super().__init__()
        self.name = "Thief"
        self.tags = ["scavenge", "stealth"] 
        self.min_size = 1
        self.max_size = 99
        self.weight = 9

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Nothing happens."
        targets = self.get_valid_targets(alliance, game_engine_ref)
        if not targets: return f"{format_tribute_list(alliance.members)} sneaks around but finds no one."
        
        target = random.choice(targets)
        
        # Check Stealth vs Intel
        if self.get_skill_check(alliance.members, target.members, 'stealth', 'intel'):
            # Steal 1 Item
            stolen = self.attempt_theft(alliance, target, amount=1)
            if stolen:
                return f"{format_tribute_list(alliance.members)} sneaks into {format_tribute_list(target.members)}'s camp and steals a {stolen[0].name}!"
            return f"{format_tribute_list(alliance.members)} raids {format_tribute_list(target.members)}'s camp but finds nothing to steal."
        
        return f"{format_tribute_list(alliance.members)} tries to steal from {format_tribute_list(target.members)} but is caught and forced to flee."

class RiskyTheftEvent(InterAllianceEvent, CombatEvent):
    """
    Complex Theft: Low Success, Failure = Combat.
    """
    def __init__(self):
        super().__init__()
        self.name = "High Stakes Theft"
        self.tags = ["scavenge", "stealth", "combat"]
        self.min_size = 1
        self.max_size = 99
        self.weight = 10

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Nothing happens."
        targets = self.get_valid_targets(alliance, game_engine_ref)
        if not targets: return f"{format_tribute_list(alliance.members)} stalks the shadows alone."
        
        target = random.choice(targets)
        
        # Stealth vs Intel (+5 Difficulty)
        if self.get_skill_check(alliance.members, target.members, 'stealth', 'intel', difficulty_mod=5):
            stolen = self.attempt_theft(alliance, target, amount=2)
            if stolen:
                names = ", ".join([i.name for i in stolen])
                return f"{format_tribute_list(alliance.members)} pulls off a master heist, stealing {names} from {format_tribute_list(target.members)}!"
            return f"{format_tribute_list(alliance.members)} infiltrates {format_tribute_list(target.members)}'s camp but they have nothing left."
        
        # FAIL -> COMBAT
        return f"{format_tribute_list(alliance.members)} is caught stealing from {format_tribute_list(target.members)}! {self.resolver.resolve_fight(target, alliance, terrain, game_engine_ref)}"

class SpyEvent(InterAllianceEvent, CombatEvent):
    """
    Spy Interaction: Success (Intel Gain) or Fail (Combat).
    """
    def __init__(self):
        super().__init__()
        self.name = "Spy"
        self.tags = ["stealth", "intel"]
        self.weight = 8
        self.resolver = CombatResolver()

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Nothing happens."
        targets = self.get_valid_targets(alliance, game_engine_ref)
        if not targets: return f"{format_tribute_list(alliance.members)} watches the horizon."
        
        target = random.choice(targets)
        
        if self.get_skill_check(alliance.members, target.members, 'stealth', 'intel'):
            for t in alliance.members:
                t.stats['intel'] = min(10, t.stats['intel'] + 1)
            return f"{format_tribute_list(alliance.members)} spies on {format_tribute_list(target.members)}, learning valuable information."
        
        return f"{format_tribute_list(alliance.members)} is spotted spying on {format_tribute_list(target.members)}! {self.resolver.resolve_fight(target, alliance, terrain, game_engine_ref)}"


class SpecialEvent(GameEvent):
    def __init__(self):
        super().__init__()
        self.tags = ["gamemaker"]   

class ScavengeEvent(ComplexEvent):
    """
    Complex Event: Searching for items (Finite vs Infinite).
    """
    def __init__(self):
        super().__init__()
        self.name = "Scavenge"
        self.tags = ["scavenge"]
        self.min_size = 1
        self.max_size = 1

    def execute(self, alliance, terrain, game_engine_ref=None):
        super().execute(alliance, terrain, game_engine_ref)
        
        tribute = alliance.members[0]
        # TODO: High intelligence finds better loot
        
        # We need the terrain to access items
        if not terrain: return f"{tribute.name} looks for supplies but finds nothing."

        found_item = None

        # 1. Try to find a Rare/Finite Item (30% Chance if any exist)
        if terrain.finite_items and random.random() < 0.30:
            # Randomly pick an index so we can POP it (remove from game)
            idx = random.randrange(len(terrain.finite_items))
            found_item = terrain.finite_items.pop(idx)
            
        # 2. Fallback to Common/Infinite Items
        elif terrain.infinite_items:
            proto = random.choice(terrain.infinite_items)
            found_item = Item(proto.name, proto.kind, proto.bonuses)
        
        else:
            return f"{tribute.name} searches frantically but the arena has been picked clean."
            
        if found_item:
            if len(alliance.members) == 1: tribute.inventory.append(found_item)
            else: alliance.shared_inventory.append(found_item)
            if found_item.name in tribute.proficient_items:
                return f"{tribute.name} uncovers a {found_item.name}. They smile wickedly."
            return f"{tribute.name} scavenges and finds a {found_item.name}."
        return f"{tribute.name} finds nothing of use."

class AmicableDisbandEvent(ComplexEvent):
    """
    Complex Event: Breaking up a group.
    """
    def __init__(self):
        super().__init__()
        self.name = "Disband"
        self.tags = ["social"]
        self.min_size = 2
        self.max_size = 10

    def execute(self, alliance, terrain, game_engine_ref=None):
        # 1. Pool Items
        all_items = []
        all_items.extend(alliance.shared_inventory)
        alliance.shared_inventory = []

        # 2. Redistribute based on Proficiency
        remaining = []
        members = list(alliance.members)
        random.shuffle(members)

        for item in all_items:
            assigned = False
            for m in members:
                # If member is proficient and we haven't assigned this item yet
                if item.name in m.proficient_items:
                    m.inventory.append(item)
                    assigned = True
                    break # Item goes to the first specialist found
                
                # Critical items (e.g. Medkits) go to first who doesn't have one
                if item.is_critical(m) and not any([i.is_critical(m) for i in m.inventory]):
                    m.inventory.append(item)
                    assigned = True
                    break
                
            if not assigned: remaining.append(item)

        # 3. Distribute Remaining
        random.shuffle(remaining)
        idx = 0
        while remaining:
            alliance.members[idx].inventory.append(remaining.pop())
            idx = (idx + 1) % len(alliance.members)

        # 4. Disband
        new_alliances = alliance.disband()
        alliance.members = [] 
        if game_engine_ref: game_engine_ref.pending_new_alliances.extend(new_alliances)
            
        names = format_tribute_list([a.members[0] for a in new_alliances])
        return f"{names} decide to split. They divide their supplies evenly and go their separate ways."

class FormAllianceEvent(ComplexEvent):
    """
    Complex Event: Merges two groups into one.
    """
    def __init__(self):
        super().__init__()
        self.name = "Form Alliance"
        self.tags = ["social"]
        self.min_size = 1
        self.max_size = 5
        self.weight = 8

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Error."
        # 1. Enforce Minimum 2 Alliances Rule
        active_count = len([a for a in game_engine_ref.alliances if a.is_active])
        names = format_tribute_list(alliance.members)
        
        if active_count <= 2:
             return f"{names} {'look' if len(alliance.members) > 1 else 'looks'} for allies, but decides trust is too dangerous right now."

        # 2. Find a target group to merge with
        potential = [a for a in game_engine_ref.alliances if a != alliance and a.is_active and (len(a.members) + len(alliance.members) <= 6)]
        if not potential:
            return f"{names} looks for allies but finds no one."

        # 3. Pick a friend
        friend_alliance = random.choice(potential)
        
        # Merge Members
        new_members = list(set(alliance.members + friend_alliance.members))
        new_members.sort(key=lambda t: t.name)
        
        new_alliance = Alliance(new_members)
        
        # 5. Merge Shared Inventory
        new_alliance.shared_inventory.extend(alliance.shared_inventory)
        new_alliance.shared_inventory.extend(friend_alliance.shared_inventory)

        # 6. Update Engine
        game_engine_ref.pending_new_alliances.append(new_alliance)
        
        # 6. Clear old alliances so they become inactive (and don't act again this turn)
        names_a = format_tribute_list(alliance.members)
        names_b = format_tribute_list(friend_alliance.members)
        
        # Clear old alliances
        alliance.members = [] 
        friend_alliance.members = []

        return f"An alliance is formed! {names} joins forces with {names_b}."

class ForceSplitEvent(SpecialEvent):
    """
    Special Event: Forces the final group to disband.
    """
    def __init__(self):
        super().__init__()
        self.name = "Force Split"
        self.min_size = 2
        self.max_size = 10

    def execute(self, alliance, terrain, game_engine_ref=None):
        # Distribute shared inventory
        # TODO: add proficiency logic
        if alliance.shared_inventory:
            for item in alliance.shared_inventory:
                random.choice(alliance.members).inventory.append(item)
            alliance.shared_inventory = []

        names = format_tribute_list(alliance.members)
        
        # Perform disband
        new_solos = alliance.disband()
        if game_engine_ref: game_engine_ref.alliances = new_solos
        
        return f"Only {names} remain. The Gamemakers announce that there can be only one victor!"

class ExtinctionPreventionEvent(SpecialEvent):
    """
    Special Event: Revives a tribute if everyone died.
    """
    def __init__(self):
        super().__init__()
        self.name = "Extinction Prevention"
        self.min_size = 0
        self.max_size = 0

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Error"
        # Find recently dead
        dead = [t for t in game_engine_ref.tributes if not t.alive and t.name not in game_engine_ref._get_previously_dead()]
        if dead:
            survivor = max(dead, key=lambda t: t.stats.get('defense', 0) + random.random())
            survivor.alive = True
            survivor.health = 1
            return f"Against all odds, {survivor.name} clings to life!"
        return "Everyone is dead."

class BloodbathEvent(SpecialEvent, CombatEvent):
    """
    Day 1 Special: High chance of combat or finding weapons.
    """
    def __init__(self):
        super().__init__()
        self.name = "Bloodbath"
        self.tags = ["combat", "scavenge"]
        self.min_size = 1
        self.max_size = 99
        self.weight = 100

    def execute(self, alliance, terrain, game_engine_ref=None):
        tribute = alliance.members[0]
        aggro = sum(t.stats.get('aggression', 5) for t in alliance.members) / len(alliance.members)
        
        # FIGHT
        if (random.random() * 20) + aggro > 12 and game_engine_ref:
            targets = self.get_valid_targets(alliance, game_engine_ref)
            if targets:
                return self.resolver.resolve_fight(
                    alliance, 
                    random.choice(targets), 
                    terrain, 
                    game_engine_ref, 
                    lethality_scale=5.0
                )
        
        # FLEE
        if (random.random() * 20) + tribute.get_effective_stat('speed') > 15 and aggro < 6:
            return f"{format_tribute_list(alliance.members)} runs away from the Cornucopia."
        
        # SCAVENGE
        found = None
        if game_engine_ref and game_engine_ref.terrain.finite_items:
            found = game_engine_ref.terrain.finite_items.pop(random.randrange(len(game_engine_ref.terrain.finite_items)))
        elif game_engine_ref and game_engine_ref.terrain.infinite_items:
            p = random.choice(game_engine_ref.terrain.infinite_items)
            found = Item(p.name, p.kind, p.bonuses)
            
        if found:
            if len(alliance.members) == 1: alliance.members[0].inventory.append(found)
            else: alliance.shared_inventory.append(found)
            return f"{format_tribute_list(alliance.members)} grabs a {found.name} from the Cornucopia!"
            
        return f"{format_tribute_list(alliance.members)} tries to grab supplies but is pushed away."

class FeastEvent(SpecialEvent, CombatEvent):
    """
    Triggered when population drops. High risk/reward.
    """
    def __init__(self):
        super().__init__()
        self.name = "The Feast"
        self.tags = ["combat", "scavenge"]
        self.min_size = 1
        self.max_size = 99
        self.weight = 100

    def execute(self, alliance, terrain, game_engine_ref=None):
        super().execute(alliance, terrain, game_engine_ref)

        # 1. Decision: Go to Feast or Stay Away?
        # Intel and Stealth influence this.
        intel = sum(t.stats.get('intel', 5) for t in alliance.members) / len(alliance.members)
        
        # Smart characters might avoid it if they are healthy
        if intel > 7 and all(t.health > 50 for t in alliance.members):
            return f"{format_tribute_list(alliance.members)} decides the Feast is a trap and stays away."
            
        # At the Feast
        if random.random() < 0.6 and game_engine_ref:
             targets = self.get_valid_targets(alliance, game_engine_ref)
             if targets:
                 return f"At the Feast, {self.resolver.resolve_fight(alliance, random.choice(targets), terrain, game_engine_ref)}"
        
        # Loot Chance (Guaranteed good item if not fighting)
        # Create a special "Feast Gift" or pull from finite
        found = None
        if game_engine_ref and game_engine_ref.terrain.finite_items:
             found = game_engine_ref.terrain.finite_items.pop(random.randrange(len(game_engine_ref.terrain.finite_items)))
        
        if not found: found = Item("Feast Basket", "food", {"health": 50})
            
        if len(alliance.members) == 1: alliance.members[0].inventory.append(found)
        else: alliance.shared_inventory.append(found)
            
        return f"{format_tribute_list(alliance.members)} dashes into the Feast and grabs {found.name}!"

class CorpseLootEvent(ComplexEvent):
    """
    Scavenges items from tributes who have already died.
    """
    def __init__(self):
        super().__init__()
        self.name = "Loot Corpse"
        self.tags = ["scavenge", "death"]
        self.min_size = 1
        self.max_size = 99
        self.weight = 10

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Error"
        # Find dead bodies with loot
        dead = [t for t in game_engine_ref.tributes if not t.alive and t.inventory]
        if not dead: return f"{format_tribute_list(alliance.members)} searches for supplies but finds nothing."
        
        # Pick a body
        body = random.choice(dead)
        item = body.inventory.pop()
        
        # Give to alliance
        if len(alliance.members) == 1: alliance.members[0].inventory.append(item)
        else: alliance.shared_inventory.append(item)
            
        return f"{format_tribute_list(alliance.members)} finds the body of {body.name} and loots a {item.name}."

class AmicableTradeEvent(InterAllianceEvent):
    """
    Intra-Alliance Event: Two members of the SAME group swap/share items.
    """
    def __init__(self):
        super().__init__()
        self.name = "Share Supplies"
        self.tags = ["social", "trade"]
        self.min_size = 2
        self.max_size = 99
        self.weight = 10

    def execute(self, alliance, terrain, game_engine_ref=None):
        if len(alliance.members) < 2: return "Logic error."
        m1, m2 = random.sample(alliance.members, 2)
        
        item_m1 = get_tradable_item(m1)
        item_m2 = get_tradable_item(m2)
        
        if item_m1 and item_m2:
            # Swap
            m1.inventory.append(item_m2)
            m2.inventory.append(item_m1)
            return f"{m1.name} and {m2.name} trade supplies, swapping {item_m1.name} for {item_m2.name}."
        elif item_m1:
            # m1 -> m2
            m2.inventory.append(item_m1)
            return f"{m1.name} gives {item_m1.name} to {m2.name}."
        elif item_m2:
            # m2 -> m1
            m1.inventory.append(item_m2)
            return f"{m2.name} gives {item_m2.name} to {m1.name}."
            
        return f"{m1.name} and {m2.name} discuss their inventory but have nothing to part with."

class TenseTradeEvent(InterAllianceEvent, CombatEvent):
    """
    Inter-Alliance Event: Two DIFFERENT groups meet to trade. Can go wrong (Ambush).
    """
    def __init__(self):
        super().__init__()
        self.name = "Tense Trade"
        self.tags = ["social", "trade", "combat"]
        self.min_size = 1
        self.max_size = 99
        self.weight = 8

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Error"
        targets = self.get_valid_targets(alliance, game_engine_ref)
        if not targets: return f"{format_tribute_list(alliance.members)} travels alone."
        
        target = random.choice(targets)
        
        # Ambush Check
        aggro = sum(t.stats.get('aggression', 5) for t in alliance.members) / len(alliance.members)
        if aggro > 7 and random.random() < 0.5:
             return f"A trade deal goes wrong! {self.resolver.resolve_fight(alliance, target, terrain, game_engine_ref)}"

        # Trade Logic
        my_item = get_tradable_item(alliance.members[0])
        their_item = get_tradable_item(target.members[0])
        
        if my_item and their_item:
            alliance.members[0].inventory.append(their_item)
            target.members[0].inventory.append(my_item)
            return f"{format_tribute_list(alliance.members)} trades {my_item.name} for {their_item.name} with {format_tribute_list(target.members)}."

        return f"{format_tribute_list(alliance.members)} meets {format_tribute_list(target.members)} to trade, but talks break down."

class BetrayalEvent(ComplexEvent):
    """
    Complex Event: A member turns on their own alliance.
    Trigger: High aggression, Group size > 1.
    """
    def __init__(self):
        super().__init__()
        self.name = "Betrayal"
        self.tags = ["betrayal", "combat", "death"]
        self.min_size = 2
        self.max_size = 10
        self.weight = 5

    def execute(self, alliance, terrain, game_engine_ref=None):
        # 1. Identify a potential traitor (High Aggression)
        traitor = None
        for t in alliance.members:
            if t.stats['aggression'] > 7 and random.random() < 0.3:
                traitor = t
                break
        
        if not traitor:
            return f"{format_tribute_list(alliance.members)} argues heatedly but stays together."

        # 2. Identify a victim (someone else)
        potential_victims = [m for m in alliance.members if m != traitor]
        victim = random.choice(potential_victims)

        # 3. Resolve the stab
        # If victim is sleeping or low defense, they die instantly
        if victim.health < 30 or victim.get_effective_stat('defense') < traitor.get_effective_stat('strength'):
            victim.change_health(-999)
            
            # Traitor steals their items
            traitor.inventory.extend(victim.inventory)
            victim.inventory = []
            
            # Traitor leaves the alliance
            alliance.members.remove(traitor)
            if game_engine_ref:
                from .models import Alliance
                game_engine_ref.pending_new_alliances.append(Alliance([traitor]))

            return f"BETRAYAL! {traitor.name} stabs {victim.name} in the back and flees with their supplies!"
        
        else:
            # Failed attempt
            victim.change_health(-20)
            return f"{traitor.name} tries to kill {victim.name} in their sleep, but {victim.name} wakes up in time to fight them off!"

class SmartSponsorEvent(ComplexEvent):
    """
    Sponsors analyze the tribute's needs and send exactly what is required.
    """
    def __init__(self):
        super().__init__()
        self.name = "Smart Sponsor"
        self.tags = ["sponsor"]
        self.min_size = 1
        self.max_size = 6
        self.weight = 5

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Nothing happens."
        tribute = random.choice(alliance.members)
        gift = None
        message = ""

        # Check Needs
        if tribute.health < 40 or tribute.injured:
            gift = game_engine_ref.create_item_from_name("Medkit")
            message = "medicine to heal their wounds"
        elif tribute.poisoned:
            gift = game_engine_ref.create_item_from_name("Antidote") # Assuming you have this or generic
            if not gift.name: gift = game_engine_ref.create_item_from_name("Medical Supplies")
            message = "an antidote"
        elif not any(i.kind == 'weapon' for i in tribute.inventory):
             # Try to give them their proficient weapon
             weapon_name = tribute.proficient_items[0] if tribute.proficient_items else "Knife"
             gift = game_engine_ref.create_item_from_name(weapon_name)
             message = f"a {gift.name}"
        elif not any(i.kind == 'food' for i in tribute.inventory):
             gift = game_engine_ref.create_item_from_name("Fresh Food")
             message = "a hot meal"

        if gift:
            tribute.inventory.append(gift)
            return f"Sponsors see {tribute.name} struggling and parachute in {message}."
        
        return f"{tribute.name} looks to the sky for help, but receives nothing."
    
class DefectionEvent(InterAllianceEvent):
    """
    Inter-Alliance: One group convinces a member of another group to switch sides.
    """
    def __init__(self):
        super().__init__()
        self.name = "Defection"
        self.tags = ["social", "betrayal"]
        self.weight = 4 

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Nothing happens."
        
        # 1. Find a target group
        targets = self.get_valid_targets(alliance, game_engine_ref)
        if not targets: return f"{format_tribute_list(alliance.members)} tries to recruit allies but finds no one."
        target_alliance = random.choice(targets)
        
        # 2. Pick the Persuader and the Potential Defector
        persuader = max(alliance.members, key=lambda t: t.get_effective_stat('intel'))
        defector = min(target_alliance.members, key=lambda t: t.get_effective_stat('aggression'))
        
        # 3. Skill Check: Intel vs Aggression/Loyalty
        score_a = persuader.get_effective_stat('intel') + random.randint(1, 10)
        score_b = defector.get_effective_stat('aggression') + 5 # Base loyalty bonus
        
        if score_a > score_b:
            # SUCCESS: Switch Sides
            target_alliance.members.remove(defector)
            alliance.add_member(defector)
            
            return f"{persuader.name} convinces {defector.name} to abandon their allies and join {format_tribute_list(alliance.members)}!"
            
        return f"{persuader.name} tries to convince {defector.name} to defect, but is rebuffed."

class WildfireEvent(ComplexEvent):
    """
    Complex Event: A fire forces a speed check. 
    Fast characters are safe; slow characters take damage or are rescued.
    """
    def __init__(self):
        super().__init__()
        self.name = "Wildfire Escape"
        self.tags = ["gamemaker", "disaster", "fire"]
        self.weight = 5

    def execute(self, alliance, terrain, game_engine_ref=None):
        # 1. Sort by Speed
        sorted_members = sorted(alliance.members, key=lambda t: t.get_effective_stat('speed'), reverse=True)
        
        fastest = sorted_members[0]
        slowest = sorted_members[-1]
        
        if len(alliance.members) == 1:
            if fastest.get_effective_stat('speed') > 4:
                return f"A wildfire erupts! {fastest.name} outruns the flames."
            else:
                fastest.change_health(-25)
                return f"A wildfire erupts! {fastest.name} isn't fast enough and gets badly burned."

        # Group Scenario
        if slowest.get_effective_stat('speed') < 5:
            # Slowest is in trouble.
            # Brave/Good characters (Low aggression) might save.
            if fastest.stats['aggression'] < 6:
                fastest.change_health(-10) # Takes a hit to save friend
                return f"A wildfire chases the group! {fastest.name} doubles back to carry {slowest.name} to safety, getting singed in the process."
            else:
                slowest.change_health(-40) # Left behind
                if not slowest.alive:
                    return f"A wildfire chases the group! {fastest.name} leaves {slowest.name} behind to be consumed by the flames."
                return f"A wildfire chases the group! {slowest.name} barely survives the flames while the others run ahead."
        
        return f"A wildfire erupts, but {format_tribute_list(alliance.members)} are fast enough to escape unharmed."

class SabotageEvent(InterAllianceEvent):
    """
    Inter-Alliance: Sneak into a camp and destroy supplies.
    """
    def __init__(self):
        super().__init__()
        self.name = "Sabotage"
        self.tags = ["stealth", "sabotage"]
        self.weight = 6

    def execute(self, alliance, terrain, game_engine_ref=None):
        if not game_engine_ref: return "Nothing happens."
        
        targets = self.get_valid_targets(alliance, game_engine_ref)
        if not targets: return f"{format_tribute_list(alliance.members)} plans a sabotage mission but finds no targets."
        target_alliance = random.choice(targets)
        
        # Skill Check
        saboteur = max(alliance.members, key=lambda t: t.get_effective_stat('stealth'))
        
        # Stealth vs Intel
        if saboteur.get_effective_stat('stealth') + random.randint(1,10) > 12:
            # Success: Find food or weapons to destroy
            destroyed = []
            
            # Check Target Inventory
            # We target shared inventory first as it represents the "camp stockpile"
            if target_alliance.shared_inventory:
                # Destroy up to 4 items
                to_destroy = target_alliance.shared_inventory[:4]
                for item in to_destroy:
                    target_alliance.shared_inventory.remove(item)
                    destroyed.append(item.name)
            
            # If no shared, try personal
            elif target_alliance.members[0].inventory:
                 item = target_alliance.members[0].inventory.pop()
                 destroyed.append(item.name)

            if destroyed:
                names = ", ".join(destroyed)
                return f"{saboteur.name} sneaks into {format_tribute_list(target_alliance.members)}'s camp and destroys their {names}!"
            else:
                return f"{saboteur.name} infiltrates {format_tribute_list(target_alliance.members)}'s camp but they have nothing worth destroying."

        return f"{saboteur.name} attempts to sabotage {format_tribute_list(target_alliance.members)} but is forced to retreat."
    
class MiracleHealEvent(ComplexEvent):
    """
    Complex: A high-intel character heals a critically injured ally using nature.
    """
    def __init__(self):
        super().__init__()
        self.name = "Miracle Heal"
        self.tags = ["medical", "social"]
        self.min_size = 2 # Need healer and patient
        self.weight = 6

    def execute(self, alliance, terrain, game_engine_ref=None):
        # 1. Find a Medic (Intel > 7)
        medic = next((m for m in alliance.members if m.stats['intel'] >= 7), None)

        # 2. Find a Patient (Health < 30 or Injured/Poisoned)
        patient = next((m for m in alliance.members if m != medic and (m.health < 40 or m.injured or m.poisoned)), None)
        
        if not medic and not patient:
            return f"{format_tribute_list(alliance.members)} looks for a way to heal, but no one has the knowledge."
        elif not medic and patient:
            return f"{patient.name} is gravely ill, but no one knows how to help them."
        elif medic and not patient:
            return f"{medic.name} gathers medicinal herbs, just in case."
        elif medic and patient:
            # 3. Perform Heal
            patient.health = min(patient.max_health, patient.health + 25)
            patient.injured = False
            patient.poisoned = False
            
            return f"{patient.name} is on the brink of death, but {medic.name} manages to stabilize them using medicinal plants found nearby."

class EventManager:
    """
    The Brain that picks events.
    """
    def __init__(self) -> None:
        self.events = []
        # Register Classes
        self.events.extend([
            ScavengeEvent(), AmicableDisbandEvent(), FormAllianceEvent(), CombatEvent(), 
            CorpseLootEvent(), AmicableTradeEvent(), TenseTradeEvent(), 
            ThiefEvent(), RiskyTheftEvent(), SpyEvent(), 
            ForceSplitEvent(), ExtinctionPreventionEvent(), BloodbathEvent(), FeastEvent(),
            BetrayalEvent(), SmartSponsorEvent(), DefectionEvent(), WildfireEvent(), SabotageEvent(), MiracleHealEvent()
        ])
        self.load_json_events()

    def load_json_events(self) -> None:
        path = os.path.join(os.path.dirname(__file__), 'data', 'events.json')
        if not os.path.exists(path): return
        with open(path, 'r') as f:
            data = json.load(f)
        for e_data in data:
            if e_data.get("type") == "interaction": self.events.append(InterAllianceEvent(e_data))
            else: self.events.append(SimpleEvent(e_data))

    def select_event(self, alliance, terrain, day=1):
        """
        Weighted Random Selection based on Terrain and Group Size.
        """
        valid = [e for e in self.events if e.check_conditions(alliance, terrain)]
        if not valid: return None
        weights = [e.get_adjusted_weight(terrain, day) for e in valid]
        return random.choices(valid, weights=weights, k=1)[0]