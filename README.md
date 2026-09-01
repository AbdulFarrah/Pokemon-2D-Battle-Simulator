# Pokémon 2D Battle Simulator

A 2D Pokémon battle simulator built with **Python and Pygame**, featuring single-player battles against the computer, local two-player battles, and TCP-based online multiplayer.

The project includes a data-generation pipeline that retrieves Pokémon and move information from the web and builds the JSON and image data used by the game.

## Features

- 2D Pokémon battle interface built with Pygame
- Player vs Computer (`PvC`)
- Local Player vs Player (`PvP`)
- Online Player vs Player (`Online`)
- Pokémon selection by generation
- Support for selecting different party sizes
- Support for selecting different move sizes
- Pokémon stats, types, abilities, moves, and evolutions
- Pokémon switching during battle
- Move effects and battle mechanics
- Special multi-turn moves
- Healing moves
- HP-draining moves
- Pokémon fainting and automatic/manual switching
- Battle animations and visual effects
- Team summary screens
- Restart option after completing a battle
- TCP socket-based online communication
- Automatic Pokémon image generation
- Scripts for updating the Pokémon and move datasets

---

## Requirements

### Operating System

The project was originally developed and tested on **Windows**.

The game can be run directly using Windows Python.

### Python

The development environment used for this project is:

```text
Python 3.13.1
```

Check your installed version with:

```powershell
python --version
```

or:

```powershell
py --version
```

### Python packages

The game itself requires:

```text
pygame
```

The data-generation scripts additionally require:

```text
requests
beautifulsoup4
```

Install the dependencies with:

```powershell
python -m pip install pygame requests beautifulsoup4
```

If you also want to build the standalone Windows executable, install PyInstaller:

```powershell
python -m pip install pyinstaller
```

---

## Running the Game from Source

Clone the repository and enter the project directory:

```powershell
git clone <your-repository-url>
cd Pokemon-2D-Battle-Simulator
```

Install the required packages:

```powershell
python -m pip install pygame requests beautifulsoup4
```

Then run:

```powershell
python main.py
```

Running `main.py` directly is recommended during development because the program's debug information is printed to the terminal.

---

## Window Size

The default Pygame window is:

```text
1300 × 650
```

The dimensions are configured near the beginning of `src/base.py`:

```python
def run_ui_setup():
    import pygame
    from src.online_setup import online_setup
    
    pygame.init()
    WIDTH, HEIGHT = 1300, 650
    #WIDTH, HEIGHT = 800, 600
```

To change the game window size, modify:

```python
WIDTH, HEIGHT = 1300, 650
```

For example:

```python
WIDTH, HEIGHT = 800, 600
```

The rest of the game obtains the active screen dimensions dynamically, so changing these values changes the size used by the UI.

---

## Game Modes

### Player vs Computer

`PvC` allows one player to battle against the computer-controlled opponent.

The computer opponent is automatically assigned the name:

```text
RED
```

The computer selects Pokémon and performs battle actions automatically.

### Local Player vs Player

`PvP` allows two players to play on the same computer.

Both players enter their names before configuring the battle.

The game prevents both players from using the same name during setup.

### Online Multiplayer

`Online` uses a direct TCP socket connection between two players.

One player acts as the **host**, while the other acts as the **client**.

The game uses:

```text
TCP port 5000
```

The host starts a server and receives an invite code derived from the host's IP address.

The second player enters that invite code to connect.

---

## Online Multiplayer Networking

The online mode uses Python's built-in `socket` module.

The host:

1. Opens a TCP server on port `5000`.
2. Waits for a player to connect.
3. Displays an invite code.
4. Accepts the incoming connection.
5. Exchanges player and battle information with the client.

The client:

1. Enters the host's invite code.
2. Converts the code back into an IP address.
3. Connects to the host on TCP port `5000`.
4. Exchanges the required battle information.

### Same-LAN Play

The online mode is primarily suited to situations where the two computers can directly reach each other over the network.

For two computers on the same LAN, the host's local IP address can normally be used by the client through the generated invite code, provided that the host firewall allows incoming TCP connections on port `5000`.

### Different Networks

The project does **not** include a central multiplayer server, relay server, or NAT traversal mechanism.

Therefore, playing between separate networks requires the host computer to be reachable from the client.

Depending on the network configuration, this can require:

- TCP port `5000` to be allowed by the host's firewall
- Router/NAT configuration
- Port forwarding from the host's router to the host computer
- A reachable address for the client to connect to

Simply sharing the invite code is not sufficient if the host is behind a network that does not permit the incoming connection.

