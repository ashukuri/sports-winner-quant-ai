#!/usr/bin/env python3
import urllib.request
import json

headers = {'User-Agent': 'Mozilla/5.0'}

# 1. Check v2 in bleaguebydata
try:
    url = 'https://api.github.com/repos/rintaromasuda/bleaguebydata/contents/data/v2'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        items = json.loads(r.read().decode('utf-8'))
    print("Files in bleaguebydata/data/v2:")
    for item in items:
        print(f"  {item['name']} ({item['size']} bytes, {item['download_url']})")
except Exception as e:
    print('v2 error:', e)

# 2. Check scrapers in bleaguebydata
try:
    url = 'https://api.github.com/repos/rintaromasuda/bleaguebydata/contents/scrapers'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        items = json.loads(r.read().decode('utf-8'))
    print("Files in scrapers:")
    for item in items:
        print(f"  {item['name']}")
except Exception as e:
    print('scrapers error:', e)

# 3. Check genius_schedule.js
try:
    url = 'https://bleague.bl.kuroco-img.app/v=1790306790/files/js/front/user/genius_schedule.js'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        js_code = r.read().decode('utf-8')
    print("genius_schedule.js len:", len(js_code))
    # Look for API endpoints in genius_schedule.js
    import re
    urls = re.findall(r'https?://[^\s\'"]+|/rcms-api/[^\s\'"]+|/api/[^\s\'"]+', js_code)
    print("Found endpoints/URLs in JS:", set(urls[:15]))
except Exception as e:
    print('genius_schedule error:', e)
