import json
import re
from collections import defaultdict
from pathlib import Path


DATA_FILE = Path(__file__).resolve().parent / "data.json"


def clean_name(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find_duplicate_moves(moves):
    name_map = defaultdict(list)
    for move in moves:
        if not isinstance(move, dict):
            continue
        original_name = move.get("Name", "")
        if not isinstance(original_name, str):
            continue
        cleaned = clean_name(original_name)
        name_map[cleaned].append((move.get("Index", ""), original_name))
    return {name: entries for name, entries in name_map.items() if len(entries) > 1}


def main():
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read {DATA_FILE}: {exc}")
        return 1
    if not isinstance(data, dict) or not isinstance(data.get("moves"), list):
        print(f"Invalid move data in {DATA_FILE}.")
        return 1
    duplicates = find_duplicate_moves(data["moves"])
    print("Duplicate Moves Based on Cleaned Names:\n")
    for entries in duplicates.values():
        for index, name in entries:
            print(f"Index: {index}, Name: {name}")
        print("-" * 40)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
