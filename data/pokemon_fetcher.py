import requests
from bs4 import BeautifulSoup
import json
import base64
import os
import tempfile
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent
REQUEST_TIMEOUT = (5, 20)
MAX_RETRIES = 3
MAX_POKEMON_FETCH_SECONDS = 180

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


def clean_abilities(raw_abilities):
    abilities = []
    for ab in raw_abilities:
        clean = ab.text.strip().replace(" (hidden ability)", "")
        if clean not in abilities:
            abilities.append(clean)
    return abilities

def get_generation_number(soup):
    national_row = soup.find("th", string="National №")
    if national_row:
        national_td = national_row.find_next("td")
        if national_td:
            try:
                number = int(national_td.text.strip().replace("#", ""))
            except ValueError:
                number = None
            if number is not None:
                ranges = ((151, 1), (251, 2), (386, 3), (493, 4),
                          (649, 5), (721, 6), (809, 7), (905, 8), (1025, 9))
                for maximum, generation in ranges:
                    if number <= maximum:
                        return generation
                return None

    local_row = soup.find("th", string="Local №")
    local_td = local_row.find_next("td") if local_row else None
    if not local_td:
        return None
    generation_text = local_td.get_text().lower()
    generation_terms = (
        (2, ("gold", "silver", "crystal")),
        (3, ("ruby", "sapphire", "emerald", "firered", "leafgreen")),
        (4, ("diamond", "pearl", "platinum", "heartgold", "soulsilver")),
        (5, ("black", "white")),
        (6, ("omega ruby", "alpha sapphire", "kalos")),
        (7, ("sun", "moon", "let's go", "alola")),
        (8, ("sword", "shield", "galar")),
        (9, ("scarlet", "violet", "paldea", "indigo disk", "teal mask")),
    )
    return next((generation for generation, terms in generation_terms
                 if any(term in generation_text for term in terms)), None)



def get_missing_pokemon_names(existing_names):
    url = "https://pokemondb.net/pokedex/national"
    resp = request_url(url)
    if resp is None or resp.status_code != 200:
        print("❌ Failed to fetch the national Pokédex.")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    all_names = [tag.text.strip() for tag in soup.select("div.infocard a.ent-name")]

    if not all_names:
        print("❌ The National Pokédex response contained no Pokémon records.")
        return None
    existing_lower = {name.lower() for name in existing_names}
    missing = [name for name in all_names if name.lower() not in existing_lower]
    return missing

def fetch_and_encode_image(name_url, deadline=None):

    match name_url:
        case "giratina":
            name_url = "giratina-altered"
        case "shaymin":
            name_url = "shaymin-land"
        case "oricorio":
            name_url = "oricorio-baile"
        case "lycanroc":
            name_url = "lycanroc-midday"
        case "wishiwashi":
            name_url = "wishiwashi-solo"
        case "eiscue":
            name_url = "eiscue-ice"
        case "morpeko":
            name_url = "morpeko-full-belly"
        case "urshifu":
            name_url = "urshifu-single-strike"
        case "enamorus":
            name_url = "enamorus-incarnate"

    primary_url = f"https://img.pokemondb.net/artwork/large/{name_url}.jpg"
    match name_url:
        case "sinistcha":
            primary_url = "https://img.pokemondb.net/sprites/scarlet-violet/normal/sinistcha.png"
        case "hydrapple":
            primary_url = "https://img.pokemondb.net/sprites/scarlet-violet//normal/hydrapple.png"
        case "gouging-fire":
            primary_url = "https://img.pokemondb.net/sprites/scarlet-violet/normal/gouging-fire.png"
        case "iron-boulder":
            primary_url = "https://img.pokemondb.net/sprites/scarlet-violet/normal/iron-boulder.png"
    response = request_url(primary_url, deadline)
    if response is not None and response.status_code == 200:
        return base64.b64encode(response.content).decode("utf-8")
    status = response.status_code if response is not None else "no response"
    print(f"❌ Could not fetch primary image for {name_url} (status {status})\n Tried {primary_url}")
    return ""


