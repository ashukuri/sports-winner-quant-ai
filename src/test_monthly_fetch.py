#!/usr/bin/env python3
import urllib.request
import json
import ssl
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

def test_month_fetch():
    # 2022年10月〜2023年5月のB1 (event=2)
    yr = 2022
    for mon in [10, 11, 12, 1, 2, 3, 4, 5]:
        query_yr = yr if mon >= 10 else yr + 1
        url = f"https://www.bleague.jp/schedule/?data_format=json&year={query_yr}&mon={mon:02d}&event=2&tab=1"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
                data = json.loads(r.read().decode('utf-8'))
            topics = data.get('topics', [])
            match_count = 0
            for t in topics:
                soup = BeautifulSoup(t, 'html.parser')
                match_count += len(soup.find_all('li', class_='list-item'))
            print(f"Year {query_yr} Mon {mon:02d}: {match_count} matches")
        except Exception as e:
            print(f"Error {query_yr}-{mon}: {e}")

if __name__ == "__main__":
    test_month_fetch()
