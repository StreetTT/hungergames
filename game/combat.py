import random
from typing import LiteralString
from .models import Tribute, Terrain, Alliance, format_tribute_list

class CombatResolver:
    """
    Handles the math for fights.
    """
    def __init__(self) -> None:
        pass

    def resolve_fight(self, attacker_alliance: Alliance, defender_alliance: Alliance, terrain: Terrain) -> str:
        """
        Main entry point.
        Calculates outcome based on members AND shared inventory of the alliances.
        """
        attackers = attacker_alliance.members
        defenders = defender_alliance.members
        def_names = format_tribute_list(defenders)
        att_names = format_tribute_list(attackers)

        # 1. ESCAPE PHASE
        # Check if defenders can run away
        if self._attempt_escape(attackers, defenders, terrain):
            return f"{def_names} managed to outrun {att_names}!"

        # 2. BATTLE PHASE
        # Pass the full alliance to access shared inventory
        att_score = self._calculate_group_power(attacker_alliance, "attack")
        def_score = self._calculate_group_power(defender_alliance, "defense")

        # 3. RESOLUTION
        margin = att_score - def_score
        
        if margin > 0:
            return self._apply_outcome(winners=attacker_alliance, losers=defender_alliance, margin=margin)
        elif margin < 0:
            return self._apply_outcome(winners=defender_alliance, losers=attacker_alliance, margin=abs(margin))
        else:
            return f"{att_names} clashes with {def_names}, but neither side gains the upper hand. Both retreat tired."

    def _attempt_escape(self, attackers: list[Tribute], defenders: list[Tribute], terrain: Terrain) -> bool:
        """
        Compare average speeds. Returns True if defenders escape.
        """
        # Calculate average speed of groups
        if not attackers or not defenders: return False
        
        avg_speed_att = sum(t.get_effective_stat('speed') for t in attackers) / len(attackers)
        avg_speed_def = sum(t.get_effective_stat('speed') for t in defenders) / len(defenders)

        # For simplicity: If terrain has 'stealth' tag, boost escape chance
        escape_bonus = 0
        if terrain.get_multiplier(["stealth"]) > 1.0:
            escape_bonus = 2

        # Roll for variance (-3 to +3)
        roll = random.randint(-3, 3)
        
        # Defender needs higher speed + variance
        return (avg_speed_def + escape_bonus + roll) > avg_speed_att

    def _calculate_group_power(self, alliance: Alliance, mode: str) -> float:
        """
        Sum of stats + Item Bonuses (Personal & Shared) + RNG.
        mode: "attack" or "defense"
        """
        total_power = 0.0
        
        # 1. Member Base Stats + Personal Items
        for t in alliance.members:
            if mode == "attack":
                # Strength + Aggression + small Intel bonus
                base = t.get_effective_stat("strength") + (t.stats["aggression"] * 0.5)
            else:
                # Defense + Speed + small Intel bonus
                base = t.get_effective_stat("defense") + (t.stats["speed"] * 0.5)
            
            # RNG Variance (The "Chaos Factor")
            # A d10 roll equivalent
            variance = random.randint(1, 10)
            total_power += (base + variance)

        # 2. Shared Inventory Bonuses
        # We add the raw stat values from shared items to the group total
        if hasattr(alliance, 'shared_inventory'):
            for item in alliance.shared_inventory:
                if mode == "attack":
                    # Attack power from shared weapons
                    total_power += item.bonuses.get('strength', 0)
                else:
                    # Defense power from shared armor/shields
                    total_power += item.bonuses.get('defense', 0)

        return total_power

    def _apply_outcome(self, winners: Alliance, losers: Alliance, margin: float) -> str:
        """
        Determines who gets hurt/killed based on the victory margin.
        """
        # Identify key actors
        killer = max(winners.members, key=lambda x: x.stats['strength'])
        victim = min(losers.members, key=lambda x: x.health)

        # 1. Calculate Damage
        # Higher margin = more damage.
        damage = 15 + (margin * 2) 
        
        # 2. Lethality Check (Aggression)
        # If the killer is aggressive, they might finish the job even if damage wasn't fatal
        is_fatal = False
        victim.change_health(-damage)
        
        if not victim.alive:
            is_fatal = True
        elif killer.stats['aggression'] > 7 and random.random() < 0.5:
             # Execution move
             victim.change_health(-999) 
             is_fatal = True

        # 3. Looting
        loot_text = ""
        stolen = None
        
        # Try stealing from personal inventory
        if is_fatal and victim.inventory:
            stolen = victim.inventory.pop()
        # Else try stealing from shared inventory
        elif is_fatal and losers.shared_inventory:
            stolen = losers.shared_inventory.pop()
            
        if stolen:
            # If solo, personal; if group, shared
            if len(winners.members) == 1:
                killer.inventory.append(stolen)
            else:
                winners.shared_inventory.append(stolen)
            loot_text = f" {killer.name} steals {stolen.name}."

        if is_fatal:
            killer.kills.append(victim.name)
            return f"{killer.name} overpowers {victim.name} and kills {victim.him_her}!{loot_text}"
        else:
            victim.injured = True
            return f"{killer.name} beats {victim.name} severely, but leaves {victim.him_her} alive."