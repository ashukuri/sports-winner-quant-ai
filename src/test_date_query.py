#!/usr/bin/env python3
import urllib.request
import json
import ssl
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

# 2022年10月の各土日を叩いてみる (10/1, 10/2, 10/8, 10/9, 10/15, 10/16, ...)
days_to_test = [1, 2, 8, 9, 15, 16, 22, 23]
total_matches = 0

for d in days_to_test:
    url = f"https://www.bleague.jp/schedule/?data_format=json&year=2022&mon=10&day={d:02d}&event=2&tab=1"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
            data = json.loads(r.read().decode('utf-8'))
        topics = data.get('topics', [])
        m_count = 0
        for t in topics:
            soup = BeautifulSoup(t, 'html.parser')
            items = soup.find_all('li', class_='list-item')
            m_count += len(items)
            for it in items:
                h = it.find('span', class_='team home')
                a = it.find('span', class_='team away')
                s = it.find('div', class_='score')
                # print sample
        print(f"2022-10-{d:02d}: {m_count} matches")
        total_matches += m_count
    except Exception as e:
        print(f"Error 2022-10-{d}: {e}")

print("Total matches across sample dates:", total_matches)
