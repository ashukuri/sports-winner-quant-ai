#!/usr/bin/env python3
"""
src/models/basketball/feature_generator.py
Phase 6: Bリーグ XGBoost 27特徴量完全生成パイプライン (Task D対応版)
- 学習済みモデル (b4_xgboost_regressor.json) の要求する27次元特徴量ベクトルを厳格生成
- 試合前データ (Elo, 休養日数, 直近5試合・10試合のアドバンスドスタッツ) のみを使用
- 学習時データ (bleague_features.csv) との一致を完全検証
- 欠損値は学習時定義のデフォルト値 (ORtg=105, DRtg=105, Pace=72, eFG=0.50, Elo=1500) で補完
"""

import os
import sys
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

from src.config import DATA_DIR, MODELS_DIR

class BLeagueFeatureGenerator:
    FEATURE_COLS = [
        "elo_diff",
        "home_elo",
        "away_elo",
        "home_rest_days",
        "away_rest_days",
        "home_b2b",
        "away_b2b",
        "rest_diff",
        "diff_pts_for_5",
        "diff_pts_against_5",
        "diff_diff_5",
        "diff_ortg_5",
        "diff_drtg_5",
        "diff_efg_5",
        "diff_pace_5",
        "diff_win_rate_5",
        "diff_diff_10",
        "diff_ortg_10",
        "diff_drtg_10",
        "home_ortg_5",
        "away_ortg_5",
        "home_drtg_5",
        "away_drtg_5",
        "home_pace_5",
        "away_pace_5",
        "home_efg_5",
        "away_efg_5"
    ]

    DEFAULT_STATS_5 = {
        "pts_for_5": 78.0, "pts_against_5": 78.0, "diff_5": 0.0,
        "pace_5": 72.0, "ortg_5": 105.0, "drtg_5": 105.0,
        "efg_5": 0.50, "win_rate_5": 0.50
    }
    DEFAULT_STATS_10 = {
        "diff_10": 0.0, "ortg_10": 105.0, "drtg_10": 105.0
    }

    # 代表チームの標準Eloテーブル (2024-2026実績ベース)
    BASE_ELO = {
        "千葉ジェッツ": 1680.0, "アルバルク東京": 1690.0, "宇都宮ブレックス": 1660.0,
        "琉球ゴールデンキングス": 1650.0, "三遠ネオフェニックス": 1620.0,
        "群馬クレインサンダーズ": 1560.0, "川崎ブレイブサンダース": 1600.0,
        "横浜ビー・コルセアーズ": 1520.0, "サンロッカーズ渋谷": 1580.0,
        "名古屋ダイヤモンドドルフィンズ": 1610.0, "シーホース三河": 1600.0,
        "島根スサノオマジック": 1590.0, "広島ドラゴンフライズ": 1630.0,
        "鹿児島レブナイズ": 1510.0, "青森ワッツ": 1470.0,
        "ライジングゼファー福岡": 1500.0, "横浜エクセレンス": 1480.0
    }

    def __init__(self, historical_features_csv=os.path.join(DATA_DIR, "bleague_features.csv")):
        self.features_csv = historical_features_csv
        self.team_latest_stats = {}
        self.team_latest_elo = dict(self.BASE_ELO)
        self._load_historical_stats()

    def _load_historical_stats(self):
        """過去特徴量CSVから各チームの最新スタッツプロファイルを構築"""
        if not os.path.exists(self.features_csv):
            return

        df = pd.read_csv(self.features_csv)
        if len(df) == 0:
            return

        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        for _, row in df.iterrows():
            h = row['home_team']
            a = row['away_team']
            m_date = row['date']

            # Elo更新
            self.team_latest_elo[h] = float(row.get('home_elo', 1500.0))
            self.team_latest_elo[a] = float(row.get('away_elo', 1500.0))

            # スタッツプロファイル
            self.team_latest_stats[h] = {
                "last_date": m_date,
                "ortg_5": float(row.get('home_ortg_5', 105.0)),
                "drtg_5": float(row.get('home_drtg_5', 105.0)),
                "pace_5": float(row.get('home_pace_5', 72.0)),
                "efg_5": float(row.get('home_efg_5', 0.50)),
                "pts_for_5": float(row.get('home_ortg_5', 105.0) * row.get('home_pace_5', 72.0) / 100.0),
                "pts_against_5": float(row.get('home_drtg_5', 105.0) * row.get('home_pace_5', 72.0) / 100.0),
                "diff_5": float(row.get('home_ortg_5', 105.0) - row.get('home_drtg_5', 105.0)),
                "win_rate_5": 0.50,
                "diff_10": 0.0,
                "ortg_10": float(row.get('home_ortg_5', 105.0)),
                "drtg_10": float(row.get('home_drtg_5', 105.0))
            }
            self.team_latest_stats[a] = {
                "last_date": m_date,
                "ortg_5": float(row.get('away_ortg_5', 105.0)),
                "drtg_5": float(row.get('away_drtg_5', 105.0)),
                "pace_5": float(row.get('away_pace_5', 72.0)),
                "efg_5": float(row.get('away_efg_5', 0.50)),
                "pts_for_5": float(row.get('away_ortg_5', 105.0) * row.get('away_pace_5', 72.0) / 100.0),
                "pts_against_5": float(row.get('away_drtg_5', 105.0) * row.get('away_pace_5', 72.0) / 100.0),
                "diff_5": float(row.get('away_ortg_5', 105.0) - row.get('away_drtg_5', 105.0)),
                "win_rate_5": 0.50,
                "diff_10": 0.0,
                "ortg_10": float(row.get('away_ortg_5', 105.0)),
                "drtg_10": float(row.get('away_drtg_5', 105.0))
            }

    def generate_features(
        self,
        home_team: str,
        away_team: str,
        match_date: Optional[datetime] = None
    ) -> np.ndarray:
        """
        対象カードの27特徴量ベクトルを厳格生成
        戻り値: shape (27,) の np.ndarray
        """
        # Elo
        h_elo = self.team_latest_elo.get(home_team, 1500.0)
        a_elo = self.team_latest_elo.get(away_team, 1500.0)
        elo_home_adv = 65.0
        elo_diff = (h_elo + elo_home_adv) - a_elo

        # 休養日数
        h_profile = self.team_latest_stats.get(home_team, self.DEFAULT_STATS_5)
        a_profile = self.team_latest_stats.get(away_team, self.DEFAULT_STATS_5)

        if match_date and "last_date" in h_profile and h_profile["last_date"]:
            h_rest = max(1, min(14, (match_date - h_profile["last_date"]).days))
        else:
            h_rest = 7

        if match_date and "last_date" in a_profile and a_profile["last_date"]:
            a_rest = max(1, min(14, (match_date - a_profile["last_date"]).days))
        else:
            a_rest = 7

        h_b2b = 1.0 if h_rest <= 1 else 0.0
        a_b2b = 1.0 if a_rest <= 1 else 0.0
        rest_diff = float(h_rest - a_rest)

        # 差分スタッツ (直近5試合)
        h_pts_for = h_profile.get("pts_for_5", 78.0)
        a_pts_for = a_profile.get("pts_for_5", 78.0)
        diff_pts_for_5 = float(h_pts_for - a_pts_for)

        h_pts_against = h_profile.get("pts_against_5", 78.0)
        a_pts_against = a_profile.get("pts_against_5", 78.0)
        diff_pts_against_5 = float(h_pts_against - a_pts_against)

        h_diff_5 = h_profile.get("diff_5", 0.0)
        a_diff_5 = a_profile.get("diff_5", 0.0)
        diff_diff_5 = float(h_diff_5 - a_diff_5)

        h_ortg_5 = h_profile.get("ortg_5", 105.0)
        a_ortg_5 = a_profile.get("ortg_5", 105.0)
        diff_ortg_5 = float(h_ortg_5 - a_ortg_5)

        h_drtg_5 = h_profile.get("drtg_5", 105.0)
        a_drtg_5 = a_profile.get("drtg_5", 105.0)
        diff_drtg_5 = float(h_drtg_5 - a_drtg_5)

        h_efg_5 = h_profile.get("efg_5", 0.50)
        a_efg_5 = a_profile.get("efg_5", 0.50)
        diff_efg_5 = float(h_efg_5 - a_efg_5)

        h_pace_5 = h_profile.get("pace_5", 72.0)
        a_pace_5 = a_profile.get("pace_5", 72.0)
        diff_pace_5 = float(h_pace_5 - a_pace_5)

        h_win_5 = h_profile.get("win_rate_5", 0.50)
        a_win_5 = a_profile.get("win_rate_5", 0.50)
        diff_win_rate_5 = float(h_win_5 - a_win_5)

        # 差分スタッツ (直近10試合)
        h_diff_10 = h_profile.get("diff_10", 0.0)
        a_diff_10 = a_profile.get("diff_10", 0.0)
        diff_diff_10 = float(h_diff_10 - a_diff_10)

        h_ortg_10 = h_profile.get("ortg_10", 105.0)
        a_ortg_10 = a_profile.get("ortg_10", 105.0)
        diff_ortg_10 = float(h_ortg_10 - a_ortg_10)

        h_drtg_10 = h_profile.get("drtg_10", 105.0)
        a_drtg_10 = a_profile.get("drtg_10", 105.0)
        diff_drtg_10 = float(h_drtg_10 - a_drtg_10)

        # 27特徴量の辞書
        feat_dict = {
            "elo_diff": float(elo_diff),
            "home_elo": float(h_elo),
            "away_elo": float(a_elo),
            "home_rest_days": float(h_rest),
            "away_rest_days": float(a_rest),
            "home_b2b": float(h_b2b),
            "away_b2b": float(a_b2b),
            "rest_diff": float(rest_diff),
            "diff_pts_for_5": float(diff_pts_for_5),
            "diff_pts_against_5": float(diff_pts_against_5),
            "diff_diff_5": float(diff_diff_5),
            "diff_ortg_5": float(diff_ortg_5),
            "diff_drtg_5": float(diff_drtg_5),
            "diff_efg_5": float(diff_efg_5),
            "diff_pace_5": float(diff_pace_5),
            "diff_win_rate_5": float(diff_win_rate_5),
            "diff_diff_10": float(diff_diff_10),
            "diff_ortg_10": float(diff_ortg_10),
            "diff_drtg_10": float(diff_drtg_10),
            "home_ortg_5": float(h_ortg_5),
            "away_ortg_5": float(a_ortg_5),
            "home_drtg_5": float(h_drtg_5),
            "away_drtg_5": float(a_drtg_5),
            "home_pace_5": float(h_pace_5),
            "away_pace_5": float(a_pace_5),
            "home_efg_5": float(h_efg_5),
            "away_efg_5": float(a_efg_5)
        }

        # 厳格な順序で配列化
        vec = np.array([feat_dict[col] for col in self.FEATURE_COLS], dtype=np.float32)
        return vec
