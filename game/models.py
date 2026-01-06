import random
from typing import Optional, Union, Any 

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


class Tribute:
    """The Player Character."""
    def __init__(self, 
                 name: str, 
                district: int, 
                image_url: Optional[str]=None, 
                stats: Optional[dict[str, float]]=None, 
                proficient_items: Optional[list[str]]=None) -> None:
        self.name = name
        self.district = district
        self.image_url = image_url
        
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
            "strength": stats.get('strength', 5),
            "intel": stats.get('intel', 5),
            "speed": stats.get('speed', 5),
            "defense": stats.get('defense', 5),
            "aggression": stats.get('aggression', 5),
            "stealth": stats.get('stealth', 5)
        }

        self.inventory: list[Item] = []
        self.kills: list[str] = []
        
        # The specific items they are good with (e.g. "Bow")
        self.proficient_items = proficient_items if proficient_items else []

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
            
            # Proficiency Bonus: If using their signature weapon
            # We assume a weapon boosts 'strength' or 'defense' effectively
            if item.name in self.proficient_items and stat_name in ["strength", "defense"]:
                val *= 1.5  # 50% Boost

        return round(val, 2)

    def take_damage(self, amount: float) -> None:
        self.health -= amount
        if self.health <= 0:
            self.alive = False
            self.health = 0
    
    def to_dict(self)-> dict[str, Any]:
        """Serialize for JSON export/saving."""
        return {
            "name": self.name,
            "district": self.district,
            "image_url": self.image_url,
            "stats": self.stats,
            "proficient_item_name": self.proficient_items,
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
            proficient_items=data.get('proficient_items')
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


class Terrain:
    """Global Modifier for Event Probabilities."""
    def __init__(self, name, tag_multipliers: Optional[dict[str,float]]=None) -> None:
        self.name = name
        
        # Example: {"water": 2.0, "desert": 0.0}
        self.tag_multipliers = tag_multipliers if tag_multipliers else {}

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
            "tag_multipliers": self.tag_multipliers
        }
    
    @staticmethod
    def from_dict(data) -> "Terrain":
        return Terrain(data['name'], data.get('tag_multipliers'))