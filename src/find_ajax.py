#!/usr/bin/env python3
import urllib.request
import re

url = 'https://bleague.bl.kuroco-img.app/v=1790306790/files/js/front/user/genius_schedule.js'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as r:
    js_code = r.read().decode('utf-8')

for m in re.finditer(r'(\$\.ajax|\$\.getJSON|fetch)\s*\(\s*({|[^\)]+)\)', js_code):
    print("Match:", m.group(0)[:300])
    print("-" * 50)
