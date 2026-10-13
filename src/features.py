#!/usr/bin/env python3
"""
src/features.py
サッカー試合データの前処理、動的Eloレーティング、直近パフォーマンス特徴量、
および市場オッズのマージン除去（正規化確率）を生成するモジュール
"""

import numpy as np
import pandas as pd
from datetime import datetime

TEAM_NAME_MAP = {
    'FC東京': 'FC Tokyo', '京都': 'Kyoto', '仙台': 'Vegalta Sendai', '名古屋': 'Nagoya Grampus',
    '大分': 'Oita Trinita', '大宮': 'Omiya Ardija', '山形': 'Montedio Yamagata', '川崎Ｆ': 'Kawasaki Frontale',
    '広島': 'Sanfrecce Hiroshima', '徳島': 'Tokushima', '新潟': 'Albirex Niigata', '札幌': 'Hokkaido Consadole Sapporo',
    '東京Ｖ': 'Verdy', '松本': 'Yamaga', '柏': 'Kashiwa Reysol', '横浜FC': 'Yokohama FC',
    '横浜FM': 'Yokohama F. Marinos', '浦和': 'Urawa Reds', '清水': 'Shimizu S-Pulse', '湘南': 'Shonan Bellmare',
    '甲府': 'Kofu', '町田': 'Machida', '磐田': 'Iwata', '神戸': 'Vissel Kobe',
    '福岡': 'Avispa Fukuoka', '長崎': 'V-Varen Nagasaki', '鳥栖': 'Sagan Tosu', '鹿島': 'Kashima Antlers',
    'Ｃ大阪': 'Cerezo Osaka', 'Ｇ大阪': 'Gamba Osaka'
}

class EloTracker:
    def __init__(self, k_factor=20.0, home_adv=65.0, initial_elo=1500.0):
        self.k_factor = k_factor
        self.home_adv = home_adv
        self.initial_elo = initial_elo
        self.ratings = {}

    def get_rating(self, team):
        return self.ratings.get(team, self.initial_elo)

    def expected_result(self, r_home, r_away):
        # ホームアドバンテージを加味
        dr = (r_home + self.home_adv) - r_away
        return 1.0 / (1.0 + 10.0 ** (-dr / 400.0))

    def update(self, home_team, away_team, result_1x2):
        r_h = self.get_rating(home_team)
        r_a = self.get_rating(away_team)
        exp_h = self.expected_result(r_h, r_a)

        # 実際のスコア (H: 1.0, D: 0.5, A: 0.0)
        actual_h = 1.0 if result_1x2 == 'H' else (0.5 if result_1x2 == 'D' else 0.0)
        actual_a = 1.0 - actual_h
        exp_a = 1.0 - exp_h

        # レート更新
        new_r_h = r_h + self.k_factor * (actual_h - exp_h)
        new_r_a = r_a + self.k_factor * (actual_a - exp_a)

        self.ratings[home_team] = new_r_h
        self.ratings[away_team] = new_r_a

def remove_bookmaker_margin(odds_h, odds_d, odds_a):
    """
    ブックメーカーオッズから比例正規化（Overround除去）により公平確率を算出
    """
    if pd.isna(odds_h) or pd.isna(odds_d) or pd.isna(odds_a) or odds_h <= 1.0 or odds_d <= 1.0 or odds_a <= 1.0:
        return np.nan, np.nan, np.nan
    inv_h, inv_d, inv_a = 1.0 / odds_h, 1.0 / odds_d, 1.0 / odds_a
    total_inv = inv_h + inv_d + inv_a
    return inv_h / total_inv, inv_d / total_inv, inv_a / total_inv

