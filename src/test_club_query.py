#!/usr/bin/env python3
import urllib.request
import json
import ssl
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

# Test club-based schedule query
# e.g., year=2022, club=703 (宇都宮), tab=1
url = "https://www.bleague.jp/schedule/?data_format=json&year=2022&event=2&club=703&tab=1"
try:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
        data = json.loads(r.read().decode('utf-8'))
    topics = data.get('topics', [])
    print("Club 703 topics count:", len(topics))
    if topics:
        soup = BeautifulSoup(topics[0], 'html.parser')
        items = soup.find_all('li', class_='list-item')
        print("Matches found for Club 703 in 2022-23:", len(items))
        for it in items[:3]:
            home = it.find('span', class_='team home')
            away = it.find('span', class_='team away')
            score = it.find('div', class_='score')
            print(f"  {home.get_text().strip() if home else ''} vs {away.get_text().strip() if away else ''}: {score.get_text().strip() if score else ''}")
except Exception as e:
    print("Error:", e)
