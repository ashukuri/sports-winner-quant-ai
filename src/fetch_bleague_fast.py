#!/usr/bin/env python3
"""
src/fetch_bleague_fast.py
Bリーグ公式APIから 2022-23 〜 2025-26、および2026-27（直近）の試合結果を
水・金・土・日（試合開催日）に絞って高速かつ確実に取得するスクリプト。
"""

import os
import sys
import time
import json
import urllib.request
import ssl
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime, date, timedelta

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
DATA_DIR = os.path.join(BASE_DIR, "data")
VERIFIED_DIR = os.path.join(DATA_DIR, "verified")

HEADERS = {'User-Agent': 'Mozilla/5.0'}
CTX = ssl.create_default_context()

def get_bleague_winner_category(home_pts, away_pts):
    diff = home_pts - away_pts
    if diff == 0:
        return "DRAW_INVALID"
    is_home = (diff > 0)
    adiff = abs(diff)
    if 1 <= adiff <= 3: band = "1-3"
    elif 4 <= adiff <= 6: band = "4-6"
    elif 7 <= adiff <= 9: band = "7-9"
    elif 10 <= adiff <= 14: band = "10-14"
    elif 15 <= adiff <= 19: band = "15-19"
    elif 20 <= adiff <= 24: band = "20-24"
    elif 25 <= adiff <= 29: band = "25-29"
    else: band = "30+"
    prefix = "H" if is_home else "A"
    return f"{prefix}_{band}"

def fetch_fast():
    os.makedirs(VERIFIED_DIR, exist_ok=True)
    all_matches = []
    seen_keys = set()

    # シーズン設定
    # 2022-23: 2022-10-01 〜 2023-05-10
    # 2023-24: 2023-10-01 〜 2024-05-10
    # 2024-25: 2024-10-01 〜 2025-05-10
    # 2025-26: 2025-10-01 〜 2026-05-10
    # 2026-27: 2026-10-01 〜 2026-10-13 (直近開幕節)

    season_periods = [
        ("2022-23", date(2022, 10, 1), date(2023, 5, 10)),
        ("2023-24", date(2023, 10, 1), date(2024, 5, 10)),
        ("2024-25", date(2024, 10, 1), date(2025, 5, 10)),
        ("2025-26", date(2025, 10, 1), date(2026, 5, 10)),
        ("2026-27", date(2026, 10, 1), date(2026, 10, 13))
    ]

    for s_label, d_start, d_end in season_periods:
        cur_d = d_start
        s_matches = 0
        print(f"\nScanning {s_label} ({d_start} to {d_end})...")

        while cur_d <= d_end:
            # 水(2), 金(4), 土(5), 日(6) のみ走査
            if cur_d.weekday() in [2, 4, 5, 6]:
                yr = cur_d.year
                mon = cur_d.month
                day = cur_d.day

                url = f"https://www.bleague.jp/schedule/?data_format=json&year={yr}&mon={mon:02d}&day={day:02d}&event=2&tab=1"
                try:
                    req = urllib.request.Request(url, headers=HEADERS)
                    with urllib.request.urlopen(req, timeout=4, context=CTX) as r:
                        data = json.loads(r.read().decode('utf-8'))
                    topics = data.get('topics', [])
                    for chunk in topics:
                        soup = BeautifulSoup(chunk, 'html.parser')
                        for it in soup.find_all('li', class_='list-item'):
                            sk = it.get('id')
                            if not sk or sk in seen_keys:
                                continue

                            h_span = it.find('span', class_='team home')
                            a_span = it.find('span', class_='team away')
                            s_div = it.find('div', class_='score')

                            if not h_span or not a_span or not s_div:
                                continue

                            s_text = s_div.get_text().strip()
                            pts = re.findall(r'\d+', s_text)
                            if len(pts) < 2:
                                continue

                            h_pts = int(pts[0])
                            a_pts = int(pts[1])
                            if h_pts == a_pts:
                                continue

                            h_name = h_span.get_text().strip()
                            a_name = a_span.get_text().strip()
                            is_ot = 1 if "OT" in s_text else 0
                            w_cat = get_bleague_winner_category(h_pts, a_pts)

                            all_matches.append({
                                "schedule_key": sk,
                                "season": s_label,
                                "season_year": d_start.year,
                                "date": cur_d.strftime("%Y-%m-%d"),
                                "home_team": h_name,
                                "away_team": a_name,
                                "home_pts": h_pts,
                                "away_pts": a_pts,
                                "point_diff": h_pts - a_pts,
                                "total_pts": h_pts + a_pts,
                                "winner_category": w_cat,
                                "is_ot": is_ot
                            })
                            seen_keys.add(sk)
                            s_matches += 1
                except Exception as e:
                    pass
            cur_d += timedelta(days=1)

        print(f"Season {s_label}: collected {s_matches} official matches (cumulative {len(all_matches)})")

    df = pd.DataFrame(all_matches)
    out_path = os.path.join(VERIFIED_DIR, "bleague_matches_2022_2026.csv")
    df.to_csv(out_path, index=False)
    print(f"\nFinal collected: {len(df)} matches saved to {out_path}")
    return df

if __name__ == "__main__":
    fetch_fast()
