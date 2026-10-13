#!/usr/bin/env python3
"""
src/fetch_bleague_multi_season.py
Bリーグ公式サイトから 2022-23 〜 2026-27 (直近) の公式試合結果を網羅的に取得し、
公式スコア、点差、OT有無、および公式16選択肢を構造化して保存するスクリプト。
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
from datetime import datetime, timedelta

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
DATA_DIR = os.path.join(BASE_DIR, "data")
VERIFIED_DIR = os.path.join(DATA_DIR, "verified")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
CTX = ssl.create_default_context()

def get_bleague_winner_category(home_pts, away_pts):
    diff = home_pts - away_pts
    if diff == 0:
        return "DRAW_INVALID"
    is_home = (diff > 0)
    abs_diff = abs(diff)
    if 1 <= abs_diff <= 3: band = "1-3"
    elif 4 <= abs_diff <= 6: band = "4-6"
    elif 7 <= abs_diff <= 9: band = "7-9"
    elif 10 <= abs_diff <= 14: band = "10-14"
    elif 15 <= abs_diff <= 19: band = "15-19"
    elif 20 <= abs_diff <= 24: band = "20-24"
    elif 25 <= abs_diff <= 29: band = "25-29"
    else: band = "30+"
    prefix = "H" if is_home else "A"
    return f"{prefix}_{band}"

def fetch_season_dates(start_year, end_year):
    """
    指定期間の全対象日程（10月〜翌年5月）を走査して試合結果を取得
    """
    all_matches = []
    seen_keys = set()

    # シーズン定義: (開始年, 終了年)
    seasons = [
        ("2022-23", 2022, 2023),
        ("2023-24", 2023, 2024),
        ("2024-25", 2024, 2025),
        ("2025-26", 2025, 2026),
        ("2026-27", 2026, 2026) # 2026年10月13日以前の直近試合
    ]

    for s_label, sy, ey in seasons:
        if sy < start_year or sy > end_year:
            continue
        print(f"\n=== Fetching Season {s_label} ===")

        # 試合のある月: 10, 11, 12, 1, 2, 3, 4, 5
        months_to_check = [10, 11, 12] if sy == 2026 else [10, 11, 12, 1, 2, 3, 4, 5]
        
        for mon in months_to_check:
            cur_yr = sy if mon >= 10 else ey
            # 日の範囲: 主に水・金・土・日・月 (1〜31日)
            # 効率化のため、各月の全日（1〜31日）を走査
            # 2026年10月は13日以前まで
            max_day = 13 if (cur_yr == 2026 and mon == 10) else 31

            for day in range(1, max_day + 1):
                # B1 (event=2 または event=1)
                for ev in [2, 1]:
                    url = f"https://www.bleague.jp/schedule/?data_format=json&year={cur_yr}&mon={mon:02d}&day={day:02d}&event={ev}&tab=1"
                    try:
                        req = urllib.request.Request(url, headers=HEADERS)
                        with urllib.request.urlopen(req, timeout=5, context=CTX) as r:
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
                                    continue # 未開催または中止試合

                                h_pts = int(pts[0])
                                a_pts = int(pts[1])
                                if h_pts == a_pts:
                                    continue

                                h_name = h_span.get_text().strip()
                                a_name = a_span.get_text().strip()
                                is_ot = 1 if "OT" in s_text else 0
                                w_cat = get_bleague_winner_category(h_pts, a_pts)

                                match_date = f"{cur_yr}-{mon:02d}-{day:02d}"

                                all_matches.append({
                                    "schedule_key": sk,
                                    "season": s_label,
                                    "season_year": sy,
                                    "date": match_date,
                                    "home_team": h_name,
                                    "away_team": a_name,
                                    "home_pts": h_pts,
                                    "away_pts": a_pts,
                                    "point_diff": h_pts - a_pts,
                                    "total_pts": h_pts + a_pts,
                                    "winner_category": w_cat,
                                    "is_ot": is_ot,
                                    "event_id": ev
                                })
                                seen_keys.add(sk)
                    except Exception as e:
                        pass # 通信エラー等はスキップ

            print(f"  {cur_yr}-{mon:02d}: cumulative matches = {len(all_matches)}")

    df = pd.DataFrame(all_matches)
    if len(df) > 0:
        df = df.sort_values(["season_year", "date"]).reset_index(drop=True)
    return df

if __name__ == "__main__":
    os.makedirs(VERIFIED_DIR, exist_ok=True)
    # 2022-23 〜 2026-27 (直近)
    df_new = fetch_season_dates(2022, 2026)
    out_path = os.path.join(VERIFIED_DIR, "bleague_matches_2022_2026.csv")
    df_new.to_csv(out_path, index=False)
    print(f"\nSaved {len(df_new)} verified matches to {out_path}")
