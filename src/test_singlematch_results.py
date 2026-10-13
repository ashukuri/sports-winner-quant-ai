#!/usr/bin/env python3
import urllib.request
import ssl
from bs4 import BeautifulSoup
import re

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

for sport in ['basketball', 'soccer']:
    url = f"https://winner.toto.rakuten.co.jp/result/singlematch/{sport}/"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
            html = r.read().decode('utf-8')
        print(f"=== {sport.upper()} RESULT LIST === (len: {len(html)})")
        soup = BeautifulSoup(html, 'html.parser')
        # Check title and select options (e.g. rounds / years)
        selects = soup.find_all('select')
        for s in selects:
            print("Select name:", s.get('name'), "options count:", len(s.find_all('option')))
            for o in s.find_all('option')[:5]:
                print(f"  {o.get('value')}: {o.get_text().strip()}")
        # Check match cards
        tables = soup.find_all(['table', 'div'], class_=re.compile(r'result|match|item|card|game', re.I))
        print("Result card elements count:", len(tables))
    except Exception as e:
        print(f"Error {sport}: {e}")
