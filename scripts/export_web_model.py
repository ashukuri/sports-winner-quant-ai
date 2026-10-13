#!/usr/bin/env python3
"""
scripts/export_web_model.py
Python学習済みモデルをGitHub Pages用JavaScriptデータにエクスポートするスクリプト
"""

import os
import sys
import json
import pandas as pd

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.config import PROJECT_ROOT, DATA_DIR, MODELS_DIR

def export_web_model():
    print("Exporting models to docs/model_data.js ...")
    
    # 1. Bリーグ
    df_b = pd.read_csv(os.path.join(DATA_DIR, "bleague_features.csv"))
    b_elo = {}
    b_stats = {}
    for _, r in df_b.iterrows():
        b_elo[r['home_team']] = float(r['home_elo'])
        b_elo[r['away_team']] = float(r['away_elo'])
        b_stats[r['home_team']] = {
            'ortg': float(r['home_ortg_5']),
            'drtg': float(r['home_drtg_5']),
            'pace': float(r['home_pace_5']),
            'efg': float(r['home_efg_5'])
        }
        b_stats[r['away_team']] = {
            'ortg': float(r['away_ortg_5']),
            'drtg': float(r['away_drtg_5']),
            'pace': float(r['away_pace_5']),
            'efg': float(r['away_efg_5'])
        }

    # 2. サッカー
    df_s = pd.read_csv(os.path.join(DATA_DIR, "dataset_with_timesfm.csv"))
    s_elo = {}
    for _, r in df_s.iterrows():
        s_elo[r['home_team']] = float(r['home_elo'])
        s_elo[r['away_team']] = float(r['away_elo'])

    with open(os.path.join(MODELS_DIR, "dixon_coles_params.json")) as f:
        s_params = json.load(f)

    with open(os.path.join(MODELS_DIR, "b4_xgboost_meta.json")) as f:
        b_meta = json.load(f)

    web_model_data = {
        'version': '1.0.0',
        'trained_date': '2026-10-13',
        'next_maintenance_date': '2027-09-01',
        'basketball': {
            'meta': b_meta,
            'teams_elo': b_elo,
            'teams_stats': b_stats,
            'league_avg_pace': 72.0,
            'league_avg_ortg': 105.0
        },
        'soccer': {
            'home_adv': s_params['home_adv'],
            'rho': s_params['rho'],
            'teams_elo': s_elo
        }
    }

    out_json = json.dumps(web_model_data, ensure_ascii=False, indent=2)
    
    # docs/ および ルートへ出力
    for d in ["docs", "."]:
        js_path = os.path.join(PROJECT_ROOT, d, "model_data.js")
        with open(js_path, "w", encoding="utf-8") as f:
            f.write("window.WINNER_MODEL_DATA = " + out_json + ";\n")
        json_path = os.path.join(PROJECT_ROOT, d, "model_data.json")
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(out_json)

    print("Successfully exported web model files to docs/ and root!")

if __name__ == "__main__":
    export_web_model()
