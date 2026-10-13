#!/usr/bin/env python3
import urllib.request
import json

base = "http://b-league.s3.amazonaws.com/web_json/v2_genius_contexts/"
headers = {'User-Agent': 'Mozilla/5.0'}

test_files = [
    "schedule_2022_b1.json", "schedule_2023_b1.json", "schedule_2024_b1.json",
    "schedule_2022.json", "schedule_2023.json", "schedule_2024.json",
    "2022_b1.json", "2023_b1.json", "2024_b1.json",
    "context_2022.json", "context_2023.json", "context_2024.json"
]

for tf in test_files:
    try:
        url = base + tf
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as r:
            data = r.read()
            print(f"SUCCESS: {tf} (len: {len(data)})")
    except Exception as e:
        pass
print("Tested basic S3 filenames.")
