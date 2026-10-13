#!/usr/bin/env python3
"""
src/models/xgboost_model.py
XGBoost 1X2 分類モデル (Mac ARM64 安定化: float32/int32 C-contiguous & n_jobs=1)
"""

import numpy as np
import pandas as pd
import xgboost as xgb

BASE_FEATURE_COLS = [
    'elo_diff', 'home_elo', 'away_elo',
    'home_rest_days', 'away_rest_days', 'rest_diff',
    'home_gf_5', 'home_ga_5', 'home_pts_5',
    'away_gf_5', 'away_ga_5', 'away_pts_5',
    'home_gf_10', 'home_ga_10', 'away_gf_10', 'away_ga_10'
]

TIMESFM_FEATURE_COLS = BASE_FEATURE_COLS + [
    'tfm_home_exp_gf', 'tfm_home_exp_ga',
    'tfm_away_exp_gf', 'tfm_away_exp_ga',
    'tfm_exp_goal_diff'
]

LABEL_MAP = {'H': 0, 'D': 1, 'A': 2}
INV_LABEL_MAP = {0: 'H', 1: 'D', 2: 'A'}

class SoccerXGBoostModel:
    def __init__(self, use_timesfm=False, max_depth=3, n_estimators=100, learning_rate=0.03, random_state=42):
        self.use_timesfm = use_timesfm
        self.feature_cols = TIMESFM_FEATURE_COLS if use_timesfm else BASE_FEATURE_COLS
        self.name = "XGBoost_with_TimesFM" if use_timesfm else "XGBoost_Standard"
        self.model = xgb.XGBClassifier(
            max_depth=max_depth,
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            objective='multi:softprob',
            num_class=3,
            eval_metric='mlogloss',
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.5,
            reg_lambda=1.5,
            n_jobs=1,
            random_state=random_state
        )

    def fit(self, train_df, val_df=None):
        X_train = np.ascontiguousarray(train_df[self.feature_cols].values, dtype=np.float32)
        y_train = np.ascontiguousarray(train_df['result_1x2'].map(LABEL_MAP).values, dtype=np.int32)

        if val_df is not None:
            X_val = np.ascontiguousarray(val_df[self.feature_cols].values, dtype=np.float32)
            y_val = np.ascontiguousarray(val_df['result_1x2'].map(LABEL_MAP).values, dtype=np.int32)
            eval_set = [(X_val, y_val)]
            self.model.fit(X_train, y_train, eval_set=eval_set, verbose=False)
        else:
            self.model.fit(X_train, y_train)

        print(f"[{self.name}] Fitted successfully with {len(self.feature_cols)} features.")

    def predict_proba(self, df):
        X = np.ascontiguousarray(df[self.feature_cols].values, dtype=np.float32)
        probs = self.model.predict_proba(X)
        return np.ascontiguousarray(probs, dtype=np.float64)

    def get_feature_importances(self):
        return pd.Series(self.model.feature_importances_, index=self.feature_cols).sort_values(ascending=False)