---

## Data Pipeline

The repository includes scripts for maintaining the Pokémon and move datasets.

The intended data flow is:

```text
Pokémon data source
        │
        ▼
pokemon_fetcher.py
        │
        ▼
pokemon.json
        │
        ▼
move_fetcher.py
        │
        ▼
data.json
        │
        ▼
image_fetcher.py
        │
        ├──► Pokémon PNG images
        │
        └──► gallery.html
```

These scripts are useful when updating the game's Pokémon database rather than manually maintaining every Pokémon entry and image.

---

## Pokémon Data

`data/pokemon.json` contains the Pokémon records used by the game.

The generated records include information such as:

- Pokémon name
- Generation
- Types
- Abilities
- Base HP
- Attack
- Defense
- Special Attack
- Special Defense
- Speed
- Next evolutions
- Learnable moves
- Encoded Pokémon image data

The Pokémon fetcher checks the National Pokédex for Pokémon that are not already present in `pokemon.json` and fetches the missing records.

The current generation mapping in the fetcher covers Pokémon generations through **Generation 9**.

### Updating Pokémon Data

The fetcher scripts use the current working directory when opening their JSON files.

Because the scripts are located inside `data/`, run them from that directory:

```powershell
cd data
python pokemon_fetcher.py
```

The script checks the National Pokédex for missing Pokémon and adds newly discovered entries to:

```text
data/pokemon.json
```

---

## Move Data

`data/data.json` contains the move information used by the battle system.

The move data includes fields such as:

- Move name
- Type
- Category
- Contest type
- PP
- Power
- Accuracy
- Generation
- Internal move index

`move_fetcher.py` compares the moves referenced by `pokemon.json` against the existing move dataset and fetches missing move information.

Run it from the `data/` directory:

```powershell
cd data
python move_fetcher.py
```

If missing moves are found, they are added to:

```text
data/data.json
```

---

## Pokémon Images

The game requires Pokémon images during gameplay.

Instead of committing a potentially large collection of generated Pokémon image files to the repository, the project stores encoded image data inside the Pokémon records and provides `image_fetcher.py` to generate the PNG files.

Run:

```powershell
cd data
python image_fetcher.py
```

The generated images are placed in:

```text
data/Images/
```

The game loads the generated Pokémon images from that directory.

The only image intended to remain directly in the repository's `data/Images/` directory is:

```text
background.png
```

The generated Pokémon PNG files can be recreated using the data-generation pipeline.

---

## Recommended Data Update Order

When rebuilding/updating the dataset, use the scripts in this order:

```text
1. pokemon_fetcher.py
          ↓
2. move_fetcher.py
          ↓
3. image_fetcher.py
```

From the project root:

```powershell
cd data

python pokemon_fetcher.py
python move_fetcher.py
python image_fetcher.py
```

This keeps the Pokémon dataset, move dataset, and generated images synchronized.

`image_fetcher.py` can also generate a Pokémon HTML gallery from the available Pokémon data and generated images.

---

## Project Structure

The recommended repository structure is:

```text
Pokemon-2D-Battle-Simulator/
│
├── assets/
│   └── Poké_Ball.ico
│
├── data/
│   ├── Images/
│   │   └── background.png
│   │
│   ├── data.json
│   ├── pokemon.json
│   │
│   ├── image_fetcher.py
│   ├── move_check.py
│   ├── move_fetcher.py
│   └── pokemon_fetcher.py
│
├── src/
│   ├── __init__.py
│   ├── base.py
│   ├── damage.py
│   ├── game.py
│   ├── move.py
│   ├── online_setup.py
│   ├── player.py
│   ├── pokemon.py
│   ├── restart.py
│   ├── type.py
│   └── utils.py
│
├── main.py
├── application command.txt
└── README.md
```

### Main Components

#### `main.py`

Application entry point.

It initializes Pygame, starts the UI setup, creates the `Game` instance, runs the battle loop, handles connection cleanup, and provides the restart flow.

#### `src/base.py`

Contains the initial graphical user interface and game setup flow.

It handles:

- Game mode selection
- Online host/client selection
- Player names
- Generation selection
- Party size selection
- Move size selection
- Setup summary

#### `src/game.py`

Contains the main battle system.

It handles:

- Pokémon loading
- Move loading
- Pokémon selection
- Team setup
- Battle turns
- Player actions
- Computer actions
- Damage resolution
- Pokémon switching
- Fainting
- Battle animations
- Online battle communication
- Connection monitoring
- Battle UI

