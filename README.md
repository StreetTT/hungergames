# 🏹 Hunger Games Simulator

A robust, text-based simulation engine for the Hunger Games written in Python. This project allows you to create custom rosters, design unique arenas, and simulate detailed battle royale scenarios with complex event logic, alliances, and combat systems.

## ✨ Features

* **Interactive Game Manager**: A CLI tool to manage every aspect of the simulation easily.
* **Deep Customization**: Create Tributes with unique stats (Strength, Speed, Intel, etc.) and design Terrains with specific event probabilities (e.g., a "Frozen Wasteland" with high cold damage).
* **Batch Simulation**: Run hundreds of simulations at once to gather statistics on win rates, deadliest tributes, and best items.
* **Event System**: Includes combat, scavenging, crafting, alliances, betrayals, and special events like *The Bloodbath* and *The Feast*.
* **Save/Load System**: Persist your favorite rosters and terrains to JSON files for easy sharing and reuse.

## 📂 Project Structure

* `game_manager.py`: **Main Entry Point.** The interactive CLI for managing games.
* `batch_sim.py`: Script for running mass simulations and generating statistical reports.
* `game/`: Core package containing the simulation logic.
    * `engine.py`: Orchestrates the game loop.
    * `models.py`: Definitions for Tributes, Alliances, and Terrain.
    * `events.py`: Logic for all game events (combat, theft, etc.).
* `app.py`: A lightweight Flask web interface (optional).

## 🚀 Getting Started

### Prerequisites
* Python 3.8 or higher

### Installation

1.  Clone the repository:
    ```bash
    git clone [https://github.com/StreetTT/hungergames.git](https://github.com/StreetTT/hungergames.git)
    cd hunger-games-sim
    ```

2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## 🎮 Usage

### 1. Interactive Game Manager (Recommended)
The Game Manager is the easiest way to interact with the simulator. It allows you to build rosters, configure terrains, and run single games with detailed logs.

```bash
python game_manager.py

```

**Key Menu Options:**

* **Manage Roster**: Create new tributes, edit stats, or load from saved JSON files.
* **Manage Terrain**: Adjust event multipliers (e.g., make "Combat" 2x more likely).
* **Run Simulation**: Watch the game unfold day by day.
* **Post-Game**: View summaries, save replays, or export text reports.

### 2. Batch Simulation

Want to see who wins the most out of 1,000 games? Use the batch simulator to generate a statistical report.

```bash
python batch_sim.py

```

* Reports are saved to the `reports/` directory.
* Tracks win percentages, kill counts, and event frequency.

### 3. Web Interface _[Coming Soon]_

## 🛠️ Customization

### Editing Items and Events

You can modify the base data for the game by editing the JSON files in `game/data/`:

* `items.json`: Add new weapons, food, or utility items.
* `events.json`: (If applicable) Modify or add new simple text events.

### JSON Save Files

Saved Rosters, Terrains, and Game Replays are stored in the root directory folders:

* `tributes/`: Saved Roster presets.
* `terrains/`: Saved Arena configurations.
* `saves/`: Full game state replays.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is open-source and available under the MIT License.