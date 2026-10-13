#!/usr/bin/env python3
"""
src/models/timesfm_feature_extractor.py
Google TimesFM 3.0 公式モデルを用いたチーム別得点・失点期待値特徴量抽出モジュール
各試合前のチームの過去試合得点系列・失点系列から、ファンデーションモデルによる次回得失点予測値を生成する。
"""

import os
import numpy as np
import pandas as pd
import timesfm

class TimesFMSoccerFeatureExtractor:
    def __init__(self, model_name="google/timesfm-3.0-pytorch", min_history_len=8, context_window=32):
        self.model_name = model_name
        self.min_history_len = min_history_len
        self.context_window = context_window
        print(f"[TimesFM Soccer] Loading {model_name}...")
        self.forecaster = timesfm.TimesFM3Forecaster.from_pretrained(model_name)
        print("[TimesFM Soccer] Model loaded successfully.")

    def extract_features_for_dataset(self, df):
        """
        データセット全体に対して、各試合時点の過去履歴のみを用いて
        TimesFMによる次回得点・失点予測特徴量を生成 (Walk-Forward)
        """
        print(f"[TimesFM Soccer] Extracting foundation model features for {len(df)} matches...")
        
        # チーム別時系列履歴の構築
        team_gf_history = {}
        team_ga_history = {}

        # 予測値を保持するリスト
        tfm_home_exp_gf = []
        tfm_home_exp_ga = []
        tfm_away_exp_gf = []
        tfm_away_exp_ga = []

        # 高速化のため、一定試合数ごとにバッチ処理、または順次抽出
        # まず各行ごとのコンテキスト系列を収集
        contexts_to_predict = [] # list of (row_idx, role, 'gf'/'ga', series)

        for idx, row in df.iterrows():
            h_team = row['home_team']
            a_team = row['away_team']

            # ホームチームの過去履歴
            h_gf = team_gf_history.get(h_team, [])
            h_ga = team_ga_history.get(h_team, [])
            # アウェイチームの過去履歴
            a_gf = team_gf_history.get(a_team, [])
            a_ga = team_ga_history.get(a_team, [])

            # 予測コンテキストの登録（十分な履歴があればTimesFM、なければ直近平均フォールバック）
            if len(h_gf) >= self.min_history_len:
                sub_h_gf = np.array(h_gf[-self.context_window:], dtype=np.float32)
                sub_h_ga = np.array(h_ga[-self.context_window:], dtype=np.float32)
                contexts_to_predict.append((idx, 'H_gf', sub_h_gf))
                contexts_to_predict.append((idx, 'H_ga', sub_h_ga))
            
            if len(a_gf) >= self.min_history_len:
                sub_a_gf = np.array(a_gf[-self.context_window:], dtype=np.float32)
                sub_a_ga = np.array(a_ga[-self.context_window:], dtype=np.float32)
                contexts_to_predict.append((idx, 'A_gf', sub_a_gf))
                contexts_to_predict.append((idx, 'A_ga', sub_a_ga))

            # 試合終了後の履歴追加
            if h_team not in team_gf_history: team_gf_history[h_team] = []
            if h_team not in team_ga_history: team_ga_history[h_team] = []
            if a_team not in team_gf_history: team_gf_history[a_team] = []
            if a_team not in team_ga_history: team_ga_history[a_team] = []

            team_gf_history[h_team].append(float(row['home_score']))
            team_ga_history[h_team].append(float(row['away_score']))
            team_gf_history[a_team].append(float(row['away_score']))
            team_ga_history[a_team].append(float(row['home_score']))

        # バッチ推論の実行
        print(f"[TimesFM Soccer] Running batch inference for {len(contexts_to_predict)} time-series contexts...")
        predictions_map = {} # (idx, role) -> val

        batch_size = 500
        for i in range(0, len(contexts_to_predict), batch_size):
            chunk = contexts_to_predict[i : i + batch_size]
            ts_list = [item[2] for item in chunk]
            outputs = list(self.forecaster.predict_batch(ts_list, horizon=1))
            for k, out in enumerate(outputs):
                idx, role, _ = chunk[k]
                pred_val = float(out.forecast[0])
                predictions_map[(idx, role)] = pred_val

        # 結果をデータフレーム形式に結合
        n_rows = len(df)
        h_exp_gf = np.full(n_rows, 1.35)
        h_exp_ga = np.full(n_rows, 1.25)
        a_exp_gf = np.full(n_rows, 1.25)
        a_exp_ga = np.full(n_rows, 1.35)

        for idx in range(n_rows):
            if (idx, 'H_gf') in predictions_map: h_exp_gf[idx] = predictions_map[(idx, 'H_gf')]
            if (idx, 'H_ga') in predictions_map: h_exp_ga[idx] = predictions_map[(idx, 'H_ga')]
            if (idx, 'A_gf') in predictions_map: a_exp_gf[idx] = predictions_map[(idx, 'A_gf')]
            if (idx, 'A_ga') in predictions_map: a_exp_ga[idx] = predictions_map[(idx, 'A_ga')]

        res_df = df.copy()
        res_df['tfm_home_exp_gf'] = np.clip(h_exp_gf, 0.2, 4.0)
        res_df['tfm_home_exp_ga'] = np.clip(h_exp_ga, 0.2, 4.0)
        res_df['tfm_away_exp_gf'] = np.clip(a_exp_gf, 0.2, 4.0)
        res_df['tfm_away_exp_ga'] = np.clip(a_exp_ga, 0.2, 4.0)
        res_df['tfm_exp_goal_diff'] = res_df['tfm_home_exp_gf'] - res_df['tfm_away_exp_gf']

        print("[TimesFM Soccer] Feature extraction complete.")
        return res_df
