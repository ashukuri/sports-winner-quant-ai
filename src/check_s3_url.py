#!/usr/bin/env python3
import urllib.request
import re

url = 'https://bleague.bl.kuroco-img.app/v=1790306790/files/js/front/user/genius_schedule.js'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as r:
    js_code = r.read().decode('utf-8')

matches = [m.start() for m in re.finditer(r'amazonaws\.com/web_json', js_code)]
for pos in matches:
    print("--- Snippet around amazonaws.com ---")
    start = max(0, pos - 150)
    end = min(len(js_code), pos + 250)
    print(js_code[start:end])