def build_dataset_with_features(matches_csv, football_data_csv):
    df_j = pd.read_csv(matches_csv)
    df_fd = pd.read_csv(football_data_csv)
    df_fd = df_fd[df_fd['League'] == 'J1 League'].copy()
    df_fd['Season'] = df_fd['Season'].astype(str)
    df_j['season'] = df_j['season'].astype(str)

    df_j['home_en'] = df_j['home_team'].map(TEAM_NAME_MAP)
    df_j['away_en'] = df_j['away_team'].map(TEAM_NAME_MAP)

    # オッズデータのマージ
    merged = pd.merge(df_j, df_fd[['Season', 'Home', 'Away', 'PSCH', 'PSCD', 'PSCA', 'AvgCH', 'AvgCD', 'AvgCA', 'MaxCH', 'MaxCD', 'MaxCA']],
                      left_on=['season', 'home_en', 'away_en'],
                      right_on=['Season', 'Home', 'Away'],
                      how='left')

    # 市場確率の計算 (Pinnacle最優先、なければAvgオッズ)
    market_probs_h = []
    market_probs_d = []
    market_probs_a = []

    for _, row in merged.iterrows():
        oh, od, oa = row['PSCH'], row['PSCD'], row['PSCA']
        if pd.isna(oh):
            oh, od, oa = row['AvgCH'], row['AvgCD'], row['AvgCA']
        ph, pd_, pa = remove_bookmaker_margin(oh, od, oa)
        market_probs_h.append(ph)
        market_probs_d.append(pd_)
        market_probs_a.append(pa)

    merged['market_prob_H'] = market_probs_h
    merged['market_prob_D'] = market_probs_d
    merged['market_prob_A'] = market_probs_a

    # 日付ソート
    merged['match_dt'] = pd.to_datetime(merged['match_date'])
    merged = merged.sort_values('match_dt').reset_index(drop=True)

    # Walk-Forward 特徴量生成 (Elo, 直近得失点, 休養日数)
    elo_tracker = EloTracker(k_factor=20.0, home_adv=65.0)
    
    # チーム別履歴トラッカー
    team_history = {} # team -> list of {dt, goals_for, goals_against, points, is_home}

    home_elo_list, away_elo_list, elo_diff_list = [], [], []
    home_rest_list, away_rest_list = [], []
    home_gf_5, home_ga_5, home_pts_5 = [], [], []
    away_gf_5, away_ga_5, away_pts_5 = [], [], []
    home_gf_10, home_ga_10 = [], []
    away_gf_10, away_ga_10 = [], []

    for idx, row in merged.iterrows():
        h_team = row['home_team']
        a_team = row['away_team']
        cur_dt = row['match_dt']
        res = row['result_1x2']

        # 1. 試合前のElo
        r_h = elo_tracker.get_rating(h_team)
        r_a = elo_tracker.get_rating(a_team)
        home_elo_list.append(r_h)
        away_elo_list.append(r_a)
        elo_diff_list.append(r_h + elo_tracker.home_adv - r_a)

        # 2. 直近パフォーマンスと休養日数 (試合前)
        h_hist = team_history.get(h_team, [])
        a_hist = team_history.get(a_team, [])

        # 休養日数
        if len(h_hist) > 0:
            h_rest = (cur_dt - h_hist[-1]['dt']).days
        else:
            h_rest = 7
        if len(a_hist) > 0:
            a_rest = (cur_dt - a_hist[-1]['dt']).days
        else:
            a_rest = 7
        home_rest_list.append(min(h_rest, 30))
        away_rest_list.append(min(a_rest, 30))

        # 直近5試合
        def get_recent_stats(hist, n=5):
            if len(hist) == 0:
                return 1.3, 1.3, 1.3  # J1平均デフォルト
            sub = hist[-n:]
            avg_gf = np.mean([x['gf'] for x in sub])
            avg_ga = np.mean([x['ga'] for x in sub])
            avg_pts = np.mean([x['pts'] for x in sub])
            return avg_gf, avg_ga, avg_pts

        h_gf5, h_ga5, h_p5 = get_recent_stats(h_hist, 5)
        a_gf5, a_ga5, a_p5 = get_recent_stats(a_hist, 5)
        h_gf10, h_ga10, _ = get_recent_stats(h_hist, 10)
        a_gf10, a_ga10, _ = get_recent_stats(a_hist, 10)

        home_gf_5.append(h_gf5)
        home_ga_5.append(h_ga5)
        home_pts_5.append(h_p5)
        away_gf_5.append(a_gf5)
        away_ga_5.append(a_ga5)
        away_pts_5.append(a_p5)
        home_gf_10.append(h_gf10)
        home_ga_10.append(h_ga10)
        away_gf_10.append(a_gf10)
        away_ga_10.append(a_ga10)

        # 試合終了後の履歴更新
        h_pts = 3 if res == 'H' else (1 if res == 'D' else 0)
        a_pts = 3 if res == 'A' else (1 if res == 'D' else 0)
        if h_team not in team_history: team_history[h_team] = []
        if a_team not in team_history: team_history[a_team] = []
        team_history[h_team].append({'dt': cur_dt, 'gf': row['home_score'], 'ga': row['away_score'], 'pts': h_pts, 'is_home': 1})
        team_history[a_team].append({'dt': cur_dt, 'gf': row['away_score'], 'ga': row['home_score'], 'pts': a_pts, 'is_home': 0})

        # Elo更新
        elo_tracker.update(h_team, a_team, res)

    merged['home_elo'] = home_elo_list
    merged['away_elo'] = away_elo_list
    merged['elo_diff'] = elo_diff_list
    merged['home_rest_days'] = home_rest_list
    merged['away_rest_days'] = away_rest_list
    merged['rest_diff'] = np.array(home_rest_list) - np.array(away_rest_list)
    merged['home_gf_5'] = home_gf_5
    merged['home_ga_5'] = home_ga_5
    merged['home_pts_5'] = home_pts_5
    merged['away_gf_5'] = away_gf_5
    merged['away_ga_5'] = away_ga_5
    merged['away_pts_5'] = away_pts_5
    merged['home_gf_10'] = home_gf_10
    merged['home_ga_10'] = home_ga_10
    merged['away_gf_10'] = away_gf_10
    merged['away_ga_10'] = away_ga_10

    # スプリットフラグ (Train: 2015-2021, Val: 2022, Test: 2023-2024)
    merged['season_int'] = merged['season'].astype(int)
    conditions = [
        (merged['season_int'] <= 2021),
        (merged['season_int'] == 2022),
        (merged['season_int'] >= 2023)
    ]
    choices = ['train', 'val', 'test']
    merged['split'] = np.select(conditions, choices, default='train')

    return merged
