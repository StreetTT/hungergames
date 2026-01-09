import random
from typing import Literal, Optional, Union, Any 
from .utils import _get_random_items_from_db

class Item:
    """Represents an object in the game (Weapon, Food, Utility)."""
    def __init__(self, 
                 name: str, 
                 kind: str, 
                 bonuses: Optional[dict[str,float]]=None) -> None:
        self.name = name
        self.kind = kind  # "weapon", "food", "medical", "misc"
        # bonuses example: {'strength': 2, 'defense': 1}
        self.bonuses = bonuses if bonuses else {}

    def to_dict(self)-> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "bonuses": self.bonuses
        }

    @staticmethod
    def from_dict(data) -> "Item":
        return Item(data['name'], data['kind'], data.get('bonuses'))

    def is_critical(self, member: "Tribute") -> bool:
        """Determines if an item is critical for the member based on status."""
        if member.injured and self.bonuses.get('injured', 0) < 0: return True
        if member.poisoned and self.bonuses.get('poisoned', 0) < 0: return True
        if member.health < 40 and self.bonuses.get('health', 0) > 0: return True
        return False

MIN_STAT = 1
MAX_STAT = 15
MIN_MULT = 0.0
MAX_MULT = 5.0

class Tribute:
    """The Player Character."""
    def __init__(self, 
                 name: str, 
                district: int, 
                image_url: Optional[str]=None, 
                stats: Optional[dict[str, float]]=None, 
                proficient_items: Optional[list[str]]=None,
                gender: str = "N") -> None:
        self.name = name
        self.district = district
        self.image_url = image_url
        self.gender = gender
        
        # Core Status
        self.alive: bool = True
        self.health: float = 100
        self.max_health: float = 100
        self.injured: bool = False
        self.poisoned: bool = False 
        
        # Stats (0-10 Scale)
        # Defaulting to 5 if not provided
        if stats == None: stats = {}
        self.stats = {
            "strength": self._clamp(stats.get('strength', 5)),
            "intel": self._clamp(stats.get('intel', 5)),
            "speed": self._clamp(stats.get('speed', 5)),
            "defense": self._clamp(stats.get('defense', 5)),
            "aggression": self._clamp(stats.get('aggression', 5)),
            "stealth": self._clamp(stats.get('stealth', 5))
        }

        self.inventory: list[Item] = []
        self.kills: list[str] = []
        
        # The specific items they are good with (e.g. "Bow")
        self.proficient_items = proficient_items if proficient_items else []
    
    def _clamp(self, value: float) -> float:
        return max(MIN_STAT, min(MAX_STAT, value))

    def modify_stat(self, stat_name: str, amount: float) -> None:
        """Safely modifies a stat within bounds."""
        if stat_name in self.stats:
            new_val = self.stats[stat_name] + amount
            self.stats[stat_name] = self._clamp(new_val)
    
    @property
    def pronouns(self):
        """Returns a dict of pronouns based on gender."""
        if self.gender == 'M':
            return {'subj': 'he', 'obj': 'him', 'pos': 'his'}
        if self.gender == 'F':
            return {'subj': 'she', 'obj': 'her', 'pos': 'her'}
        return {'subj': 'they', 'obj': 'them', 'pos': 'their'}

    @property
    def he_she(self): return self.pronouns['subj']
    
    @property
    def him_her(self): return self.pronouns['obj']
    
    @property
    def his_her(self): return self.pronouns['pos']

    def get_effective_stat(self, stat_name: str)-> float:
        """
        Calculates stat value based on base stats + item bonuses + status effects.
        """
        val = self.stats.get(stat_name, 0)

        # 1. Apply Status Debuffs
        if self.injured:
            val *= 0.8
        if self.poisoned:
            val *= 0.7

        # 2. Apply Item Bonuses
        for item in self.inventory:
            # General stat boost from item
            if stat_name in item.bonuses:
                val += item.bonuses[stat_name]
            
            # Proficiency Bonus: Applies to any stat the item enhances
            if item.name in self.proficient_items and stat_name in item.bonuses and item.bonuses[stat_name] > 0:
                val *= 1.5 # 50% boost for proficiency

        return round(val, 2)

    def change_health(self, amount: float) -> None:
        self.health += amount
        self.health = min(self.max_health, self.health)
        if self.health <= 0:
            self.alive = False
            self.health = 0
    
    def to_dict(self)-> dict[str, Any]:
        """Serialize for JSON export/saving."""
        return {
            "name": self.name,
            "district": self.district,
            "image_url": self.image_url,
            "gender": self.gender,
            "stats": self.stats,
            "proficient_items": self.proficient_items,
            "status": {
                "alive": self.alive,
                "health": self.health,
                "injured": self.injured,
                "poisoned": self.poisoned
            },
            "inventory": [i.to_dict() for i in self.inventory],
            "kills": self.kills
        }

    @staticmethod
    def from_dict(data) -> "Tribute":
        """Load from JSON."""
        t = Tribute(
            name=data['name'], 
            district=data['district'], 
            image_url=data.get('image_url'), 
            stats=data.get('stats'), 
            proficient_items=data.get('proficient_items'),
            gender=data.get('gender', 'N')
        )
        
        # Restore state if loading a save
        if 'status' in data:
            t.alive = data['status']['alive']
            t.health = data['status']['health']
            t.injured = data['status']['injured']
            t.poisoned = data['status']['poisoned']
        
        if 'inventory' in data:
            t.inventory = [Item.from_dict(i) for i in data['inventory']]
            
        return t

