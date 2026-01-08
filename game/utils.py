from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .models import Tribute, Item

def format_tribute_list(tributes: list["Tribute"]) -> str:
    """
    Turns a list of Tribute objects into a readable string.
    ['Katniss', 'Peeta', 'Cato'] -> "Katniss, Peeta and Cato"
    """
    if not tributes:
        return "nobody"
    
    names = [t.name for t in tributes]
    if len(names) == 1:
        return names[0]
    
    return ", ".join(names[:-1]) + f" and {names[-1]}"

def replace_pronouns(text: str, tribute: "Tribute", key: str = "t1") -> str:
    """
    Replaces pronouns based on a key (e.g. 't1', 'e2').
    
    1. Universal Support: {t1} -> {he_t1}, {him_t1}, {his_t1}
    2. Legacy Support: If key matches 'tX', also generates {heX}, {himX}
    """
    replacements = {
        f"{{{key}}}": tribute.name,
        # Universal Underscore Style (e.g. {he_t1}, {he_e2})
        f"{{he_{key}}}": tribute.he_she,
        f"{{him_{key}}}": tribute.him_her,
        f"{{his_{key}}}": tribute.his_her,
        f"{{He_{key}}}": tribute.he_she.capitalize(),
        f"{{Him_{key}}}": tribute.him_her.capitalize(),
        f"{{His_{key}}}": tribute.his_her.capitalize(),
    }
    
    # Legacy Standard (e.g. {t1} -> {he1})
    # Only applies if key starts with 't' and is followed by numbers
    if key.startswith('t') and key[1:].isdigit():
        idx = key[1:]
        replacements.update({
            f"{{he{idx}}}": tribute.he_she,
            f"{{him{idx}}}": tribute.him_her,
            f"{{his{idx}}}": tribute.his_her,
            f"{{He{idx}}}": tribute.he_she.capitalize(),
            f"{{Him{idx}}}": tribute.him_her.capitalize(),
            f"{{His{idx}}}": tribute.his_her.capitalize(),
        })

    for k, v in replacements.items():
        text = text.replace(k, v)
        
    return text

def get_tradable_item(member: "Tribute") -> Optional["Item"]:
    """Returns a tradable item from the member's inventory."""
    firstCritItemFound = False # Flag to track if a critical item has been found
    for i, item in enumerate(member.inventory):
        if item.name not in member.proficient_items \
        and (not item.is_critical(member) or (item.is_critical(member) and firstCritItemFound)):
             return item
    return None