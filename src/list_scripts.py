#!/usr/bin/env python3
import urllib.request
from bs4 import BeautifulSoup

url = "https://www.bleague.jp/schedule/?tab=1&year_index=2023&event=1"
headers = {'User-Agent': 'Mozilla/5.0'}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as r:
    html = r.read().decode('utf-8')

soup = BeautifulSoup(html, 'html.parser')
for s in soup.find_all('script'):
    src = s.get('src')
    if src:
        print("Script src:", src)
    else:
        text = s.string or ''
        if len(text.strip()) > 0:
            print("Inline script preview:", text.strip()[:100].replace('\n', ' '))
