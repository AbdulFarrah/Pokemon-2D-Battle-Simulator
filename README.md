# Pokémon 2D Battle Simulator

A Pygame battle game with Player vs Computer, local Player vs Player, and direct TCP online play.

## Requirements

- Python 3.10 or newer
- Pygame
- For the data update scripts: `requests` and `beautifulsoup4`
- For standalone builds: PyInstaller

Install the game and build dependencies with:

```sh
python -m pip install pygame pyinstaller requests beautifulsoup4
```

The game itself only needs Pygame. The scraper dependencies are needed only to update data.

## Runtime data

The game reads these paths relative to the project root (or the packaged application):

- `data/pokemon.json`
- `data/data.json`
- `data/Images/`, including `background.png` and the generated Pokémon sprites

`data/pokemon.json` and generated Pokémon PNGs are ignored by Git. `data/data.json` and `data/Images/background.png` are included in the repository. On a fresh checkout, create the missing Pokémon records and sprites from the project root:

```sh
python data/pokemon_fetcher.py
python data/move_fetcher.py
python data/image_fetcher.py
```

The fetchers make network requests, so an internet connection is required. They are safe to import; work starts only when a script is run directly. Existing valid Pokémon data and images are kept, missing entries are added, and invalid or missing sprites are regenerated. If a fetch reports unresolved records, rerun that script to retry them before building.

## Run from source

From the project root:

```sh
python main.py
```

At startup, the game validates the data files and Pokémon images before showing setup. If data is missing or invalid, generate or repair it with the commands above.

## Build a standalone application

Build on the operating system you intend to run. PyInstaller does not cross-compile between Windows and Linux. The data-generation steps above must finish first because PyInstaller requires `data/pokemon.json` and the generated sprites to exist.

The repository intentionally ignores `pokemon_ONLINE_Game.spec`, so a fresh clone will not have the spec file. Install PyInstaller using the Requirements command above, then create the spec once with the command for your platform. Run these commands from the project root.

**Windows** — run from Command Prompt or PowerShell in the project root:

```powershell
# Create the spec only if pokemon_ONLINE_Game.spec is missing.
pyi-makespec --onefile --windowed --name pokemon_ONLINE_Game --icon "assets/Poké_Ball.ico" --add-data "data/pokemon.json;data" --add-data "data/data.json;data" --add-data "data/Images;data/Images" --add-data "src;src" main.py

# Build (run this on later builds when the spec already exists).
pyinstaller --clean pokemon_ONLINE_Game.spec
```

This creates `dist\pokemon_ONLINE_Game.exe`. The spec uses a windowed build, so Windows does not open a console window. The game’s debug prints are discarded in this build.

**Linux / WSL** — run from a Linux shell in the project root:

```sh
# Create the spec only if pokemon_ONLINE_Game.spec is missing.
pyi-makespec --onefile --windowed --name pokemon_ONLINE_Game --icon "assets/Poké_Ball.ico" --add-data "data/pokemon.json:data" --add-data "data/data.json:data" --add-data "data/Images:data/Images" --add-data "src:src" main.py

# Build (run this on later builds when the spec already exists).
pyinstaller --clean pokemon_ONLINE_Game.spec
```

This creates `dist/pokemon_ONLINE_Game`. PyInstaller ignores the spec’s `console=False` setting on Linux. Launching from a terminal writes debug output to that terminal; launching from a desktop menu normally does not open one.

The `dist/` executable is native to the build platform. A Windows `.exe` must be built on Windows; a Linux executable must be built on Linux. Both platform-specific commands are also kept in `application command.txt`.

## Controls

- Use the on-screen buttons to choose the game mode and battle actions.
- During Pokémon selection, click Pokémon to choose them; Up/Down and the mouse wheel scroll the selection.
- In move, switch, and team lists, use Up/Down to scroll. Mouse-wheel scrolling is only enabled on the Pokémon selection screen.
- On the invite-code screen, the host can click **Copy Code** or press Ctrl+C. The joining player can paste with Ctrl+V.
- Press Enter to close the party list; it also closes automatically after five seconds.

Battle actions are Fight, Switch, List, and Exit. Moves with no PP cannot be selected. If all active Pokémon’s moves are exhausted, switch, view the team, or exit. Healing is capped at maximum HP and reports when no HP was recovered. In local PvP, Exit forfeits the match.

## Online play

Online play uses a direct TCP connection on port **5000**; there is no matchmaking or relay service. The host shares the invite code, which contains the host address and a random authentication secret. The code can be copied and pasted. The connection is authenticated, but traffic is not encrypted.

The host must be reachable by the joining player. On a LAN, allow incoming TCP connections on port 5000 in the host firewall. Connections across separate networks may also require router port forwarding or another reachable network path.

## Data and image maintenance scripts

- `data/pokemon_fetcher.py` adds missing Pokémon records.
- `data/move_fetcher.py` adds missing move records and repairs invalid PP values.
- `data/image_fetcher.py` preserves valid PNGs, regenerates invalid or missing images, and updates `data/gallery.html`.
- `data/move_check.py` reports duplicate move names after normalization.

All data scripts use paths relative to their own location, so run them from the project root as shown above. Network fetchers use bounded timeouts and retries; failed records are reported for a later retry.

## Project layout

```text
main.py                    Application entry point
src/                       UI, battle rules, Pokémon and move models, networking
data/                      Runtime JSON data and data maintenance scripts
data/Images/background.png Static battle background
assets/Poké_Ball.ico       Windows application icon
pokemon_ONLINE_Game.spec   PyInstaller build configuration
application command.txt    Platform-specific build commands
```

Generated JSON files and Pokémon sprites are excluded from Git so the ignore rules do not need per-Pokémon updates.
