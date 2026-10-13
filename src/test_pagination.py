#!/usr/bin/env python3
import urllib.request
import json
import ssl
from bs4 import BeautifulSoup

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

def test_pagination():
    url_base = "https://www.bleague.jp/schedule/?data_format=json&year=2022&mon=10&event=2&tab=1"
    cur_index = None
    all_matches = 0

    for page in range(10):
        url = url_base if cur_index is None else f"{url_base}&index={cur_index}"
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
            data = json.loads(r.read().decode('utf-8'))
        topics = data.get('topics', [])
        m_count = 0
        for t in topics:
            soup = BeautifulSoup(t, 'html.parser')
            m_count += len(soup.find_all('li', class_='list-item'))
        all_matches += m_count
        next_idx = data.get('index')
        print(f"Page {page}: got {m_count} matches, next_index = {next_idx}")
        if not next_idx or next_idx == cur_index:
            break
        cur_index = next_idx

    print(f"Total October 2022 matches: {all_matches}")

if __name__ == "__main__":
    test_pagination()
