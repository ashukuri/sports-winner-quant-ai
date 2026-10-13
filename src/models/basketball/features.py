#!/usr/bin/env python3
"""
src/models/basketball/features.py
Bリーグ（B1）特徴量エンジニアリング
- Eloレーティング (時系列Walk-Forward更新)
- 連戦・休養日数 (Back-to-back, Rest days)
- 直近5試合・10試合のローリングアドバンスドスタッツ (Pace, ORtg, DRtg, eFG%, 3P%, TO)
- ホーム/アウェイ差分特徴量
- 16択WINNERクラスインデックス
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
DATA_DIR = os.path.join(BASE_DIR, "data")

BLEAGUE_WINNER_CATEGORIES = [
    "H_1-3", "H_4-6", "H_7-9", "H_10-14", "H_15-19", "H_20-24", "H_25-29", "H_30+",
    "A_1-3", "A_4-6", "A_7-9", "A_10-14", "A_15-19", "A_20-24", "A_25-29", "A_30+"
]

CAT_TO_IDX = {c: i for i, c in enumerate(BLEAGUE_WINNER_CATEGORIES)}
IDX_TO_CAT = {i: c for i, c in enumerate(BLEAGUE_WINNER_CATEGORIES)}

def build_bleague_features(csv_path):
    df = pd.read_csv(csv_path)
    df['date'] = pd.to_datetime(df['date'].str.replace('.', '-'))
    df = df.sort_values(['date', 'schedule_key']).reset_index(drop=True)

    # 1. EloレーティングのWalk-Forward計算
    elo = {}
    elo_k = 20.0
    elo_home_adv = 65.0 # バスケのホームアドバンテージ (約2.5〜3点差相当)

    home_elo_list = []
    away_elo_list = []

    # チーム別直近試合履歴
    team_history = {} # team -> list of {date, pts, opp_pts, diff, pace, ortg, drtg, efg, to, is_home, win}

    # 各試合の特徴量
    feat_rows = []

    for idx, row in df.iterrows():
        h = row['home_team']
        a = row['away_team']
        m_date = row['date']

        # Elo
        h_elo = elo.get(h, 1500.0)
        a_elo = elo.get(a, 1500.0)
        home_elo_list.append(h_elo)
        away_elo_list.append(a_elo)

        # 休養日数
        h_hist = team_history.get(h, [])
        a_hist = team_history.get(a, [])

        h_rest = (m_date - h_hist[-1]['date']).days if len(h_hist) > 0 else 7
        a_rest = (m_date - a_hist[-1]['date']).days if len(a_hist) > 0 else 7
        h_b2b = 1 if h_rest <= 1 else 0
        a_b2b = 1 if a_rest <= 1 else 0

        # 直近5試合スタッツ (リーク防止のため試合前の履歴のみ使用)
        def get_recent_stats(hist, n=5):
            if len(hist) == 0:
                return {
                    f"pts_for_{n}": 78.0, f"pts_against_{n}": 78.0, f"diff_{n}": 0.0,
                    f"pace_{n}": 72.0, f"ortg_{n}": 105.0, f"drtg_{n}": 105.0,
                    f"efg_{n}": 0.50, f"to_{n}": 13.0, f"win_rate_{n}": 0.50
                }
            recent = hist[-n:]
            return {
                f"pts_for_{n}": np.mean([x['pts'] for x in recent]),
                f"pts_against_{n}": np.mean([x['opp_pts'] for x in recent]),
                f"diff_{n}": np.mean([x['diff'] for x in recent]),
                f"pace_{n}": np.mean([x['pace'] for x in recent]),
                f"ortg_{n}": np.mean([x['ortg'] for x in recent]),
                f"drtg_{n}": np.mean([x['drtg'] for x in recent]),
                f"efg_{n}": np.mean([x['efg'] for x in recent]),
                f"to_{n}": np.mean([x['to'] for x in recent]),
                f"win_rate_{n}": np.mean([x['win'] for x in recent])
            }

        h_st5 = get_recent_stats(h_hist, 5)
        a_st5 = get_recent_stats(a_hist, 5)
        h_st10 = get_recent_stats(h_hist, 10)
        a_st10 = get_recent_stats(a_hist, 10)

        # 特徴量辞書
        feat = {
            "schedule_key": row['schedule_key'],
            "season": row['season'],
            "season_year": row['season_year'],
            "date": m_date,
            "home_team": h,
            "away_team": a,
            "home_pts": row['home_pts'],
            "away_pts": row['away_pts'],
            "point_diff": row['point_diff'],
            "winner_category": row['winner_category'],
            "target_cat_idx": CAT_TO_IDX[row['winner_category']],
            "home_win": 1 if row['point_diff'] > 0 else 0,
            
            # Elo
            "home_elo": h_elo,
            "away_elo": a_elo,
            "elo_diff": (h_elo + elo_home_adv) - a_elo,

            # 休養
            "home_rest_days": min(h_rest, 14),
            "away_rest_days": min(a_rest, 14),
            "home_b2b": h_b2b,
            "away_b2b": a_b2b,
            "rest_diff": h_rest - a_rest,

            # 差分スタッツ
            "diff_pts_for_5": h_st5["pts_for_5"] - a_st5["pts_for_5"],
            "diff_pts_against_5": h_st5["pts_against_5"] - a_st5["pts_against_5"],
            "diff_diff_5": h_st5["diff_5"] - a_st5["diff_5"],
            "diff_ortg_5": h_st5["ortg_5"] - a_st5["ortg_5"],
            "diff_drtg_5": h_st5["drtg_5"] - a_st5["drtg_5"],
            "diff_efg_5": h_st5["efg_5"] - a_st5["efg_5"],
            "diff_pace_5": h_st5["pace_5"] - a_st5["pace_5"],
            "diff_win_rate_5": h_st5["win_rate_5"] - a_st5["win_rate_5"],

            # 10試合スタッツ
            "diff_diff_10": h_st10["diff_10"] - a_st10["diff_10"],
            "diff_ortg_10": h_st10["ortg_10"] - a_st10["ortg_10"],
            "diff_drtg_10": h_st10["drtg_10"] - a_st10["drtg_10"],

            # 生スタッツ
            "home_ortg_5": h_st5["ortg_5"],
            "away_ortg_5": a_st5["ortg_5"],
            "home_drtg_5": h_st5["drtg_5"],
            "away_drtg_5": a_st5["drtg_5"],
            "home_pace_5": h_st5["pace_5"],
            "away_pace_5": a_st5["pace_5"],
            "home_efg_5": h_st5["efg_5"],
            "away_efg_5": a_st5["efg_5"]
        }
        feat_rows.append(feat)

        # 試合終了後に Elo と履歴を更新
        # 期待勝率
        e_h = 1.0 / (1.0 + 10.0 ** ((a_elo - (h_elo + elo_home_adv)) / 400.0))
        e_a = 1.0 - e_h
        s_h = 1.0 if row['point_diff'] > 0 else 0.0
        s_a = 1.0 - s_h
        elo[h] = h_elo + elo_k * (s_h - e_h)
        elo[a] = a_elo + elo_k * (s_a - e_a)

        # 履歴追加
        if h not in team_history:
            team_history[h] = []
        if a not in team_history:
            team_history[a] = []

        team_history[h].append({
            "date": m_date, "pts": row['home_pts'], "opp_pts": row['away_pts'],
            "diff": row['point_diff'], "pace": row.get('pace', 72.0),
            "ortg": row.get('home_ortg', 105.0), "drtg": row.get('home_drtg', 105.0),
            "efg": row.get('home_efg', 0.50), "to": row.get('home_to', 13.0),
            "is_home": 1, "win": s_h
        })
        team_history[a].append({
            "date": m_date, "pts": row['away_pts'], "opp_pts": row['home_pts'],
            "diff": -row['point_diff'], "pace": row.get('pace', 72.0),
            "ortg": row.get('away_ortg', 105.0), "drtg": row.get('away_drtg', 105.0),
            "efg": row.get('away_efg', 0.50), "to": row.get('away_to', 13.0),
            "is_home": 0, "win": s_a
        })

    feat_df = pd.DataFrame(feat_rows)
    return feat_df

if __name__ == "__main__":
    csv_path = os.path.join(DATA_DIR, "bleague_matches_2016_2024.csv")
    f_df = build_bleague_features(csv_path)
    out_path = os.path.join(DATA_DIR, "bleague_features.csv")
    f_df.to_csv(out_path, index=False)
    print(f"Features created successfully: {f_df.shape} -> {out_path}")
