#!/usr/bin/env python3
"""
src/models/baseline_models.py
ベースライン予測モデル群
- GlobalFrequencyModel: リーグ過去頻度固定確率
- EloProbabilityModel: 動的Eloレーティングに基づく1X2確率モデル
- MarketOddsModel: ブックメーカー（Pinnacle / Avg）オッズからマージンを除去した市場確率
"""

import numpy as np
import pandas as pd

class GlobalFrequencyModel:
    """学習期間全体の1X2出現頻度を固定確率として出力するモデル"""
    def __init__(self):
        self.name = "GlobalFrequency"
        self.probs = np.array([0.40, 0.25, 0.35]) # H, D, A 初期値

    def fit(self, train_df):
        counts = train_df['result_1x2'].value_counts()
        total = len(train_df)
        p_h = counts.get('H', 0) / total
        p_d = counts.get('D', 0) / total
        p_a = counts.get('A', 0) / total
        self.probs = np.array([p_h, p_d, p_a])
        print(f"[GlobalFreq] Fitted probabilities: H={p_h:.4f}, D={p_d:.4f}, A={p_a:.4f}")

    def predict_proba(self, df):
        n = len(df)
        return np.tile(self.probs, (n, 1))

class EloProbabilityModel:
    """Eloレーティング差に基づく1X2確率推定モデル"""
    def __init__(self, draw_base=0.26, draw_sigma=250.0):
        self.name = "EloProbability"
        self.draw_base = draw_base
        self.draw_sigma = draw_sigma

    def fit(self, train_df):
        # 引き分けベース確率を学習データから設定
        d_rate = (train_df['result_1x2'] == 'D').mean()
        self.draw_base = float(d_rate)
        print(f"[EloProb] Fitted base draw rate: {self.draw_base:.4f}")

    def predict_proba(self, df):
        # dfには 'elo_diff' (R_home + H_adv - R_away) が必要
        dr = df['elo_diff'].values
        # 基本引き分け確率（実力差が大きいほど引き分け率は減少）
        p_draw = self.draw_base * np.exp(- (dr / self.draw_sigma) ** 2)
        p_draw = np.clip(p_draw, 0.10, 0.35)

        # Eloの期待勝率 E_H
        e_h = 1.0 / (1.0 + 10.0 ** (-dr / 400.0))
        e_a = 1.0 - e_h

        # 引き分け以外の残余確率を配分
        rem = 1.0 - p_draw
        p_h = rem * e_h
        p_a = rem * e_a

        probs = np.vstack([p_h, p_draw, p_a]).T
        # 正規化
        probs = probs / np.sum(probs, axis=1, keepdims=True)
        return probs

class MarketOddsModel:
    """ブックメーカーオッズからマージンを除去した市場確率"""
    def __init__(self):
        self.name = "MarketOdds_Pinnacle"

    def predict_proba(self, df):
        # 'market_prob_H', 'market_prob_D', 'market_prob_A'
        p_h = df['market_prob_H'].values
        p_d = df['market_prob_D'].values
        p_a = df['market_prob_A'].values
        probs = np.vstack([p_h, p_d, p_a]).T
        # 欠損がある場合はGlobalFrequencyで補完
        nan_mask = np.isnan(probs).any(axis=1)
        if nan_mask.any():
            probs[nan_mask] = np.array([0.4027, 0.2494, 0.3479])
        return probs
