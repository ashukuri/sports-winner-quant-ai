#!/usr/bin/env python3
import urllib.request
import ssl
from bs4 import BeautifulSoup
import re

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

url = "https://sports.yahoo.co.jp/basket/bleague/schedule?sec=1"
try:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
        html = r.read().decode('utf-8')
    print("Fetched SportsNavi sec=1, length:", len(html))
    soup = BeautifulSoup(html, 'html.parser')
    print("Title:", soup.title.string.strip() if soup.title else "")
    # Check for match cards
    matches = soup.find_all(class_=re.compile(r'bb-score|bb-match|game|schedule', re.I))
    print("Matches tags count:", len(matches))
    for m in matches[:5]:
        print("  tag:", m.name, "class:", m.get('class'), "text:", m.get_text()[:60].strip())
except Exception as e:
    print("Error:", e)
