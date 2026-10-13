#!/usr/bin/env python3
import urllib.request
import ssl
from bs4 import BeautifulSoup
import re

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

url = "https://winner.toto.rakuten.co.jp/result/"
req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
    html = r.read().decode('utf-8')

soup = BeautifulSoup(html, 'html.parser')
links = soup.find_all('a', href=True)
print(f"Total links: {len(links)}")
for a in links:
    href = a['href']
    t = a.get_text().strip()
    if 'result' in href or 'history' in href or 'lot' in href or 'round' in href:
        print(f"  Href: {href} | Text: {t}")
