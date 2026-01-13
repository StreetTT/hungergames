from os.path import join, dirname, abspath
from os import makedirs

# Configuration
BASE_DIR = dirname(abspath(__file__))
SAVES_DIR = join(BASE_DIR, "saves")
TRIBUTES_DIR = join(BASE_DIR, "tributes")
TERRAINS_DIR = join(BASE_DIR, "terrains")
DATA_DIR = join(BASE_DIR, "game", "data")

# Ensure folders exist
for path in [SAVES_DIR, TRIBUTES_DIR, TERRAINS_DIR]:
    makedirs(path, exist_ok=True)