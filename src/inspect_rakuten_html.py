#!/usr/bin/env python3
import urllib.request
import ssl
from bs4 import BeautifulSoup
import re

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

url = "https://winner.toto.rakuten.co.jp/result/match/basketball/"
req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
    html = r.read().decode('utf-8')

soup = BeautifulSoup(html, 'html.parser')
print("Page Title:", soup.title.string.strip() if soup.title else "")

# Search for match results, tables, rounds
matches = soup.find_all(class_=re.compile(r'result|match|game|round|lottery', re.I))
print("Found match elements:", len(matches))
for m in matches[:10]:
    t = m.get_text().strip()
    if len(t) > 0 and len(t) < 150:
        print("  Elem class:", m.get('class'), "Text:", t.replace('\n', ' '))
