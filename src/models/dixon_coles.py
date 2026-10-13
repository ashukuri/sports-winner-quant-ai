#!/usr/bin/env python3
"""
src/models/dixon_coles.py
Dixon-Coles / ポアソン得点期待値モデル
各チームの攻撃力・守備力、ホームアドバンテージ、低得点相関パラメータrhoを最尤推定し、
二変量ポアソン分布から 1X2確率 および WINNER 18選択肢の確率分布を算出する。
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

WINNER_CATEGORIES = [
    "1-0", "2-0", "2-1", "3-0", "3-1", "3-2", "other_home_win",
    "0-0", "1-1", "2-2", "other_draw",
    "0-1", "0-2", "1-2", "0-3", "1-3", "2-3", "other_away_win"
]

def tau(x, y, lambda_param, mu_param, rho):
    """Dixon-Coles低得点補正係数"""
    if x == 0 and y == 0:
        return 1.0 - lambda_param * mu_param * rho
    elif x == 0 and y == 1:
        return 1.0 + lambda_param * rho
    elif x == 1 and y == 0:
        return 1.0 + mu_param * rho
    elif x == 1 and y == 1:
        return 1.0 - rho
    else:
        return 1.0

class DixonColesModel:
    def __init__(self, max_goals=10):
        self.name = "DixonColes_Poisson"
        self.max_goals = max_goals
        self.teams = []
        self.params = {}
        self.home_adv = 0.25
        self.rho = -0.05

    def fit(self, train_df):
        teams = sorted(list(set(train_df['home_team']).union(set(train_df['away_team']))))
        self.teams = teams
        n_teams = len(teams)
        team_idx = {t: i for i, t in enumerate(teams)}

        # パラメータ配列の構成:
        # [attack_0, ..., attack_{n-1}, defense_0, ..., defense_{n-1}, home_adv, rho]
        # 制約: sum(attack) = 0 または固定 (平均を0に制約)
        init_att = np.zeros(n_teams)
        init_def = np.zeros(n_teams)
        init_home_adv = 0.25
        init_rho = -0.05
        init_params = np.concatenate([init_att, init_def, [init_home_adv, init_rho]])

        h_teams = train_df['home_team'].map(team_idx).values
        a_teams = train_df['away_team'].map(team_idx).values
        h_goals = train_df['home_score'].values
        a_goals = train_df['away_score'].values

        def neg_log_likelihood(params):
            att = params[:n_teams]
            defe = params[n_teams:2*n_teams]
            h_adv = params[-2]
            rho_val = params[-1]

            # 攻撃力平均ゼロ制約ペナルティ
            penalty = 100.0 * (np.mean(att) ** 2)

            log_lambda = att[h_teams] - defe[a_teams] + h_adv
            log_mu = att[a_teams] - defe[h_teams]

            # クリップ
            log_lambda = np.clip(log_lambda, -3.0, 3.0)
            log_mu = np.clip(log_mu, -3.0, 3.0)
            lambdas = np.exp(log_lambda)
            mus = np.exp(log_mu)

            # ポアソン確率
            log_p_x = poisson.logpmf(h_goals, lambdas)
            log_p_y = poisson.logpmf(a_goals, mus)

            # tau補正
            tau_vals = np.array([tau(x, y, l, m, rho_val) for x, y, l, m in zip(h_goals, a_goals, lambdas, mus)])
            tau_vals = np.clip(tau_vals, 1e-6, None)
            log_tau = np.log(tau_vals)

            ll = np.sum(log_p_x + log_p_y + log_tau)
            return -ll + penalty

        print("[DixonColes] Fitting Dixon-Coles Poisson parameters...")
        res = minimize(neg_log_likelihood, init_params, method='L-BFGS-B', options={'maxiter': 100})
        
        self.params = {
            'attack': {t: res.x[i] for i, t in enumerate(teams)},
            'defense': {t: res.x[n_teams + i] for i, t in enumerate(teams)},
            'home_adv': res.x[-2],
            'rho': res.x[-1]
        }
        self.home_adv = float(res.x[-2])
        self.rho = float(res.x[-1])
        print(f"[DixonColes] Fitted Home Adv: {self.home_adv:.4f}, Rho: {self.rho:.4f}")

    def predict_score_matrix(self, home_team, away_team):
        """1試合の得点同時分布行列 (max_goals+1, max_goals+1) を計算"""
        att_h = self.params['attack'].get(home_team, 0.0)
        def_a = self.params['defense'].get(away_team, 0.0)
        att_a = self.params['attack'].get(away_team, 0.0)
        def_h = self.params['defense'].get(home_team, 0.0)

        lambda_val = np.exp(np.clip(att_h - def_a + self.home_adv, -2.5, 2.5))
        mu_val = np.exp(np.clip(att_a - def_h, -2.5, 2.5))

        goals_range = np.arange(self.max_goals + 1)
        p_x = poisson.pmf(goals_range, lambda_val)
        p_y = poisson.pmf(goals_range, mu_val)

        # テンソル積
        matrix = np.outer(p_x, p_y)

        # 低得点相関tau補正
        for x in range(2):
            for y in range(2):
                matrix[x, y] *= tau(x, y, lambda_val, mu_val, self.rho)
                matrix[x, y] = max(matrix[x, y], 1e-8)

        # 正規化
        matrix = matrix / np.sum(matrix)
        return matrix, lambda_val, mu_val

    def predict_proba(self, df):
        """1X2の勝敗確率 (N, 3) を予測"""
        probs = []
        for _, row in df.iterrows():
            matrix, _, _ = self.predict_score_matrix(row['home_team'], row['away_team'])
            p_h = np.sum(np.tril(matrix, -1))
            p_d = np.sum(np.diag(matrix))
            p_a = np.sum(np.triu(matrix, 1))
            probs.append([p_h, p_d, p_a])
        return np.array(probs)

    def predict_winner_18_proba(self, home_team, away_team):
        """WINNER 18択の厳密な確率分布 (和=1.0) を算出"""
        matrix, l_val, m_val = self.predict_score_matrix(home_team, away_team)
        winner_dict = {cat: 0.0 for cat in WINNER_CATEGORIES}

        for x in range(self.max_goals + 1):
            for y in range(self.max_goals + 1):
                p = matrix[x, y]
                score_str = f"{x}-{y}"
                if x > y:
                    if score_str in winner_dict:
                        winner_dict[score_str] += p
                    else:
                        winner_dict["other_home_win"] += p
                elif x == y:
                    if score_str in winner_dict:
                        winner_dict[score_str] += p
                    else:
                        winner_dict["other_draw"] += p
                else:
                    if score_str in winner_dict:
                        winner_dict[score_str] += p
                    else:
                        winner_dict["other_away_win"] += p

        # 配列化と正規化
        p_vec = np.array([winner_dict[c] for c in WINNER_CATEGORIES])
        p_vec = p_vec / np.sum(p_vec)
        return p_vec, {c: float(p_vec[i]) for i, c in enumerate(WINNER_CATEGORIES)}, l_val, m_val
