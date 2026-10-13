#!/usr/bin/env python3
import urllib.request
import re

url = "https://www.bleague.jp/schedule/?tab=1&year_index=2023&event=1"
headers = {'User-Agent': 'Mozilla/5.0'}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as r:
    html = r.read().decode('utf-8')

idx = html.find('function schedule_b1_more()')
if idx != -1:
    print(html[idx:idx+1200])
