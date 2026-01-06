import random
from typing import LiteralString
from .models import Tribute, Terrain

class CombatResolver:
    """
    Handles the math for fights.
    Separated from Events to keep code clean.
    """
    def __init__(self) -> None:
        pass

    def resolve_fight(self, attackers: list[Tribute], defenders: list[Tribute], terrain: Terrain) -> str:
        """
        Main entry point.
        Returns: String (Log text describing the result)
        """
        # 1. ESCAPE PHASE
        # Check if defenders can run away
        if self._attempt_escape(attackers, defenders, terrain):
            names = ", ".join([t.name for t in defenders])
            return f"{names} managed to outrun the attackers!"

        # 2. BATTLE PHASE
        # Calculate raw power scores
        att_score = self._calculate_group_power(attackers, "attack")
        def_score = self._calculate_group_power(defenders, "defense")

        # 3. RESOLUTION
        margin = att_score - def_score
        
        if margin > 0:
            # Attackers Win
            return self._apply_outcome(winners=attackers, losers=defenders, margin=margin)
        elif margin < 0:
            # Defenders Win (Counter-attack)
            return self._apply_outcome(winners=defenders, losers=attackers, margin=abs(margin))
        else:
            # Tie
            return "The two groups clash, but neither side gains the upper hand. They retreat tired."

    def _attempt_escape(self, attackers, defenders, terrain) -> bool:
        """
        Compare average speeds. Returns True if defenders escape.
        """
        # Calculate average speed of groups
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

    def _calculate_group_power(self, group, mode) -> float:
        """
        Sum of stats + Item Bonuses + RNG.
        mode: "attack" or "defense"
        """
        total_power = 0
        
        for t in group:
            # Base Stat
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

        return total_power

    def _apply_outcome(self, winners: list[Tribute], losers: list[Tribute], margin: float) -> str:
        """
        Determines who gets hurt/killed based on the victory margin.
        """
        # Identify key actors
        killer = max(winners, key=lambda x: x.stats['strength'])
        victim = min(losers, key=lambda x: x.health) # Weakest link targeted first

        # 1. Calculate Damage
        # Higher margin = more damage.
        damage = 15 + (margin * 2) 
        
        # 2. Lethality Check (Aggression)
        # If the killer is aggressive, they might finish the job even if damage wasn't fatal
        is_fatal = False
        
        victim.take_damage(damage)
        
        if not victim.alive:
            is_fatal = True
        elif killer.stats['aggression'] > 7 and random.random() < 0.5:
             # Execution move
             victim.take_damage(999) 
             is_fatal = True

        # 3. Looting
        loot_text = ""
        if is_fatal and victim.inventory:
            stolen = victim.inventory.pop()
            killer.inventory.append(stolen)
            loot_text = f" {killer.name} steals their {stolen.name}."

        # 4. Return Text
        if is_fatal:
            killer.kills.append(victim.name)
            return f"{killer.name} overpowers {victim.name} and kills them!{loot_text}"
        else:
            victim.injured = True
            return f"{killer.name} beats {victim.name} severely, but leaves them alive."