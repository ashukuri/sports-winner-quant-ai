#!/usr/bin/env python3
import urllib.request
import ssl
from bs4 import BeautifulSoup
import re
import json

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

# Example: holdCountId=0423, commodityId=50 (千葉J vs A東京)
url = "https://winner.toto.rakuten.co.jp/singlematch/basketball/detail?holdCountId=0423&commodityId=50"
try:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
        html = r.read().decode('utf-8')
    print("Detail page fetched, len:", len(html))
    with open("data/raw/detail_sample.html", "w", encoding="utf-8") as f:
        f.write(html)
    # Search for embedded JSON or tables
    matches = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for m in matches:
        if any(k in m for k in ['choice', 'odds', 'vote', 'candidate', 'subCommodity']):
            if len(m.strip()) > 50:
                print("Found data script in detail, len:", len(m))
                with open("data/raw/detail_data.json", "w", encoding="utf-8") as out:
                    out.write(m.strip())
                print("Sample:", m.strip()[:300])
                break
except Exception as e:
    print("Error:", e)
