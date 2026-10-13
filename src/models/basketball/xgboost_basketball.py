#!/usr/bin/env python3
"""
src/models/basketball/xgboost_basketball.py
Bリーグ（B1）用 XGBoost 予測モデル
- 分類モデル (16クラス Multi-class Softmax)
- 回帰モデル (点差回帰 -> Student-t 誤差分布変換)
- TimesFM特徴量あり / なしの切り替え
"""

import os
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import t as student_t
from src.models.basketball.point_spread_models import continuous_diff_to_16_probs

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

BASE_FEATURES = [
    "elo_diff", "home_elo", "away_elo",
    "home_rest_days", "away_rest_days", "home_b2b", "away_b2b", "rest_diff",
    "diff_pts_for_5", "diff_pts_against_5", "diff_diff_5",
    "diff_ortg_5", "diff_drtg_5", "diff_efg_5", "diff_pace_5", "diff_win_rate_5",
    "diff_diff_10", "diff_ortg_10", "diff_drtg_10",
    "home_ortg_5", "away_ortg_5", "home_drtg_5", "away_drtg_5", "home_pace_5", "away_pace_5",
    "home_efg_5", "away_efg_5"
]

TIMESFM_FEATURES = [
    "tfm_home_pts_pred", "tfm_away_pts_pred", "tfm_home_opp_pred", "tfm_away_opp_pred", "tfm_pred_diff"
]

class BasketballXGBoostModel:
    def __init__(self, mode='classifier', use_timesfm=False, n_estimators=100, max_depth=3, learning_rate=0.03):
        self.mode = mode # 'classifier' or 'regressor'
        self.use_timesfm = use_timesfm
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.name = f"XGBoost_{mode}_{'with_TimesFM' if use_timesfm else 'Standard'}"
        self.model = None
        self.feature_cols = BASE_FEATURES + (TIMESFM_FEATURES if use_timesfm else [])
        self.sigma = 12.0 # 回帰時の誤差分散
        self.df_param = 5.0 # 回帰時の自由度

    def fit(self, train_df, val_df=None):
        X_train = train_df[self.feature_cols].values

        if self.mode == 'classifier':
            y_train = train_df['target_cat_idx'].values
            self.model = xgb.XGBClassifier(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                objective='multi:softprob',
                num_class=16,
                random_state=42,
                n_jobs=1
            )
            if val_df is not None:
                X_val = val_df[self.feature_cols].values
                y_val = val_df['target_cat_idx'].values
                self.model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
            else:
                self.model.fit(X_train, y_train, verbose=False)

        else: # 回帰モデル
            y_train = train_df['point_diff'].values
            self.model = xgb.XGBRegressor(
                n_estimators=self.n_estimators,
                max_depth=self.max_depth,
                learning_rate=self.learning_rate,
                random_state=42,
                n_jobs=1
            )
            if val_df is not None:
                X_val = val_df[self.feature_cols].values
                y_val = val_df['point_diff'].values
                self.model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
                # 残差から sigma を推定
                preds_val = self.model.predict(X_val)
                residuals = y_val - preds_val
                self.sigma = float(np.std(residuals))
            else:
                self.model.fit(X_train, y_train, verbose=False)
                preds_tr = self.model.predict(X_train)
                self.sigma = float(np.std(y_train - preds_tr))

    def predict_proba(self, df):
        X = df[self.feature_cols].values

        if self.mode == 'classifier':
            probs = self.model.predict_proba(X)
            # クリッピングと再正規化
            probs = np.clip(probs, 1e-12, 1.0)
            probs = probs / np.sum(probs, axis=1, keepdims=True)
            return probs
        else: # 回帰から Student-t 変換
            mu_preds = self.model.predict(X)
            n = len(df)
            probs_mat = np.zeros((n, 16))
            for i in range(n):
                mu = mu_preds[i]
                dist_fn = lambda x: student_t.cdf(x, df=self.df_param, loc=mu, scale=self.sigma)
                probs_mat[i] = continuous_diff_to_16_probs(dist_fn)
            return probs_mat
