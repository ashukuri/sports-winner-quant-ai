#!/usr/bin/env python3
import urllib.request
import ssl
from bs4 import BeautifulSoup
import re
import json

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

url = "https://winner.toto.rakuten.co.jp/result/singlematch/basketball/"
req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
    html = r.read().decode('utf-8')

with open("data/raw/rakuten_winner_basketball.html", "w", encoding="utf-8") as f:
    f.write(html)

soup = BeautifulSoup(html, 'html.parser')

# Check text preview
print("Checking structure...")
# Look for text with 第, 回, 当せん金, 円, 対戦カード
for block in soup.find_all(class_=re.compile(r'card|item|block|result|match', re.I))[:15]:
    t = block.get_text().strip()
    if any(k in t for k in ['第', '回', 'WINNER', '当せん金', '倍', '円', 'vs']):
        print("--- Match block snippet ---")
        print(t[:250].replace('\n', ' '))
