#!/usr/bin/env python3
import urllib.request
import json

headers = {'User-Agent': 'Mozilla/5.0'}
try:
    url = 'https://api.github.com/repos/rintaromasuda/bleaguebydata/contents/data'
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        items = json.loads(r.read().decode('utf-8'))
    print("Files in bleaguebydata/data:")
    for item in items:
        print(f"  {item['name']} ({item['size']} bytes, {item['download_url']})")
except Exception as e:
    print('Error:', e)
