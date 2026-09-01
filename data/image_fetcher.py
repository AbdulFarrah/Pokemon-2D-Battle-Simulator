import base64
import json
import os
import pygame
from collections import deque

pygame.init()
pygame.display.set_mode((1, 1))
max_width, max_height = 80, 80
threshold = 240  # White threshold

def remove_white_background(image, threshold=240):
    w, h = image.get_size()
    visited = [[False for _ in range(h)] for _ in range(w)]
    queue = deque()

    # Start flood fill from all four edges
    for x in range(w):
        queue.append((x, 0))
        queue.append((x, h - 1))
    for y in range(h):
        queue.append((0, y))
        queue.append((w - 1, y))

    while queue:
        x, y = queue.popleft()
        if not (0 <= x < w and 0 <= y < h) or visited[x][y]:
            continue

        r, g, b, a = image.get_at((x, y))
        if r >= threshold and g >= threshold and b >= threshold:
            image.set_at((x, y), (255, 255, 255, 0))
            visited[x][y] = True
            # Explore 4-connected neighbors
            queue.extend([(x+1, y), (x-1, y), (x, y+1), (x, y-1)])
        else:
            visited[x][y] = True  # Stop going deeper if not white

    return image

# Ensure the output directory exists
output_dir = "./Images"
os.makedirs(output_dir, exist_ok=True)

# Load the JSON
with open('pokemon.json', 'r') as f:
    data = json.load(f)

# Process each Pokémon entry
for pokemon in data.get("pokemons", []):
    name = pokemon.get("Name", "unknown").replace("/", "_").replace(" ", "_")
    b64_string = pokemon.get("IMAGE")
    output_path = os.path.join(output_dir, f"{name}.png")
    
    if os.path.exists(output_path):
        continue
    
    if not b64_string:
        print(f"⚠️ No image found for {name}. Skipping.")
        continue

    try:
        temp_path = os.path.join(output_dir, f"__temp__{name}.png")
        with open(temp_path, "wb") as img_file:
            img_file.write(base64.b64decode(b64_string))

        # Load with Pygame
        image = pygame.image.load(temp_path).convert_alpha()
        image = pygame.transform.smoothscale(image, (max_width, max_height))

        # Remove white background from outer edge only
        processed_image = remove_white_background(image, threshold)

        # Save the processed image
        pygame.image.save(processed_image, output_path)

        # Clean up temp file
        os.remove(temp_path)

        print(f"✅ Saved image: {output_path}")
    except Exception as e:
        print(f"❌ Failed to save image for {name}: {e}")

# Type colors for hover effects
type_colors = {
    "fire": "#f08030",
    "water": "#3399ff",
    "grass": "#78c850",
    "electric": "#f8d030",
    "bug": "#a8b820",
    "normal": "#a8a878",
    "psychic": "#f85888",
    "ghost": "#705898",
    "dragon": "#7038f8",
    "dark": "#705848",
    "fairy": "#ee99ac",
    "ice": "#98d8d8",
    "fighting": "#c03028",
    "poison": "#a040a0",
    "rock": "#b8a038",
    "steel": "#b8b8d0",
    "ground": "#e0c068"
}

# HTML template start
html_start = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Pokémon Gallery</title>
    <style>
        body { font-family: Arial, sans-serif; padding: 20px; background: #000000; color: #ffffff; }
        h1 { text-align: center; }
        .gallery { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 20px; padding: 20px; }
        .card { 
            background: #1e1e1e; padding: 10px; border-radius: 10px; text-align: center; 
            box-shadow: 0 2px 5px rgba(255,255,255,0.1); position: relative; 
            overflow: hidden;
        }
        img { max-width: 100%; height: auto; }
        
        /* Hidden info section, displayed on hover */
        .info {
            display: none;
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.7);
            color: #ffffff;
            padding: 10px;
            text-align: left;
            font-size: 14px;
        }
        
        .card:hover .info {
            display: block;
        }

        .type {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 5px;
            margin-top: 5px;
        }
        
        /* Type colors */
        .fire { background-color: #f08030; }
        .water { background-color: #3399ff; }
        .grass { background-color: #78c850; }
        .electric { background-color: #f8d030; }
        .bug { background-color: #a8b820; }
        .normal { background-color: #a8a878; }
        .psychic { background-color: #f85888; }
        .ghost { background-color: #705898; }
        .dragon { background-color: #7038f8; }
        .dark { background-color: #705848; }
        .fairy { background-color: #ee99ac; }
        .ice { background-color: #98d8d8; }
        .fighting { background-color: #c03028; }
        .poison { background-color: #a040a0; }
        .rock { background-color: #b8a038; }
        .steel { background-color: #b8b8d0; }
        .ground { background-color: #e0c068; }
        
    </style>
</head>
<body>
    <h1>Pokémon Gallery</h1>
    <div class="gallery">
"""

# HTML entries
html_entries = ""
for pokemon in data.get("pokemons", []):
    name = pokemon.get("Name", "Unknown").replace("/", "_").replace(" ", "_")
    image_path = f"./Images/{name}.png"
    
    if os.path.exists(image_path):
        # Get the Pokémon's types and abilities
        types = pokemon.get("Types", [])
        abilities = pokemon.get("Abilities", [])
        generation = pokemon.get("Generation", "Unknown")
        
        # Create the HTML for the Pokémon card
        type_classes = " ".join([t.lower() for t in types])
        type_spans = "".join([f'<span class="type {t.lower()}">{t}</span>' for t in types])

        # Add the Pokémon card with hover details
        html_entries += f"""
        <div class="card">
            <img src="{image_path}" alt="{name}">
            <div class="info">
                <div><strong>Generation:</strong> {generation}</div>
                <div><strong>Name:</strong> {pokemon.get("Name", "Unknown")}</div>
                <div><strong>Type:</strong> {type_spans}</div>
                <div><strong>Abilities:</strong> {', '.join(abilities)}</div>
            </div>
        </div>
        """

# HTML template end
html_end = """
    </div>
</body>
</html>
"""

# Write HTML to file
with open("gallery.html", "w", encoding="utf-8") as f:
    f.write(html_start + html_entries + html_end)

print("✅ HTML gallery saved as gallery.html")
