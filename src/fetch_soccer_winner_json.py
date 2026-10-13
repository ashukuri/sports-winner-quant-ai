#!/usr/bin/env python3
import urllib.request
import ssl
from bs4 import BeautifulSoup
import re
import json

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

url = "https://winner.toto.rakuten.co.jp/result/singlematch/soccer/"
req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
    html = r.read().decode('utf-8')

with open("data/raw/rakuten_winner_soccer.html", "w", encoding="utf-8") as f:
    f.write(html)

matches = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
for m in matches:
    if 'salesEndDateList' in m:
        data = json.loads(m.strip())
        print("Soccer lotteryResults count:", len(data.get('lotteryResults', [])))
        with open('data/raw/winner_soccer_json.json', 'w', encoding='utf-8') as out:
            json.dump(data, out, ensure_ascii=False, indent=2)
        print("Saved to data/raw/winner_soccer_json.json")
        break
