#!/usr/bin/env python3
"""
src/test_network_fetch.py
Bリーグデータ取得可能性の調査用テストスクリプト
"""
import urllib.request
import json
import ssl

def test():
    ctx = ssl.create_default_context()
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}

    # Test 1: GitHub API for bleaguer
    try:
        url = "https://api.github.com/repos/rintaromasuda/bleaguer/contents"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            data = json.loads(r.read().decode())
            print("GitHub bleaguer contents:", [x['name'] for x in data])
    except Exception as e:
        print("GitHub test error:", e)

    # Test 2: SportsNavi B1 schedule
    try:
        url = "https://sports.yahoo.co.jp/basket/bleague/b1/schedule"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            html = r.read().decode('utf-8')
            print("SportsNavi B1 schedule fetched, len:", len(html))
    except Exception as e:
        print("SportsNavi test error:", e)

    # Test 3: B.League official schedule
    try:
        url = "https://www.bleague.jp/schedule/?tab=1&year_index=2023&event=1"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            html = r.read().decode('utf-8')
            print("B.League official schedule fetched, len:", len(html))
    except Exception as e:
        print("B.League official test error:", e)

if __name__ == "__main__":
    test()
