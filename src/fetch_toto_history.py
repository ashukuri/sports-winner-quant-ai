#!/usr/bin/env python3
"""
src/fetch_toto_history.py
楽天totoバックナンバーからtoto / mini toto開催結果・当せん金データを確実に取得・保存するスクリプト
"""

import os
import re
import json
import time
import requests
from bs4 import BeautifulSoup

DATA_DIR = os.path.join(os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))), "data")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
}

def clean_currency(txt):
    nums = re.sub(r"[^\d]", "", txt)
    return int(nums) if nums else 0

def fetch_toto_round(round_num):
    url = f"https://toto.rakuten.co.jp/toto/result/{round_num}/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        tables = soup.find_all('table')
        if len(tables) < 6:
            return None

        # Table 0: toto 当せん金
        # Table 2: toto 13試合
        # Table 3: mini toto-A 当せん金
        # Table 5: mini toto-A 5試合
        
        t2_rows = tables[2].find_all('tr')
        toto_matches = []
        for row in t2_rows[1:]:
            cols = [c.text.strip() for c in row.find_all(['th', 'td'])]
            if len(cols) >= 6:
                raw_res = cols[5]
                res_char = 'H' if raw_res == '1' else ('D' if raw_res == '0' else 'A')
                toto_matches.append({
                    "no": cols[0],
                    "home": cols[1],
                    "score": cols[2],
                    "away": cols[3],
                    "result": res_char
                })

        def get_payout(table_elem):
            p1, p2, p3 = 0, 0, 0
            for row in table_elem.find_all('tr'):
                c = [td.text.strip() for td in row.find_all(['th', 'td'])]
                if len(c) >= 2:
                    if '1等' in c[0]: p1 = clean_currency(c[1])
                    elif '2等' in c[0]: p2 = clean_currency(c[1])
                    elif '3等' in c[0]: p3 = clean_currency(c[1])
            return p1, p2, p3

        p_toto1, p_toto2, p_toto3 = get_payout(tables[0])
        p_mini_a, _, _ = get_payout(tables[3])

        # mini toto A組 5試合
        mini_a_matches = []
        for row in tables[5].find_all('tr')[1:]:
            cols = [c.text.strip() for c in row.find_all(['th', 'td'])]
            if len(cols) >= 6:
                raw_res = cols[5]
                res_char = 'H' if raw_res == '1' else ('D' if raw_res == '0' else 'A')
                mini_a_matches.append({
                    "no": cols[0], "home": cols[1], "score": cols[2], "away": cols[3], "result": res_char
                })

        return {
            "round": round_num,
            "toto_13_matches": toto_matches,
            "toto_payout_1st": p_toto1,
            "toto_payout_2nd": p_toto2,
            "toto_payout_3rd": p_toto3,
            "mini_a_matches": mini_a_matches,
            "mini_a_payout_1st": p_mini_a
        }
    except Exception:
        return None

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    json_path = os.path.join(DATA_DIR, "toto_history.json")

    round_nums = []
    for y in [2023, 2024]:
        url = f"https://toto.rakuten.co.jp/toto/result/list/{y}/"
        r = requests.get(url, headers=HEADERS)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            tables = soup.find_all('table')
            for t in tables:
                for a in t.find_all('a'):
                    href = a.get('href', '')
                    m = re.search(r'/toto/result/(\d+)/', href)
                    if m:
                        round_nums.append(int(m.group(1)))

    round_nums = sorted(list(set(round_nums)))
    print(f"[TOTO] Found {len(round_nums)} rounds for 2023-2024.")

    # 最終テスト期間の全開催回（約40回分）を取得
    target_rounds = round_nums[-40:] if len(round_nums) > 40 else round_nums
    print(f"[TOTO] Fetching details for {len(target_rounds)} target rounds...")

    fetched_records = []
    for idx, rnd in enumerate(target_rounds, 1):
        rec = fetch_toto_round(rnd)
        if rec and len(rec['toto_13_matches']) == 13:
            fetched_records.append(rec)
        time.sleep(0.15)
        if idx % 10 == 0:
            print(f"  Fetched {idx}/{len(target_rounds)} rounds...")

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(fetched_records, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] Saved {len(fetched_records)} toto rounds to {json_path}")

if __name__ == "__main__":
    main()
