#!/usr/bin/env python3
import urllib.request
import pandas as pd
import io

headers = {'User-Agent': 'Mozilla/5.0'}
base = 'https://raw.githubusercontent.com/rintaromasuda/bleaguer/master/inst/extdata/'

for f in ['games_202122.csv', 'games_summary_202122.csv', 'teams.csv']:
    url = base + f
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as r:
        content = r.read().decode('utf-8')
    df = pd.read_csv(io.StringIO(content))
    print(f"=== {f} === (shape: {df.shape})")
    print("Columns:", df.columns.tolist()[:15])
    print(df.head(2))
    print()
