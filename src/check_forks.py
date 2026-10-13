#!/usr/bin/env python3
import urllib.request
import json

headers = {'User-Agent': 'Mozilla/5.0'}

# Check forks of bleaguer
url = 'https://api.github.com/repos/rintaromasuda/bleaguer/forks?sort=stargazers'
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as r:
        forks = json.loads(r.read().decode('utf-8'))
    print("Forks of bleaguer count:", len(forks))
    for f in forks[:10]:
        print(f"  {f['full_name']} (updated: {f['updated_at']})")
except Exception as e:
    print("Forks error:", e)

# Check branches of bleaguer
url = 'https://api.github.com/repos/rintaromasuda/bleaguer/branches'
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req) as r:
        branches = json.loads(r.read().decode('utf-8'))
    print("Branches of bleaguer:", [b['name'] for b in branches])
except Exception as e:
    print("Branches error:", e)
