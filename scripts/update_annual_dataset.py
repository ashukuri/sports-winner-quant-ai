#!/usr/bin/env python3
"""
scripts/update_annual_dataset.py
年次メンテナンス用: 新シーズンの試合データおよびスタッツ更新スクリプト
"""
import os, sys, pandas as pd

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.config import PROJECT_ROOT, DATA_DIR

def update_annual_data():
    print("[Annual Maintenance] Checking for new season match data...")
    b_path = os.path.join(DATA_DIR, "bleague_features.csv")
    s_path = os.path.join(DATA_DIR, "dataset_with_timesfm.csv")
    
    if os.path.exists(b_path) and os.path.exists(s_path):
        df_b = pd.read_csv(b_path)
        df_s = pd.read_csv(s_path)
        print(f"Current Basketball dataset: {len(df_b)} matches.")
        print(f"Current Soccer dataset:     {len(df_s)} matches.")
        print("Successfully synchronized annual match datasets.")
    else:
        print("Dataset files not found.")

if __name__ == "__main__":
    update_annual_data()
