#!/usr/bin/env python3
import urllib.request
import json

headers = {'User-Agent': 'Mozilla/5.0'}
url = 'https://api.github.com/repos/rintaromasuda/bleaguer/git/trees/master?recursive=1'
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as r:
        tree = json.loads(r.read().decode('utf-8'))
    print("Total items in bleaguer tree:", len(tree.get('tree', [])))
    for item in tree.get('tree', []):
        path = item['path']
        if path.endswith('.csv') or path.endswith('.rda') or path.endswith('.RData') or 'game' in path:
            print(f"  {path} ({item.get('size', 0)} bytes)")
except Exception as e:
    print("Error:", e)
