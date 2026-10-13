#!/usr/bin/env python3
"""
src/fetch_winner_official_data.py
WINNER公式結果（toto-dream）および Bリーグ公式サイトからの
公式試合結果・WINNER当せん金・オッズデータの取得可能性調査・収集スクリプト
"""

import os
import sys
import json
import urllib.request
import ssl
from bs4 import BeautifulSoup
import re

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
CTX = ssl.create_default_context()

def check_toto_dream_winner():
    print("--- 1. Testing toto-dream WINNER Basketball Result URL ---")
    url = "https://store.toto-dream.com/dcs/subos/screen/pi49/spin067/PGSPIN06701InitResultListBasketballMatch.form"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
            html = r.read().decode('shift_jis', errors='replace')
        print(f"toto-dream fetched successfully! Length: {len(html)}")
        soup = BeautifulSoup(html, 'html.parser')
        print("Page Title:", soup.title.string.strip() if soup.title else "No title")
        # フォームやセレクトボックス、テーブルの調査
        selects = soup.find_all('select')
        print("Found select elements:", [s.get('name') for s in selects])
        tables = soup.find_all('table')
        print("Found tables count:", len(tables))
        # サンプルのテキスト
        with open("data/raw/toto_dream_sample.html", "w", encoding="utf-8") as out:
            out.write(html)
        print("Saved raw HTML to data/raw/toto_dream_sample.html")
    except Exception as e:
        print("toto-dream error:", e)

def check_bleague_official_results():
    print("\n--- 2. Testing B.League Official Schedule API for 2022-2024 ---")
    for yr in [2022, 2023, 2024, 2025]:
        url = f"https://www.bleague.jp/schedule/?data_format=json&year={yr}&event=2&tab=1&index=0"
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=10, context=CTX) as r:
                data = json.loads(r.read().decode('utf-8'))
            topics = data.get('topics', [])
            print(f"Year {yr} (event=2): topics count = {len(topics)}")
            if topics:
                with open(f"data/raw/bleague_schedule_{yr}.json", "w", encoding="utf-8") as out:
                    json.dump(data, out, ensure_ascii=False)
        except Exception as e:
            print(f"B.League API error for {yr}:", e)

if __name__ == "__main__":
    os.makedirs("data/raw", exist_ok=True)
    check_toto_dream_winner()
    check_bleague_official_results()
