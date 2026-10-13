#!/usr/bin/env python3
import urllib.request
import re

url = "https://www.bleague.jp/schedule/?tab=1&year_index=2023&event=1"
headers = {'User-Agent': 'Mozilla/5.0'}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as r:
    html = r.read().decode('utf-8')

# Look for json or schedule in html
matches = re.findall(r'https?://[^\s\'"]+\.json', html)
print("JSON URLs in B.League page:", matches)

matches2 = re.findall(r'var schedule_contexts\s*=\s*({.*?});', html, re.DOTALL)
print("Found schedule_contexts inline?", len(matches2))
if matches2:
    print("Preview schedule_contexts:", matches2[0][:300])

# Look for any data variables
matches3 = re.findall(r'var\s+([a-zA-Z0-9_]+)\s*=\s*({|\[)', html)
print("JS variable definitions:", matches3[:10])
