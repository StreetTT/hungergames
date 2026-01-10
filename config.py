import os

# Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVES_DIR = os.path.join(BASE_DIR, "saves")
TRIBUTES_DIR = os.path.join(BASE_DIR, "tributes")
TERRAINS_DIR = os.path.join(BASE_DIR, "terrains")

# Ensure folders exist
for path in [SAVES_DIR, TRIBUTES_DIR, TERRAINS_DIR]:
    os.makedirs(path, exist_ok=True)