def fetch_pokemon_data(name):
    deadline = time.monotonic() + MAX_POKEMON_FETCH_SECONDS
    name_url = name.lower().replace(" ", "-")
    name_url = name_url.replace(".","")
    name_url = name_url.replace("'","")
    name_url = name_url.replace(":","")
    name_url = name_url.replace("é","e")
    name_url = name_url.replace("♀","-f")
    name_url = name_url.replace("♂","-m")
    base_url = f"https://pokemondb.net/pokedex/{name_url}"

    resp_main = request_url(base_url, deadline)
    if resp_main is None or resp_main.status_code != 200:
        print(f"❌ Failed to fetch base page for {name}")
        return

    soup_main = BeautifulSoup(resp_main.text, "html.parser")
    gen_number = get_generation_number(soup_main)
    if gen_number is None:
        print(f"❌ Could not determine generation for {name}")
        return None
    while gen_number <= 10:
        moves_url_test = f"https://pokemondb.net/pokedex/{name_url}/moves/{gen_number}"
        resp_test = request_url(moves_url_test, deadline)
        if resp_test is not None and resp_test.status_code == 200:
            break
        gen_number += 1

    if gen_number > 10:
        print(f"❌ Could not find any valid moves page for {name} from starting gen onward up to Gen 10")
        return
    last_valid_gen = None
    last_valid_moves = set()
    max_move_count = 0
    # Check from current gen_number up to 10
    for try_gen in range(gen_number, 11):
        moves_url_try = f"https://pokemondb.net/pokedex/{name_url}/moves/{try_gen}"
        resp_try = request_url(moves_url_try, deadline)
        if resp_try is not None and resp_try.status_code == 200:
            soup_moves = BeautifulSoup(resp_try.text, "html.parser")
            moves = set()
            move_tables = soup_moves.select("table.data-table")
            for table in move_tables:
                for row in table.select("tbody tr"):
                    move_cell = row.select_one("a.ent-name")
                    if move_cell:
                        moves.add(move_cell.text.strip())\

            if len(moves) > max_move_count:
                max_move_count = len(moves)
                last_valid_gen = try_gen
                last_valid_moves = moves

    # Use the largest valid gen number with non-empty moves
    if last_valid_gen is not None:
        moves_url = f"https://pokemondb.net/pokedex/{name_url}/moves/{last_valid_gen}"
        resp_moves = request_url(moves_url, deadline)
        if resp_moves is None or resp_moves.status_code != 200:
            return None
        # If you still need the moves set here:
        moves = last_valid_moves
    else:
        print(f"❌ Could not fetch a valid moves page with non-empty move list for {name} from gen {gen_number} to 10")
        return

    soup_moves = BeautifulSoup(resp_moves.text, "html.parser")
    type_tags = soup_main.select("table.vitals-table tr:-soup-contains('Type') a.type-icon")
    types = list(set(t.text.strip() for t in type_tags))

    ability_row = soup_main.select("table.vitals-table tr:-soup-contains('Abilities') td a")
    abilities = clean_abilities(ability_row)

    evo_block = soup_main.select("div.infocard-list-evo a.ent-name")
    evo_names = [evo.text.strip() for evo in evo_block]
    name_clean = name_url.lower()
    try:
        current_index = [n.lower() for n in evo_names].index(name_clean)
        next_evos = []
        seen = set()
        for evo_name in evo_names[current_index + 1:]:
            if evo_name not in seen:
                seen.add(evo_name)
                next_evos.append(evo_name)
    except ValueError:
        next_evos = []
    evolutions = next_evos

    moves = set()
    move_tables = soup_moves.select("table.data-table")
    for table in move_tables:
        for row in table.select("tbody tr"):
            move_cell = row.select_one("a.ent-name")
            if move_cell:
                moves.add(move_cell.text.strip())

    base_stats = []
    stats_table = soup_main.find('h2', string='Base stats')
    if stats_table:
        table = stats_table.find_next('table', class_='vitals-table')
        if table:
            rows = table.find_all('tr')
            for stat in ['HP', 'Attack', 'Defense', 'Sp. Atk', 'Sp. Def', 'Speed']:
                for row in rows:
                    if row.find('th') and stat in row.find('th').text:
                        value = row.find('td').text.strip()
                        base_stats.append(int(value))
                        break

    image_data = fetch_and_encode_image(name_url, deadline)
    if not image_data:
        print(f"❌ No image data could be fetched for {name}")
        return None

    if len(base_stats) != 6 or not types:
        print(f"❌ Required stats or types were missing for {name}")
        return None

    formatted = {
        "IMAGE": image_data,
        "Name": name,
        "Generation": gen_number,
        "Types": types,
        "Abilities": abilities,
        "Tier": "CG",
        "hp": base_stats[0] if len(base_stats) > 0 else 0,
        "attack": base_stats[1] if len(base_stats) > 1 else 0,
        "defense": base_stats[2] if len(base_stats) > 2 else 0,
        "special_attack": base_stats[3] if len(base_stats) > 3 else 0,
        "special_defense": base_stats[4] if len(base_stats) > 4 else 0,
        "speed": base_stats[5] if len(base_stats) > 5 else 0,
        "Next Evolution(s)": evolutions,
        "Moves": sorted(moves)
    }

    # print("\n=== FORMATTED ENTRY ===")
    # for k, v in formatted.items():
    #     print(f"{k}: {v}")

    return formatted


def save_json_atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
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


def main():
    pokemon_path = DATA_DIR / "pokemon.json"
    if pokemon_path.exists():
        try:
            existing_data = json.loads(pokemon_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"❌ Could not read {pokemon_path}: {exc}")
            return 1
        if not isinstance(existing_data, dict) or not isinstance(existing_data.get("pokemons"), list):
            print(f"❌ Invalid Pokémon data structure in {pokemon_path}; existing data was left unchanged.")
            return 1
    else:
        existing_data = {"pokemons": []}

    existing_names = {p["Name"] for p in existing_data["pokemons"]
                      if isinstance(p, dict) and isinstance(p.get("Name"), str)}
    missing_names = get_missing_pokemon_names(existing_names)
    if missing_names is None:
        print("❌ Could not retrieve the National Pokédex; no local data was changed.")
        return 1

    print(f"NUMBER OF MISSING POKEMON: {len(missing_names)}")
    unresolved = []
    for name in missing_names:
        try:
            new_entry = fetch_pokemon_data(name)
        except (requests.RequestException, ValueError, KeyError, TypeError, IndexError) as exc:
            print(f"❌ Failed to fetch or parse {name}: {exc}")
            new_entry = None
        if not new_entry:
            unresolved.append(name)
            continue
        existing_data["pokemons"].append(new_entry)
        existing_names.add(name)
        try:
            save_json_atomic(pokemon_path, existing_data)
            print(f"✅ Added {name} to pokemon.json")
        except OSError as exc:
            existing_data["pokemons"].pop()
            print(f"❌ Could not save {name}: {exc}")
            unresolved.append(name)
            break

    if unresolved:
        print(f"❌ Unresolved Pokémon ({len(unresolved)}): {', '.join(unresolved)}")
        return 1
    print("\n🎉 Done! Pokémon data is up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
