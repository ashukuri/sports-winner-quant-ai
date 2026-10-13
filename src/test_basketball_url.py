#!/usr/bin/env python3
import urllib.request
import ssl
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

url = "https://sports.yahoo.co.jp/basketball/bleague/schedule"
try:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
        html = r.read().decode('utf-8')
    print("Fetched successfully! Length:", len(html))
    soup = BeautifulSoup(html, 'html.parser')
    print("Title:", soup.title.string.strip() if soup.title else "")
    for a in soup.find_all('a', href=True):
        if 'schedule' in a['href'] or 'game' in a['href']:
            print("Link:", a['href'], a.get_text().strip())
except Exception as e:
    print("Error:", e)
