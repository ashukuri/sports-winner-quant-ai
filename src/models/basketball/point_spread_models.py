#!/usr/bin/env python3
"""
src/models/basketball/point_spread_models.py
Bリーグ（B1）用 ベースラインおよび確率的点差モデル
- Model B0-1: GlobalFrequencyBaseline
- Model B0-2: EloPointSpreadModel
- Model B1-Normal: 正規分布点差モデル
- Model B1-StudentT: Student-t分布点差モデル (裾の厚さを考慮)
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm, t as student_t

BLEAGUE_WINNER_CATEGORIES = [
    "H_1-3", "H_4-6", "H_7-9", "H_10-14", "H_15-19", "H_20-24", "H_25-29", "H_30+",
    "A_1-3", "A_4-6", "A_7-9", "A_10-14", "A_15-19", "A_20-24", "A_25-29", "A_30+"
]

def continuous_diff_to_16_probs(dist_cdf_fn):
    """
    点差の累積分布関数 CDF(x) から、公式16選択肢の離散確率ベクトルを算出。
    バスケは同点（diff=0）が存在しないため、各整数点差 d in Z \ {0} の確率:
    P(D = d) = CDF(d + 0.5) - CDF(d - 0.5)
    を計算し、d=0 を除外して合計1.0に再正規化する。
    """
    # 各帯の積分範囲 (連続近似):
    # Home:
    # 1-3:   [0.5, 3.5]
    # 4-6:   [3.5, 6.5]
    # 7-9:   [6.5, 9.5]
    # 10-14: [9.5, 14.5]
    # 15-19: [14.5, 19.5]
    # 20-24: [19.5, 24.5]
    # 25-29: [24.5, 29.5]
    # 30+:   [29.5, inf)
    
    # Away (Away勝利 = diff < 0):
    # 1-3:   [-3.5, -0.5]
    # 4-6:   [-6.5, -3.5]
    # 7-9:   [-9.5, -6.5]
    # 10-14: [-14.5, -9.5]
    # 15-19: [-19.5, -14.5]
    # 20-24: [-24.5, -19.5]
    # 25-29: [-29.5, -24.5]
    # 30+:   (-inf, -29.5]

    bands_home = [
        (0.5, 3.5), (3.5, 6.5), (6.5, 9.5), (9.5, 14.5),
        (14.5, 19.5), (19.5, 24.5), (24.5, 29.5), (29.5, 1000.0)
    ]
    bands_away = [
        (-3.5, -0.5), (-6.5, -3.5), (-9.5, -6.5), (-14.5, -9.5),
        (-19.5, -14.5), (-24.5, -19.5), (-29.5, -24.5), (-1000.0, -29.5)
    ]

    p_vec = np.zeros(16)
    for i, (low, high) in enumerate(bands_home):
        p_vec[i] = max(dist_cdf_fn(high) - dist_cdf_fn(low), 1e-12)
    for i, (low, high) in enumerate(bands_away):
        # Away勝利は diff が負なので、CDF(high) - CDF(low)
        p_vec[8 + i] = max(dist_cdf_fn(high) - dist_cdf_fn(low), 1e-12)

    # 再正規化 (合計を正確に1.0にする)
    s = np.sum(p_vec)
    if s > 0:
        p_vec /= s
    else:
        p_vec = np.ones(16) / 16.0
    return p_vec

class GlobalFrequencyBaseline:
    def __init__(self):
        self.name = "Model_B0_GlobalFrequency"
        self.probs = np.ones(16) / 16.0

    def fit(self, train_df):
        counts = train_df['winner_category'].value_counts()
        p = np.array([max(counts.get(c, 1), 1) for c in BLEAGUE_WINNER_CATEGORIES], dtype=float)
        self.probs = p / np.sum(p)

    def predict_proba(self, df):
        return np.tile(self.probs, (len(df), 1))

class EloPointSpreadModel:
    def __init__(self, elo_scale=25.0, base_sigma=12.5):
        self.name = "Model_B0_EloPointSpread"
        self.elo_scale = elo_scale
        self.base_sigma = base_sigma

    def fit(self, train_df):
        pass

    def predict_proba(self, df):
        n = len(df)
        probs_mat = np.zeros((n, 16))
        for i, (_, row) in enumerate(df.iterrows()):
            # 期待点差 mu = elo_diff / scale
            mu = row['elo_diff'] / self.elo_scale
            dist_fn = lambda x: norm.cdf(x, loc=mu, scale=self.base_sigma)
            probs_mat[i] = continuous_diff_to_16_probs(dist_fn)
        return probs_mat

class ProbabilisticPointSpreadModel:
    """
    Model B1: 各チームの攻撃力 alpha_i, 守備力 beta_i, ホームアドバンテージ gamma を最尤推定。
    予測点差 mu = gamma + alpha_home - beta_away
    誤差分布: 'normal' または 'student_t'
    """
    def __init__(self, dist_type='student_t'):
        self.dist_type = dist_type
        self.name = f"Model_B1_{dist_type.capitalize()}"
        self.teams = []
        self.team_idx = {}
        self.home_adv = 2.8 # バスケの平均ホームアドバンテージ (約2.8点)
        self.sigma = 12.5
        self.df_param = 5.0 # Student-t 自由度
        self.att = {}
        self.deff = {}

    def fit(self, train_df):
        teams = sorted(list(set(train_df['home_team']).union(set(train_df['away_team']))))
        self.teams = teams
        n_teams = len(teams)
        self.team_idx = {t: i for i, t in enumerate(teams)}

        h_idx = train_df['home_team'].map(self.team_idx).values
        a_idx = train_df['away_team'].map(self.team_idx).values
        y_diff = train_df['point_diff'].values

        # 最適化パラメータ:
        # [att_0, ..., att_{n-1}, def_0, ..., def_{n-1}, home_adv, log_sigma, (log_df)]
        init_att = np.zeros(n_teams)
        init_def = np.zeros(n_teams)
        init_home = 2.8
        init_log_sigma = np.log(12.5)

        if self.dist_type == 'normal':
            init_params = np.concatenate([init_att, init_def, [init_home, init_log_sigma]])
        else:
            init_log_df = np.log(6.0)
            init_params = np.concatenate([init_att, init_def, [init_home, init_log_sigma, init_log_df]])

        def neg_log_likelihood(params):
            att = params[:n_teams]
            deff = params[n_teams:2*n_teams]
            home_adv = params[2*n_teams]
            sigma = np.exp(params[2*n_teams + 1])

            # 制約: 平均を0に正規化
            att_c = att - np.mean(att)
            deff_c = deff - np.mean(deff)

            mu = home_adv + att_c[h_idx] - deff_c[a_idx]

            if self.dist_type == 'normal':
                ll = norm.logpdf(y_diff, loc=mu, scale=sigma)
            else:
                nu = np.exp(params[2*n_teams + 2])
                ll = student_t.logpdf(y_diff, df=nu, loc=mu, scale=sigma)

            # 正則化 (L2)
            reg = 0.01 * (np.sum(att_c**2) + np.sum(deff_c**2))
            return -np.sum(ll) + reg

        res = minimize(neg_log_likelihood, init_params, method='L-BFGS-B', options={'maxiter': 150})
        p_opt = res.x

        att_opt = p_opt[:n_teams] - np.mean(p_opt[:n_teams])
        def_opt = p_opt[n_teams:2*n_teams] - np.mean(p_opt[n_teams:2*n_teams])
        self.home_adv = float(p_opt[2*n_teams])
        self.sigma = float(np.exp(p_opt[2*n_teams + 1]))

        if self.dist_type != 'normal':
            self.df_param = float(np.exp(p_opt[2*n_teams + 2]))

        for i, t in enumerate(teams):
            self.att[t] = float(att_opt[i])
            self.deff[t] = float(def_opt[i])

        print(f"[{self.name}] Fitted: HomeAdv={self.home_adv:.2f}, Sigma={self.sigma:.2f}" + 
              (f", Nu(df)={self.df_param:.2f}" if self.dist_type != 'normal' else ""))

    def predict_mu(self, home_team, away_team):
        h_a = self.att.get(home_team, 0.0)
        a_d = self.deff.get(away_team, 0.0)
        return self.home_adv + h_a - a_d

    def predict_proba(self, df):
        n = len(df)
        probs_mat = np.zeros((n, 16))
        for i, (_, row) in enumerate(df.iterrows()):
            mu = self.predict_mu(row['home_team'], row['away_team'])
            if self.dist_type == 'normal':
                dist_fn = lambda x: norm.cdf(x, loc=mu, scale=self.sigma)
            else:
                dist_fn = lambda x: student_t.cdf(x, df=self.df_param, loc=mu, scale=self.sigma)
            probs_mat[i] = continuous_diff_to_16_probs(dist_fn)
        return probs_mat
