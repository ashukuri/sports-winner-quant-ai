#!/usr/bin/env python3
import urllib.request
import json

url = 'https://raw.githubusercontent.com/rintaromasuda/bleaguebydata/master/scrapers/games_scraper.R'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as r:
        code = r.read().decode('utf-8')
    print("games_scraper.R length:", len(code))
    print(code[:800])
except Exception as e:
    print("Error:", e)
