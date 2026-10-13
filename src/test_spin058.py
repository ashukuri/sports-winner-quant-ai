#!/usr/bin/env python3
import urllib.request
import ssl
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

url = "https://store.toto-dream.com/dcs/subos/screen/pi40/spin058/PGSPIN05801InitSelectGameResult.form"
try:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
        html = r.read().decode('utf-8', errors='replace')
    print("Fetched spin058, length:", len(html))
    soup = BeautifulSoup(html, 'html.parser')
    print("Title:", soup.title.string.strip() if soup.title else "")
    for sel in soup.find_all('select'):
        print("Select:", sel.get('name'))
        for o in sel.find_all('option')[:10]:
            print(f"  {o.get('value')}: {o.get_text().strip()}")
except Exception as e:
    print("Error:", e)
