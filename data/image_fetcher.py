import base64
import html
import json
import os
import re
import tempfile
from collections import deque
from io import BytesIO
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parent
IMAGE_DIR = DATA_DIR / "Images"
MAX_SIZE = (80, 80)
WHITE_THRESHOLD = 240
TYPE_COLORS = {
    "fire": "#f08030", "water": "#3399ff", "grass": "#78c850",
    "electric": "#f8d030", "bug": "#a8b820", "normal": "#a8a878",
    "psychic": "#f85888", "ghost": "#705898", "dragon": "#7038f8",
    "dark": "#705848", "fairy": "#ee99ac", "ice": "#98d8d8",
    "fighting": "#c03028", "poison": "#a040a0", "rock": "#b8a038",
    "steel": "#b8b8d0", "ground": "#e0c068",
}


def remove_white_background(image, threshold=WHITE_THRESHOLD):
    width, height = image.get_size()
    visited = [[False] * height for _ in range(width)]
    queue = deque()
    for x in range(width):
        queue.append((x, 0))
        queue.append((x, height - 1))
    for y in range(height):
        queue.append((0, y))
        queue.append((width - 1, y))
    while queue:
        x, y = queue.popleft()
        if not (0 <= x < width and 0 <= y < height) or visited[x][y]:
            continue
        red, green, blue, _alpha = image.get_at((x, y))
        visited[x][y] = True
        if red >= threshold and green >= threshold and blue >= threshold:
            image.set_at((x, y), (255, 255, 255, 0))
            queue.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    return image


def image_filename(name):
    safe_name = re.sub(r'[<>:"/\\\\|?*]', "_", name).replace(" ", "_")
    return safe_name + ".png"


def valid_png(path, pygame):
    try:
        pygame.image.load(str(path))
        return True
    except (pygame.error, OSError, ValueError):
        return False


def generate_image(pokemon, output_path, pygame):
    encoded = pokemon.get("IMAGE")
    if not isinstance(encoded, str) or not encoded:
        return False, "missing encoded image data"
    temp_path = None
    try:
        raw_image = base64.b64decode(encoded, validate=True)
        image = pygame.image.load(BytesIO(raw_image), pokemon.get("Name", "pokemon"))
        image = pygame.transform.smoothscale(image.convert_alpha(), MAX_SIZE)
        image = remove_white_background(image)
        with tempfile.NamedTemporaryFile(dir=output_path.parent, prefix=".pokemon-",
                                         suffix=".tmp.png", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
        pygame.image.save(image, str(temp_path))
        if not valid_png(temp_path, pygame):
            raise ValueError("image encoder produced an invalid PNG")
        os.replace(temp_path, output_path)
        return True, None
    except (ValueError, OSError, base64.binascii.Error, pygame.error) as exc:
        return False, str(exc)
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def build_gallery(pokemons, image_dir, output_path):
    entries = []
    for pokemon in pokemons:
        name = str(pokemon.get("Name", "Unknown"))
        if not (image_dir / image_filename(name)).is_file():
            continue
        safe_name = html.escape(name, quote=True)
        types = pokemon.get("Types", [])
        abilities = pokemon.get("Abilities", [])
        if not isinstance(types, list):
            types = []
        if not isinstance(abilities, list):
            abilities = []
        type_spans = "".join(
            f'<span class="type {html.escape(str(item).lower(), quote=True)}">'
            f'{html.escape(str(item))}</span>' for item in types
        )
        ability_text = html.escape(", ".join(map(str, abilities)))
        generation = html.escape(str(pokemon.get("Generation", "Unknown")))
        image_src = html.escape(f"./Images/{image_filename(name)}", quote=True)
        entries.append(f"""<div class="card">
            <img src="{image_src}" alt="{safe_name}">
            <div class="info"><div><strong>Generation:</strong> {generation}</div>
            <div><strong>Name:</strong> {safe_name}</div><div><strong>Type:</strong> {type_spans}</div>
            <div><strong>Abilities:</strong> {ability_text}</div></div>
        </div>""")
    type_css = "".join(f".{name}{{background-color:{color}}}" for name, color in TYPE_COLORS.items())
    template = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
    <title>Pokémon Gallery</title><style>
    body{font-family:Arial,sans-serif;padding:20px;background:#000;color:#fff}
    h1{text-align:center}.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:20px;padding:20px}
    .card{background:#1e1e1e;padding:10px;border-radius:10px;text-align:center;position:relative;overflow:hidden}
    img{max-width:100%;height:auto}.info{display:none;position:absolute;inset:0;background:#000b;padding:10px;text-align:left}
    .card:hover .info{display:block}.type{display:inline-block;padding:5px 10px;border-radius:5px;margin:5px}
    {type_css}</style></head><body><h1>Pokémon Gallery</h1><div class="gallery">\n""".replace(
        "{type_css}", type_css
    )
    output = template + "\n".join(entries) + "\n</div></body></html>"
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=output_path.parent,
                                         prefix=f".{output_path.name}.", suffix=".tmp", delete=False) as temp:
            temp_name = temp.name
            temp.write(output)
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, output_path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def main():
    pokemon_path = DATA_DIR / "pokemon.json"
    try:
        data = json.loads(pokemon_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"Could not read Pokémon data at {pokemon_path}: {exc}")
        return 1
    if not isinstance(data, dict) or not isinstance(data.get("pokemons"), list):
        print(f"Invalid Pokémon data structure in {pokemon_path}; no files were changed.")
        return 1

    try:
        import pygame
    except ImportError as exc:
        print(f"Pygame is required to generate images: {exc}")
        return 1
    try:
        pygame.init()
        pygame.display.set_mode((1, 1))
    except pygame.error as exc:
        print(f"Pygame could not initialize image processing: {exc}")
        return 1

    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    unresolved = []
    for pokemon in data["pokemons"]:
        if not isinstance(pokemon, dict) or not isinstance(pokemon.get("Name"), str):
            unresolved.append(str(pokemon))
            print("Skipping malformed Pokémon record.")
            continue
        name = pokemon["Name"]
        output_path = IMAGE_DIR / image_filename(name)
        if output_path.is_file() and valid_png(output_path, pygame):
            continue
        generated, error = generate_image(pokemon, output_path, pygame)
        if generated:
            print(f"✅ Added/refreshed image: {output_path.name}")
        else:
            unresolved.append(name)
            print(f"❌ Could not create image for {name}: {error}")

    try:
        build_gallery(data["pokemons"], IMAGE_DIR, DATA_DIR / "gallery.html")
    except OSError as exc:
        print(f"Could not write gallery.html: {exc}")
        return 1
    pygame.quit()
    if unresolved:
        print(f"Unresolved images ({len(unresolved)}): {', '.join(unresolved)}")
        return 1
    print("✅ Pokémon images and gallery are up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
