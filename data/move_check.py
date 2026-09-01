import json
import re
from collections import defaultdict

def clean_name(name):
    # Lowercase and remove non-alphanumeric characters
    return re.sub(r'[^a-z0-9]', '', name.lower())

# Load the JSON file
with open("data.json", "r") as file:
    data = json.load(file)

# Dictionary to hold cleaned names and their original entries
name_map = defaultdict(list)

# Process each move
for move in data.get("moves", []):
    original_name = move.get("Name", "")
    cleaned = clean_name(original_name)
    name_map[cleaned].append((move.get("Index", ""), original_name))

# Find and display duplicates
print("Duplicate Moves Based on Cleaned Names:\n")
for cleaned_name, entries in name_map.items():
    if len(entries) > 1:
        for index, name in entries:
            print(f"Index: {index}, Name: {name}")
        print("-" * 40)
