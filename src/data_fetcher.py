#!/usr/bin/env python3
"""
src/data_fetcher.py
J.League公式データサイト(data.j-league.or.jp)から過去10年分(2015-2024)のJ1全試合結果を取得・クレンジングするスクリプト
"""

import os
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

DATA_DIR = os.path.join(os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))), "data")

WINNER_CATEGORIES = [
    "1-0", "2-0", "2-1", "3-0", "3-1", "3-2", "other_home_win",
    "0-0", "1-1", "2-2", "other_draw",
    "0-1", "0-2", "1-2", "0-3", "1-3", "2-3", "other_away_win"
]

def score_to_winner_cat(home_score, away_score):
    diff = home_score - away_score
    score_str = f"{home_score}-{away_score}"
    if diff > 0:
        if score_str in ["1-0", "2-0", "2-1", "3-0", "3-1", "3-2"]:
            return score_str
        return "other_home_win"
    elif diff == 0:
        if score_str in ["0-0", "1-1", "2-2"]:
            return score_str
        return "other_draw"
    else:
        if score_str in ["0-1", "0-2", "1-2", "0-3", "1-3", "2-3"]:
            return score_str
        return "other_away_win"

def fetch_season_j1(year):
    url = f"https://data.j-league.or.jp/SFMS01/search?competition_years={year}&competition_frame_ids=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    resp = requests.get(url, headers=headers)
    resp.encoding = "utf-8"
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch {year}: status {resp.status_code}")

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="search-table")
    if not table:
        raise ValueError(f"Table not found for year {year}")

    rows = table.find_all("tr")
    matches = []

    for r in rows[1:]:
        cols = [td.text.strip() for td in r.find_all(["th", "td"])]
        if len(cols) < 9:
            continue
        
        # cols: ['シーズン', '大会', '節', '試合日', 'K/O時刻', 'ホーム', 'スコア', 'アウェイ', 'スタジアム', '入場者数', ...]
        season = int(cols[0])
        comp = cols[1]
        sec_str = cols[2]
        date_raw = cols[3]
        ko_time = cols[4]
        home_team = cols[5]
        score_raw = cols[6]
        away_team = cols[7]
        stadium = cols[8]
        attendance_raw = cols[9] if len(cols) > 9 else ""

        # スコアパース (例: "2-0", "1-1")
        if "-" not in score_raw:
            continue  # 未開催または中止
        try:
            parts = score_raw.split("-")
            h_score = int(parts[0].strip())
            a_score = int(parts[1].strip())
        except Exception:
            continue

        # 日付パース: "24/02/23(金・祝)" -> "2024-02-23"
        # 形式: YY/MM/DD(...)
        m_date = None
        match_dt = re.search(r"(\d{2})/(\d{2})/(\d{2})", date_raw)
        if match_dt:
            yy = int(match_dt.group(1)) + 2000
            mm = int(match_dt.group(2))
            dd = int(match_dt.group(3))
            m_date = f"{yy:04d}-{mm:02d}-{dd:02d}"
        else:
            m_date = f"{season}-01-01"

        # 1X2 結果
        if h_score > a_score:
            res_1x2 = "H"
        elif h_score == a_score:
            res_1x2 = "D"
        else:
            res_1x2 = "A"

        # WINNER 18択カテゴリ
        winner_cat = score_to_winner_cat(h_score, a_score)

        # 観客動員数
        att = None
        clean_att = re.sub(r"[^\d]", "", attendance_raw)
        if clean_att:
            att = int(clean_att)

        matches.append({
            "season": season,
            "competition": comp,
            "section": sec_str,
            "match_date": m_date,
            "kick_off_time": ko_time,
            "home_team": home_team,
            "away_team": away_team,
            "home_score": h_score,
            "away_score": a_score,
            "total_goals": h_score + a_score,
            "result_1x2": res_1x2,
            "winner_category": winner_cat,
            "stadium": stadium,
            "attendance": att
        })

    print(f"[FETCH] Season {year}: {len(matches)} matches fetched.")
    return matches

def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    all_matches = []
    years = list(range(2015, 2025))  # 2015から2024年 (10シーズン)

    for y in years:
        m_list = fetch_season_j1(y)
        all_matches.extend(m_list)
        time.sleep(0.5)

    df = pd.DataFrame(all_matches)
    # 日付・キックオフ順にソート
    df["dt_sort"] = pd.to_datetime(df["match_date"] + " " + df["kick_off_time"].fillna("14:00"), errors="coerce")
    df = df.sort_values("dt_sort").reset_index(drop=True)
    df["match_id"] = range(1, len(df) + 1)
    df = df.drop(columns=["dt_sort"])

    csv_path = os.path.join(DATA_DIR, "jleague_matches_2015_2024.csv")
    df.to_csv(csv_path, index=False)
    print(f"\n[SUCCESS] Total {len(df)} matches saved to {csv_path}")
    print(f"Season distribution:\n{df['season'].value_counts().sort_index()}")
    print(f"\n1X2 Distribution:\n{df['result_1x2'].value_counts(normalize=True)}")
    print(f"\nTop 5 WINNER categories:\n{df['winner_category'].value_counts().head(5)}")

if __name__ == "__main__":
    main()
