import requests
from bs4 import BeautifulSoup
import json
import base64

def clean_abilities(raw_abilities):
    abilities = []
    for ab in raw_abilities:
        clean = ab.text.strip().replace(" (hidden ability)", "")
        if clean not in abilities:
            abilities.append(clean)
    return abilities

def get_generation_number(soup):
    local_row = soup.find("th", string="Local №")
    if not local_row:
        return None
    local_td = local_row.find_next("td")
    if not local_td:
        return None
    national_row = soup.find("th", string="National №")
    if national_row:
        national_td = national_row.find_next("td")
        if national_td:
            try:
                national_number = int(national_td.text.strip())
                if national_number <= 151:
                    return 1
            except ValueError:
                pass
    gen_text = local_td.get_text().lower()
    if "gold" in gen_text or "silver" in gen_text or "crystal" in gen_text:
        return 2
    if "ruby" in gen_text or "sapphire" in gen_text or "emerald" in gen_text or "firered" in gen_text or "leafgreen" in gen_text:
        return 3
    if "diamond" in gen_text or "pearl" in gen_text or "platinum" in gen_text or "heartgold" in gen_text or "soulsilver" in gen_text:
        return 4
    if "black" in gen_text or "white" in gen_text or "black 2" in gen_text or "white 2" in gen_text:
        return 5
    if "x" in gen_text or "y" in gen_text or "omega ruby" in gen_text or "alpha sapphire" in gen_text:
        return 6
    if "sun" in gen_text or "moon" in gen_text or "ultra sun" in gen_text or "ultra moon" in gen_text or "let's go" in gen_text:
        return 7
    if "sword" in gen_text or "shield" in gen_text:
        return 8
    if "scarlet" in gen_text or "violet" in gen_text or "indigo disk" in gen_text or "teal mask" in gen_text:
        return 9
    
    return national_number




def get_missing_pokemon_names(existing_names):
    url = "https://pokemondb.net/pokedex/national"
    resp = requests.get(url)
    if resp.status_code != 200:
        print("❌ Failed to fetch the national Pokédex.")
        return

    soup = BeautifulSoup(resp.text, "html.parser")
    all_names = [tag.text.strip() for tag in soup.select("div.infocard a.ent-name")]

    missing = [name for name in all_names if name.lower() not in {e.lower() for e in existing_names}]
    return missing

def fetch_and_encode_image(name_url):
    
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
    try:
        response = requests.get(primary_url)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode("utf-8")
        else:
            print(f"❌ Could not fetch primary image for {name_url} (status {response.status_code})\n Tried {primary_url}")
    except Exception as e:
        print(f"❌ Exception fetching primary image for {name_url}: {e}\n Tried {primary_url}")

    return ""

def fetch_pokemon_data(name):
    name_url = name.lower().replace(" ", "-")
    name_url = name_url.replace(".","")
    name_url = name_url.replace("'","")
    name_url = name_url.replace(":","")
    name_url = name_url.replace("é","e")
    name_url = name_url.replace("♀","-f")
    name_url = name_url.replace("♂","-m")
    base_url = f"https://pokemondb.net/pokedex/{name_url}"

    resp_main = requests.get(base_url)
    if resp_main.status_code != 200:
        print(f"❌ Failed to fetch base page for {name}")
        return

    soup_main = BeautifulSoup(resp_main.text, "html.parser")
    gen_number = get_generation_number(soup_main)
    match gen_number:
        case n if 10 <= n <= 151:
            gen_number = 1
        case n if 152 <= n <= 251:
            gen_number = 2
        case n if 252 <= n <= 386:
            gen_number = 3
        case n if 387 <= n <= 493:
            gen_number = 4
        case n if 494 <= n <= 649:
            gen_number = 5
        case n if 650 <= n <= 721:
            gen_number = 6
        case n if 722 <= n <= 809:
            gen_number = 7
        case n if 810 <= n <= 905:
            gen_number = 9
        case n if 906 <= n <= 1025:
            gen_number = 9
    while gen_number <= 10:
        moves_url_test = f"https://pokemondb.net/pokedex/{name_url}/moves/{gen_number}"
        resp_test = requests.get(moves_url_test)
        if resp_test.status_code == 200:
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
        resp_try = requests.get(moves_url_try)
        if resp_try.status_code == 200:
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
        resp_moves = requests.get(moves_url)
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
    
    image_data = fetch_and_encode_image(name_url)
        
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


default_pokemon_data = {"pokemons": []}
try:
    with open('pokemon.json', 'r') as f:
        existing_data = json.load(f)
except FileNotFoundError:
    print("⚠️ 'pokemon.json' not found. Creating a new one.")
    with open('pokemon.json', 'w') as f:
        json.dump(default_pokemon_data, f, indent=4)
    existing_data = default_pokemon_data

#fetch_pokemon_data("Aerodactyl")

# new_entry = fetch_pokemon_data("Nidoran♀")
# if new_entry:
#     existing_data["pokemons"].append(new_entry)
#     with open('pokemon.json', 'w') as f:
#         json.dump(existing_data, f, indent=4)
#     print(f"✅ Added Nidoran♀ to pokemon.json")
# else:
#     print("❌ Failed to fetch or parse.")

existing_names = {p["Name"] for p in existing_data["pokemons"]}
missign_pokemon = get_missing_pokemon_names(existing_names)
print(f"NUMBER OF MISSING POKEMON: {len(missign_pokemon)}")
for name in missign_pokemon:
    new_entry = fetch_pokemon_data(name)
    if new_entry:
        existing_data["pokemons"].append(new_entry)
        with open('pokemon.json', 'w') as f:
            json.dump(existing_data, f, indent=4)
        print(f"✅ Added {name} to pokemon.json")
    else:
        print("❌ Failed to fetch or parse.")
        
print("\n🎉 Done! Missing pokemons added to pokemon.json.")