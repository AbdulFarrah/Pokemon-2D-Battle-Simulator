import json
import requests
from bs4 import BeautifulSoup

def fetch_move_details(move_name):
    move_url_name = move_name.lower().replace(" ", "-")
    move_url_name = move_url_name.lower().replace("'", "")
    url = f'https://pokemondb.net/move/{move_url_name}'
    #print(f"Fetching move: {move_name} → {url}")
    if move_name=='WillOWisp':
        url = 'https://pokemondb.net/move/will-o-wisp'
    response = requests.get(url)
    if response.status_code != 200:
        #print(f"❌ Failed to fetch {move_name}. Status: {response.status_code}")
        for i in range(1, len(move_url_name)):
            variation = move_url_name[:i] + '-' + move_url_name[i:]
            url1 = f'https://pokemondb.net/move/{variation}'
            print(f"Fetching move: {move_name} → {url1}")
            response1 = requests.get(url1)
            if response1.status_code == 200:
                response = response1
                break
            # if response1.status_code != 200:
            #     print(f"❌ Failed to fetch page. Status: {response1.status_code}")
       
       
    if(response.status_code != 200 and response1.status_code != 200):
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    try:
        info_table = soup.find('table', class_='vitals-table')
        rows = info_table.find_all('tr')
        move_data = {}
        for row in rows:
            header = row.find('th').text.strip()
            value = row.find('td').text.strip()
            move_data[header] = value
        return move_data
    except Exception as e:
        print(f"⚠️ Error parsing {move_name}: {e}")
        return None


default_pokemon_data = {"pokemons": []}
default_move_data = {"moves": []}

try:
    with open('pokemon.json', 'r') as f:
        pokemon_data_full = json.load(f)
except FileNotFoundError:
    print("⚠️ 'pokemon.json' not found. Creating a new one.")
    with open('pokemon.json', 'w') as f:
        json.dump(default_pokemon_data, f, indent=4)
    pokemon_data_full = default_pokemon_data
pokemon_list = pokemon_data_full["pokemons"]

try:
    with open('data.json', 'r') as f:
        move_data_full = json.load(f)
except FileNotFoundError:
    print("⚠️ 'data.json' not found. Creating a new one.")
    with open('data.json', 'w') as f:
        json.dump(default_move_data, f, indent=4)
    move_data_full = default_move_data
move_list = move_data_full["moves"]

# Set of existing move names
valid_moves = {move["Name"].strip() for move in move_list if "Name" in move}

# Find unknown moves
unknown_moves = set()

for pokemon in pokemon_list:
    move_names = pokemon.get("Moves", [])
    if isinstance(move_names, str):
        move_names = move_names.strip("[]").split(",")
        move_names = [m.strip() for m in move_names if m.strip()]

    for move in move_names:
        if move not in valid_moves:
            unknown_moves.add(move)

# Determine starting index
max_index = max((int(move.get("Index", 0)) for move in move_list if str(move.get("Index", "0")).isdigit()), default=0)
next_index = max_index + 1

print(f"NUMBER OF UNKNOWN MOVES: {len(unknown_moves)}")

# Fetch and append missing move data
for move_name in sorted(unknown_moves):
    raw_data = fetch_move_details(move_name)
    if not raw_data:
        continue
    cleaned = {
        "Index": str(next_index),
        "Name": move_name,
        "Type": raw_data.get("Type", "Normal"),
        "Category": raw_data.get("Category", "Physical"),
        "Contest": raw_data.get("Contest", "Cool"),
        "PP": raw_data.get("PP", "20").split()[0],
        "Power": raw_data.get("Power") if raw_data.get("Power", "").isdigit() else "None",
        "Accuracy": raw_data.get("Accuracy") if raw_data.get("Accuracy", "").isdigit() else "None",
        "Generation": raw_data.get("Introduced", "1").replace("Gen. ", "").replace("Generation ", "")
    }
    move_list.append(cleaned)
    print(f"✅ Added move: {move_name} with Index {next_index}")
    next_index += 1

    with open('data.json', 'w') as f:        
        json.dump({"moves": move_list}, f, indent=4)

print("\n🎉 Done! Missing moves added to data.json.")
