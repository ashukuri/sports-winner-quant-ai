#!/usr/bin/env python3
import urllib.request
import ssl
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

urls = [
    "https://winner.toto.rakuten.co.jp/result/match/basketball/",
    "https://winner.toto.rakuten.co.jp/result/match/soccer/",
    "https://winner.toto.rakuten.co.jp/result/"
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
            html = r.read().decode('utf-8')
        print(f"SUCCESS: {url} (len: {len(html)})")
        soup = BeautifulSoup(html, 'html.parser')
        print("Title:", soup.title.string.strip() if soup.title else "")
    except Exception as e:
        print(f"FAILED: {url} ({e})")
