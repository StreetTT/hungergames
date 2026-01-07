import random
from typing import Any
from .models import Tribute, Terrain, Alliance, format_tribute_list

class CombatResolver:
    """
    Handles the math for fights.
    """
    def __init__(self) -> None:
        pass

    def resolve_fight(self, attacker_alliance: Alliance, defender_alliance: Alliance, terrain: Terrain, game_engine: Any = None) -> str:
        """
        Main entry point.
        Calculates outcome based on members AND shared inventory of the alliances.
        """
        # Context string for text generation
        att_names = format_tribute_list(attacker_alliance.members)
        
        # 1. INDIVIDUAL ESCAPE PHASE
        escaped_names = []
        
        # Iterate over a copy so we can modify the original list safely
        for defender in list(defender_alliance.members):
            if self._attempt_individual_escape(defender, attacker_alliance.members, terrain):
                # Remove from current group
                defender_alliance.members.remove(defender)
                
                # Create new solo alliance for the escapee so they remain in the game
                if game_engine:
                    from .models import Alliance 
                    new_group = Alliance([defender])
                    # They flee with their personal inventory, but leave shared items behind
                    game_engine.pending_new_alliances.append(new_group)
                
                escaped_names.append(defender.name)

        log_parts = []

        if escaped_names:
            esc_str = ", ".join(escaped_names)
            log_parts.append(f"{esc_str} broke rank and fled from {att_names}")

        # Check if anyone is left to fight
        if not defender_alliance.members:
            # Everyone fled, fight over.
            return "; ".join(log_parts)

        # 2. BATTLE PHASE
        att_score = self._calculate_group_power(attacker_alliance, "attack")
        def_score = self._calculate_group_power(defender_alliance, "defense")

        # 3. RESOLUTION
        margin = att_score - def_score
        
        if margin > 0:
            outcome = self._apply_outcome(winners=attacker_alliance, losers=defender_alliance, margin=margin)
            log_parts.append(outcome)
        elif margin < 0:
            # Note: Defenders win implies they successfully repelled the attack
            outcome = self._apply_outcome(winners=defender_alliance, losers=attacker_alliance, margin=abs(margin))
            log_parts.append(outcome)
        else:
            log_parts.append("the two groups clash, but neither side gains the upper hand")
            
        return "; ".join(log_parts)

    def _attempt_individual_escape(self, defender: Tribute, attackers: list[Tribute], terrain: Terrain) -> bool:
        """
        Compare defender speed vs average attacker speed.
        """
        if not attackers: return True
        
        avg_speed_att = sum(t.get_effective_stat('speed') for t in attackers) / len(attackers)
        def_speed = defender.get_effective_stat('speed')

        escape_bonus = 0
        if terrain.get_multiplier(["stealth"]) > 1.0:
            escape_bonus = 2
            
        # Cowardice check: high stealth/speed chars are more likely to attempt run
        if def_speed > avg_speed_att:
            escape_bonus += 2

        roll = random.randint(-5, 5)
        return (def_speed + escape_bonus + roll) > (avg_speed_att + 2)

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
        Can result in multiple deaths.
        """
        # 1. Winners take chip damage
        for w in winners.members:
            chip_dmg = random.randint(1, 5)
            w.change_health(-chip_dmg)

        # 2. Identify key killer (for flavor text)
        killer = max(winners.members, key=lambda x: x.stats['strength'])
        winner_names = format_tribute_list(winners.members)
        
        # 3. Apply Damage to Losers
        # Damage is distributed, but tailored so high margin = probable wipes
        
        deaths = []
        injured = []
        
        # Base damage that everyone on losing side takes
        base_damage = 10 + (margin * 0.5)
        
        # Loop through a copy of losers
        for victim in list(losers.members):
            # Variance: Some take more damage than others
            personal_dmg = base_damage + random.randint(0, 15)
            victim.change_health(-personal_dmg)
            
            # Execution Chance (Aggressive winners finish off weak losers)
            if victim.alive and killer.stats['aggression'] > 7 and margin > 20 and random.random() < 0.4:
                victim.change_health(-999)
            
            if not victim.alive:
                deaths.append(victim.name)
                # Looting: Killer takes 1 item per kill
                stolen_item = None
                if victim.inventory:
                    stolen_item = victim.inventory.pop()
                elif hasattr(losers, 'shared_inventory') and losers.shared_inventory:
                    stolen_item = losers.shared_inventory.pop()
                
                if stolen_item:
                    if len(winners.members) == 1: winners.members[0].inventory.append(stolen_item)
                    else: winners.shared_inventory.append(stolen_item)
                
                # Record kill
                killer.kills.append(victim.name)
            else:
                victim.injured = True
                injured.append(victim.name)

        # 4. Construct Text
        parts = []
        if deaths:
            dead_str = ", ".join(deaths)
            if len(winners.members) > 1:
                parts.append(f"{killer.name} leads {winner_names} in a brutal assault, killing {dead_str}")
            else:
                parts.append(f"{killer.name} performs a brutal assault, killing {dead_str}")
        
        if injured:
            inj_str = ", ".join(injured)
            parts.append(f"{winner_names} defeats {inj_str} but spares them, leaving them bleeding")
            
        if not parts:
            parts.append(f"{winner_names} overpowers the enemy, forcing them to retreat")

        return "; ".join(parts)