class Alliance:
    """Manages groups of Tributes working together."""
    def __init__(self, members: list[Tribute]) -> None:
        self.members = members
        self.shared_inventory: list["Item"] = [] 
        self.merge_inventory()

    @property
    def is_active(self) -> bool:
        # An alliance is valid if it has alive members
        self.members = [m for m in self.members if m.alive]
        return len(self.members) > 0

    def add_member(self, tribute: Tribute) -> None:
        if tribute not in self.members:
            self.members.append(tribute)

    def disband(self) -> list["Alliance"]:
        """Returns a list of new Alliance objects (one per member)."""
        new_groups = [Alliance([m]) for m in self.members]
        self.members = [] # Clear this group
        return new_groups

    def to_dict(self) -> dict[str, list[str]]:
        # We only save member names to link them back on load
        return {
            "members": [t.name for t in self.members]
        }
    
    def merge_inventory(self) -> None:
        for t in self.members:
            if not t.inventory: continue
            self.shared_inventory.extend(t.inventory)
            t.inventory = []



class Terrain:
    """Global Modifier and Item Container."""
    def __init__(self, 
                 name: str, 
                 tag_multipliers: Optional[dict[str,float]]=None,
                 finite_items: Optional[list[Item]]=None,
                 infinite_items: Optional[list[Item]]=None) -> None:
        self.name = name
        
        # Example: {"water": 2.0, "desert": 0.0}
        self.tag_multipliers = {}
        if tag_multipliers:
            for tag, val in tag_multipliers.items():
                # Prevent negative multipliers or crazy high values (e.g., 100x)
                self.tag_multipliers[tag] = max(MIN_MULT, min(MAX_MULT, val))
        
        # If no finite items provided, pick random subset from DB
        if finite_items is not None and len(finite_items) > 0:
            self.finite_items = finite_items
        else:
            # Select 5 to 20 random items
            rng_count = random.randint(5, 20)
            self.finite_items = _get_random_items_from_db(rng_count)

        # If no infinite items provided, pick random subset from DB
        if infinite_items is not None and len(infinite_items) > 0:
            self.infinite_items = infinite_items
        else:
             # Select 2 to 15 random items (make them scarcer than finite pool usually)
            rng_count = random.randint(2, 15)
            self.infinite_items = _get_random_items_from_db(rng_count)

    def get_multiplier(self, tags) -> float:
        """
        Returns the combined probability multiplier for a list of tags.
        E.g., Event tags ["water", "cold"] on "Frozen Lake" terrain.
        """
        total_mult = 1.0
        for tag in tags:
            total_mult *= self.tag_multipliers.get(tag, 1.0)
        return total_mult

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "tag_multipliers": self.tag_multipliers,
            # If it's a string, keep it as string. If it's Item, dict it.
            "finite_items": [i.to_dict() for i in self.finite_items],
            "infinite_items": [i.to_dict() for i in self.infinite_items]
        }
    
    @staticmethod
    def from_dict(data) -> "Terrain":
        # Handle mixed content: Dicts (serialized Items) or Strings
        def parse_list(raw_list):
            parsed = []
            for x in raw_list:
                if isinstance(x, dict):
                    parsed.append(Item.from_dict(x))
                else:
                    # It's a string (or other primitive), keep it as is for the Engine to resolve
                    parsed.append(x)
            return parsed

        return Terrain(
            name=data['name'], 
            tag_multipliers=data.get('tag_multipliers'),
            finite_items=parse_list(data.get('finite_items', [])),
            infinite_items=parse_list(data.get('infinite_items', []))
        )