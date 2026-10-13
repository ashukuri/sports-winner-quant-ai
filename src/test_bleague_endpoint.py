#!/usr/bin/env python3
import urllib.request
import json

url = "https://www.bleague.jp/schedule/?data_format=json&year=2023&event=2&tab=1&index=0"
headers = {'User-Agent': 'Mozilla/5.0'}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req) as r:
    data = json.loads(r.read().decode('utf-8'))

print("Keys:", list(data.keys()))
print("Index:", data.get('index'))
print("Topics count:", len(data.get('topics', [])))
if data.get('topics'):
    print("Sample topic HTML (first 400 chars):")
    print(data['topics'][0][:400])
