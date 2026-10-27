import json
import os
import tempfile
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


DATA_DIR = Path(__file__).resolve().parent
REQUEST_TIMEOUT = (5, 20)
MAX_RETRIES = 3
MAX_MOVE_FETCH_SECONDS = 90
KNOWN_PP_CORRECTIONS = {"Ivy Cudgel": "10"}


def normalize_pp(move_name, raw_pp):
    """Return a usable PP value, retaining known values for non-numeric source data."""
    if isinstance(raw_pp, str):
        try:
            return str(max(1, int(raw_pp.split()[0])))
        except (ValueError, IndexError):
            pass
    return KNOWN_PP_CORRECTIONS.get(move_name, "20")


def request_url(url, deadline=None):
    for attempt in range(MAX_RETRIES):
        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            timeout = (min(REQUEST_TIMEOUT[0], remaining), min(REQUEST_TIMEOUT[1], remaining))
        else:
            timeout = REQUEST_TIMEOUT
        try:
            response = requests.get(url, timeout=timeout)
        except requests.RequestException as exc:
            if attempt + 1 == MAX_RETRIES:
                print(f"Request failed after {MAX_RETRIES} attempts: {url}: {exc}")
                return None
        else:
            if response.status_code != 429 and response.status_code < 500:
                return response
            if attempt + 1 == MAX_RETRIES:
                print(f"Request failed after {MAX_RETRIES} attempts: {url} (HTTP {response.status_code})")
                return response
        delay = 0.5 * (2 ** attempt)
        if deadline is not None:
            delay = min(delay, max(0, deadline - time.monotonic()))
        if delay:
            time.sleep(delay)
    return None


def save_json_atomic(path, data):
    path = Path(path)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as output:
            temp_name = output.name
            json.dump(data, output, indent=4, ensure_ascii=False)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def fetch_move_details(move_name):
    deadline = time.monotonic() + MAX_MOVE_FETCH_SECONDS
    slug = move_name.lower().replace(" ", "-").replace("'", "")
    if move_name == "WillOWisp":
        slug = "will-o-wisp"
    candidates = [slug]
    candidates.extend(f"{slug[:index]}-{slug[index:]}" for index in range(1, len(slug)))
    for candidate in dict.fromkeys(candidates):
        url = f"https://pokemondb.net/move/{candidate}"
        response = request_url(url, deadline)
        if response is None or response.status_code != 200:
            continue
        info_table = BeautifulSoup(response.text, "html.parser").find("table", class_="vitals-table")
        if info_table is None:
            continue
        move_data = {}
        for row in info_table.find_all("tr"):
            header, value = row.find("th"), row.find("td")
            if header is not None and value is not None:
                move_data[header.get_text(strip=True)] = value.get_text(strip=True)
        if move_data:
            return move_data
    print(f"Could not retrieve move details for {move_name}.")
    return None


def load_collection(path, key, required=False):
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Required data file is missing: {path}")
        return {key: []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get(key), list):
        raise ValueError(f"Invalid {key} data in {path}")
    return data


def main():
    try:
        pokemon_data = load_collection(DATA_DIR / "pokemon.json", "pokemons", required=True)
        move_path = DATA_DIR / "data.json"
        move_data = load_collection(move_path, "moves")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"Could not load required input data: {exc}")
        return 1

    moves = move_data["moves"]
    repaired = False
    for move in moves:
        if not isinstance(move, dict) or not isinstance(move.get("Name"), str):
            continue
        normalized_pp = normalize_pp(move["Name"], move.get("PP"))
        if move.get("PP") != normalized_pp:
            move["PP"] = normalized_pp
            repaired = True
    if repaired:
        try:
            save_json_atomic(move_path, move_data)
        except OSError as exc:
            print(f"Could not save repaired move data: {exc}")
            return 1
    known_names = {move["Name"].strip() for move in moves
                   if isinstance(move, dict) and isinstance(move.get("Name"), str)}
    unknown_moves = set()
    for pokemon in pokemon_data["pokemons"]:
        if not isinstance(pokemon, dict):
            print("Ignoring malformed Pokémon record while finding moves.")
            continue
        names = pokemon.get("Moves", [])
        if isinstance(names, str):
            names = [name.strip() for name in names.strip("[]").split(",") if name.strip()]
        if not isinstance(names, list):
            print(f"Ignoring malformed move list for {pokemon.get('Name', 'unknown')}.")
            continue
        unknown_moves.update(name for name in names
                             if isinstance(name, str) and name not in known_names)

    valid_indices = [int(move.get("Index", 0)) for move in moves
                     if isinstance(move, dict) and str(move.get("Index", "0")).isdigit()]
    next_index = max(valid_indices, default=0) + 1
    print(f"NUMBER OF UNKNOWN MOVES: {len(unknown_moves)}")
    unresolved = []
    for move_name in sorted(unknown_moves):
        try:
            raw = fetch_move_details(move_name)
        except (requests.RequestException, ValueError, TypeError, AttributeError) as exc:
            print(f"Failed to parse {move_name}: {exc}")
            raw = None
        if not raw:
            unresolved.append(move_name)
            continue
        pp = normalize_pp(move_name, raw.get("PP"))
        power = raw.get("Power")
        accuracy = raw.get("Accuracy")
        cleaned = {
            "Index": str(next_index),
            "Name": move_name,
            "Type": raw.get("Type", "Normal"),
            "Category": raw.get("Category", "Physical"),
            "Contest": raw.get("Contest", "Cool"),
            "PP": pp,
            "Power": power if isinstance(power, str) and power.isdigit() else "None",
            "Accuracy": accuracy if isinstance(accuracy, str) and accuracy.isdigit() else "None",
            "Generation": raw.get("Introduced", "1").replace("Gen. ", "").replace("Generation ", ""),
        }
        moves.append(cleaned)
        try:
            save_json_atomic(move_path, move_data)
        except OSError as exc:
            moves.pop()
            unresolved.append(move_name)
            print(f"Could not save {move_name}: {exc}")
            break
        known_names.add(move_name)
        next_index += 1
        print(f"✅ Added move: {move_name} with Index {cleaned['Index']}")

    if unresolved:
        print(f"Unresolved moves ({len(unresolved)}): {', '.join(unresolved)}")
        return 1
    if not move_path.exists():
        try:
            save_json_atomic(move_path, move_data)
        except OSError as exc:
            print(f"Could not create {move_path}: {exc}")
            return 1
    print("\n🎉 Done! Move data is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
