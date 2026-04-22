
import json
from collections import Counter

with open("2026a2_songs.json", "r") as f:
    data = json.load(f)

songs = data["songs"]

print("Total songs in JSON:", len(songs))

# Check missing artist/title
missing = []
for i, song in enumerate(songs):
    if not song.get("artist") or not song.get("title"):
        missing.append((i, song))

print("Records missing artist or title:", len(missing))

# Check duplicates for current key design
keys = [(song.get("artist"), song.get("title")) for song in songs]
counter = Counter(keys)

duplicates = {k: v for k, v in counter.items() if v > 1}

print("Duplicate (artist, title) pairs:", len(duplicates))

total_extra = sum(v - 1 for v in duplicates.values())
print("How many records would be overwritten with current schema:", total_extra)

if duplicates:
    print("\nDuplicate keys found:")
    for k, v in duplicates.items():
        print(k, "appears", v, "times")