#### `src/player.py`

Contains player-related state and behavior.

#### `src/pokemon.py`

Contains the Pokémon object used by the battle system.

#### `src/move.py`

Contains the move representation used by Pokémon.

#### `src/damage.py`

Contains the battle damage calculation logic.

#### `src/type.py`

Contains Pokémon type relationships and type-effectiveness information.

#### `src/online_setup.py`

Handles online multiplayer connection setup using TCP sockets.

#### `src/restart.py`

Provides the post-battle restart/exit interface.

#### `src/utils.py`

Contains small utility functionality shared by the project.

---

## Controls

The game is primarily operated through the Pygame graphical interface using the mouse.

During Pokémon selection:

- **Left mouse button** — Select a Pokémon
- **Up arrow** — Scroll upward through the Pokémon list
- **Down arrow** — Scroll downward through the Pokémon list
- **Mouse wheel** — Scroll through the Pokémon list

During battle, actions are selected through the on-screen buttons.

The primary battle actions are:

```text
Fight
Switch
List
Exit
```

Selecting `Fight` leads to move selection.

Selecting `Switch` allows the player to choose another available Pokémon.

`List` displays the player's Pokémon.

`Exit` ends the current battle.

---

## Building a Windows Executable

The project includes a PyInstaller command for producing a standalone Windows executable.

Install PyInstaller:

```powershell
python -m pip install pyinstaller
```

Run the following command from the project root:

```powershell
pyinstaller --onefile --windowed --name pokemon_ONLINE_Game --icon=assets/Poké_Ball.ico --add-data "data/pokemon.json;data" --add-data "data/data.json;data" --add-data "data/Images;data/Images" --add-data "src;src" main.py
```

### What the command does

```text
--onefile
```

Creates a single executable.

```text
--windowed
```

Runs the application without opening a console/terminal window.

```text
--name pokemon_ONLINE_Game
```

Sets the executable name.

```text
--icon=assets/Poké_Ball.ico
```

Uses the Pokémon ball icon for the executable.

```text
--add-data "data/pokemon.json;data"
```

Packages the Pokémon dataset.

```text
--add-data "data/data.json;data"
```

Packages the move dataset.

```text
--add-data "data/Images;data/Images"
```

Packages the runtime image directory.

```text
--add-data "src;src"
```

Includes the project's source package and its required runtime files.

```text
main.py
```

Specifies the application entry point.

---

## PyInstaller Output

PyInstaller creates build artifacts such as:

```text
build/
dist/
pokemon_ONLINE_Game.spec
```

The executable is generated inside:

```text
dist/
```

For example:

```text
dist/pokemon_ONLINE_Game.exe
```

The `build/` directory and `.spec` file are build artifacts for this project and do not need to be committed to the source repository unless you specifically want to preserve a custom PyInstaller build configuration.

---

## Debugging

When running:

```powershell
python main.py
```

debug messages printed using `print()` are visible in the terminal.

The game contains various `[DEBUG]` messages that can help diagnose battle flow, player actions, Pokémon switching, and online communication.

For example:

```text
[DEBUG] Starting game loop.
[DEBUG] Awaiting Player1 input...
```

### Packaged Executable

The PyInstaller command uses:

```text
--windowed
```

Therefore, the packaged `.exe` does **not** open a terminal window.

As a result, `print()`-based debug output will not be visible when launching:

```text
pokemon_ONLINE_Game.exe
```

If you need to see debug output while developing or troubleshooting, run:

```powershell
python main.py
```

directly instead of using the packaged executable.

---

## Runtime Resources

The game loads its runtime resources using paths that support both normal Python execution and PyInstaller's bundled application environment.

The required runtime data includes:

```text
data/pokemon.json
data/data.json
data/Images/
```

The Pokémon image files must exist in `data/Images/` for Pokémon whose images are displayed by the game.

The data-generation scripts can be used to recreate those generated images.

---

## Development Notes

This project was originally developed as a personal 2D Pokémon battle simulator using Python and Pygame.

The codebase contains both the playable game and the scripts used to build and maintain the game's Pokémon/move data.

The data-fetching scripts rely on the structure of the upstream Pokémon Database pages they parse. Changes to the upstream website may require corresponding changes to the parsers.

The Pokémon fetcher currently contains generation-specific mapping logic for the generations represented by the project, with Generation 9 being the latest generation explicitly mapped in the current implementation.

---

## No License

This repository intentionally does not include a license.

---

## Repository

**Repository name:**

```text
Pokemon-2D-Battle-Simulator
```