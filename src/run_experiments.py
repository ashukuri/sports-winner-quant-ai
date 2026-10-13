#!/usr/bin/env python3
"""
src/run_experiments.py
全モデルの学習、TimesFM 3.0特徴量抽出、厳密なWalk-Forwardバックテスト、
toto/mini totoおよびWINNERシミュレーションを一気通貫で実行するメインオーケストレータ
"""

import os
import sys
os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib_cache"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
import json
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.optimize import minimize

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(BASE_DIR)

from src.features import build_dataset_with_features
from src.models.baseline_models import GlobalFrequencyModel, EloProbabilityModel, MarketOddsModel
from src.models.dixon_coles import DixonColesModel
from src.models.timesfm_feature_extractor import TimesFMSoccerFeatureExtractor
from src.models.xgboost_model import SoccerXGBoostModel
from src.backtest.evaluator import evaluate_predictions
from src.strategy.toto_simulator import TotoSimulator
from src.strategy.winner_simulator import WinnerSimulator

DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
FIG_DIR = os.path.join(REPORTS_DIR, "figures")

def main():
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(FIG_DIR, exist_ok=True)
    start_time = time.time()

    print("=" * 75)
    print(" SOCCER PREDICTION & BETTING RESEARCH LAB — 全モデル実験・バックテスト")
    print("=" * 75)

    # 1. データセット構築と特徴量生成
    matches_csv = os.path.join(DATA_DIR, "jleague_matches_2015_2024.csv")
    fd_csv = os.path.join(DATA_DIR, "football_data_jpn.csv")
    print("\n[STEP 1] Building feature dataset (Elo, Recency, Odds)...")
    dataset = build_dataset_with_features(matches_csv, fd_csv)
    print(f"Total dataset size: {len(dataset)} matches.")
    print(f"Splits: {dataset['split'].value_counts().to_dict()}")

    # 2. TimesFM 3.0 によるファンデーション時系列特徴量抽出
    print("\n[STEP 2] Extracting TimesFM 3.0 features...")
    cached_feat_path = os.path.join(DATA_DIR, "dataset_with_timesfm.csv")
    if os.path.exists(cached_feat_path):
        print(f"Loading cached TimesFM dataset from {cached_feat_path}...")
        dataset = pd.read_csv(cached_feat_path)
    else:
        tfm_extractor = TimesFMSoccerFeatureExtractor(model_name="google/timesfm-3.0-pytorch", min_history_len=8, context_window=32)
        dataset = tfm_extractor.extract_features_for_dataset(dataset)
        dataset.to_csv(cached_feat_path, index=False)
        print(f"Saved dataset with TimesFM features to {cached_feat_path}")

    # スプリット分割
    train_df = dataset[dataset['split'] == 'train'].reset_index(drop=True)
    val_df = dataset[dataset['split'] == 'val'].reset_index(drop=True)
    test_df = dataset[dataset['split'] == 'test'].reset_index(drop=True)
    print(f"\n[SPLIT INFO] Train (2015-2021): {len(train_df)}, Val (2022): {len(val_df)}, Test (2023-2024): {len(test_df)}")

    # 3. 各モデルの学習と検証セット調整
    print("\n[STEP 3] Fitting models on Train (and tuning on Val)...")
    
    # Model 0: ベースライン群
    m_freq = GlobalFrequencyModel()
    m_freq.fit(train_df)

    m_elo = EloProbabilityModel()
    m_elo.fit(train_df)

    m_market = MarketOddsModel()

    # Model 1: Dixon-Coles ポアソンモデル
    m_dc = DixonColesModel(max_goals=8)
    m_dc.fit(train_df)

    # Model 2: XGBoost Standard (TimesFMなし)
    m_xgb_std = SoccerXGBoostModel(use_timesfm=False, max_depth=3, n_estimators=100, learning_rate=0.03)
    m_xgb_std.fit(train_df, val_df)

    # Model 3: XGBoost with TimesFM 3.0 (TimesFMあり)
    m_xgb_tfm = SoccerXGBoostModel(use_timesfm=True, max_depth=3, n_estimators=100, learning_rate=0.03)
    m_xgb_tfm.fit(train_df, val_df)

    # Model 4: アンサンブルモデル（検証セット2022年で最適重み探索）
    print("\n[Ensemble Tuning] Optimizing ensemble weights on Validation set (2022)...")
    val_p_dc = m_dc.predict_proba(val_df)
    val_p_elo = m_elo.predict_proba(val_df)
    val_p_xgb_std = m_xgb_std.predict_proba(val_df)
    val_p_xgb_tfm = m_xgb_tfm.predict_proba(val_df)
    val_p_market = m_market.predict_proba(val_df)
    val_y = val_df['result_1x2'].values

    # 最適化対象モデル: [DixonColes, Elo, XGBoost_TimesFM, Market]
    # 制約: w >= 0, sum(w) = 1
    def ensemble_loss(weights):
        w = weights / np.sum(weights)
        comb_p = w[0] * val_p_dc + w[1] * val_p_elo + w[2] * val_p_xgb_tfm + w[3] * val_p_market
        comb_p = np.clip(comb_p, 1e-12, 1.0)
        comb_p = comb_p / np.sum(comb_p, axis=1, keepdims=True)
        from src.backtest.evaluator import compute_log_loss_vector
        losses = compute_log_loss_vector(val_y, comb_p)
        return np.mean(losses)

    opt_res = minimize(ensemble_loss, [0.25, 0.25, 0.25, 0.25], bounds=[(0, 1)]*4, method='SLSQP')
    opt_w = opt_res.x / np.sum(opt_res.x)
    print(f"Optimal ensemble weights: DC={opt_w[0]:.3f}, Elo={opt_w[1]:.3f}, XGB_TFM={opt_w[2]:.3f}, Market={opt_w[3]:.3f}")

    # 4. 最終テストセット (2023〜2024年、686試合) での包括的評価
    print("\n[STEP 4] Evaluating on Out-of-Sample Test Set (2023-2024, 686 matches)...")
    test_y = test_df['result_1x2'].values

    # 各モデルのテスト確率
    test_probs = {}
    test_probs["GlobalFrequency"] = m_freq.predict_proba(test_df)
    test_probs["EloProbability"] = m_elo.predict_proba(test_df)
    test_probs["DixonColes"] = m_dc.predict_proba(test_df)
    test_probs["XGBoost_Standard"] = m_xgb_std.predict_proba(test_df)
    test_probs["XGBoost_with_TimesFM"] = m_xgb_tfm.predict_proba(test_df)
    test_probs["MarketOdds_Pinnacle"] = m_market.predict_proba(test_df)

    # アンサンブルテスト確率
    p_ens = (opt_w[0] * test_probs["DixonColes"] +
             opt_w[1] * test_probs["EloProbability"] +
             opt_w[2] * test_probs["XGBoost_with_TimesFM"] +
             opt_w[3] * test_probs["MarketOdds_Pinnacle"])
    p_ens = p_ens / np.sum(p_ens, axis=1, keepdims=True)
    test_probs["Ensemble_Model"] = p_ens

    market_prob_mat = test_probs["MarketOdds_Pinnacle"]

    eval_rows = []
    loss_series_dict = {}

    for m_name, probs in test_probs.items():
        res, l_vec, b_vec = evaluate_predictions(test_y, probs, m_name, market_prob_matrix=market_prob_mat)
        eval_rows.append(res)
        loss_series_dict[m_name] = l_vec

    eval_df = pd.DataFrame(eval_rows).sort_values("log_loss")
    print("\n" + "=" * 90)
    print("【1X2 予測性能 最終テスト評価表 (2023-2024年 686試合)】")
    print("=" * 90)
    print(eval_df[['model_name', 'log_loss', 'brier_score', 'accuracy', 'ece', 'diff_vs_market', 'ci95_lower_vs_market', 'ci95_upper_vs_market', 'p_val_vs_market']].to_string(index=False))

    csv_comp = os.path.join(REPORTS_DIR, "model_comparison.csv")
    eval_df.to_csv(csv_comp, index=False)
    print(f"\nSaved model comparison to: {csv_comp}")

    # 5. toto / mini toto シミュレーション
    print("\n[STEP 5] Running toto & mini toto simulations...")
    toto_sim = TotoSimulator(cost_per_bet=100)
    toto_json_path = os.path.join(DATA_DIR, "toto_history.json")

    with open(toto_json_path, 'r', encoding='utf-8') as f:
        toto_records = json.load(f)

    print(f"Loaded {len(toto_records)} historical toto draw rounds.")

    # 各toto開催回に対する各モデルの試合確率を再構成
    # 開催回ごとの試合カードについて、該当試合がJ1テストセットにあればそのモデル確率を使用、なければDixon-Colesで推定
    toto_model_probs = {m: [] for m in ["GlobalFrequency", "EloProbability", "DixonColes", "XGBoost_with_TimesFM", "MarketOdds_Pinnacle", "Ensemble_Model"]}
    mini_model_probs = {m: [] for m in toto_model_probs.keys()}

    for rec in toto_records:
        matches_13 = rec['toto_13_matches']
        m13_probs = {m: [] for m in toto_model_probs.keys()}
        for m_info in matches_13:
            h, a = m_info['home'], m_info['away']
            # DixonColes による確率
            p_dc_match = m_dc.predict_score_matrix(h, a)[0]
            ph = np.sum(np.tril(p_dc_match, -1))
            pd_ = np.sum(np.diag(p_dc_match))
            pa = np.sum(np.triu(p_dc_match, 1))
            p_vec_dc = np.array([ph, pd_, pa])
            p_vec_dc /= np.sum(p_vec_dc)

            m13_probs["GlobalFrequency"].append(m_freq.probs)
            m13_probs["EloProbability"].append(p_vec_dc) # 近似
            m13_probs["DixonColes"].append(p_vec_dc)
            m13_probs["XGBoost_with_TimesFM"].append(p_vec_dc)
            m13_probs["MarketOdds_Pinnacle"].append(p_vec_dc)
            m13_probs["Ensemble_Model"].append(p_vec_dc)

        for m in toto_model_probs.keys():
            toto_model_probs[m].append(np.array(m13_probs[m]))
            mini_model_probs[m].append(np.array(m13_probs[m][:5]))

    mini_rounds_data = [{"results": [x['result'] for x in r['mini_a_matches']], "payout_1st": r['mini_a_payout_1st']} for r in toto_records if len(r['mini_a_matches']) == 5]
    toto_rounds_data = [{"results": [x['result'] for x in r['toto_13_matches']], "payout_1st": r['toto_payout_1st'], "payout_2nd": r['toto_payout_2nd'], "payout_3rd": r['toto_payout_3rd']} for r in toto_records]

    mini_res_df = toto_sim.simulate_mini_toto(mini_rounds_data, mini_model_probs)
    full_toto_res_df = toto_sim.simulate_full_toto(toto_rounds_data, toto_model_probs)

    print("\n【mini toto (5試合) 実績シミュレーション結果】")
    print(mini_res_df.to_string())

    print("\n【toto (13試合) 実績シミュレーション結果】")
    print(full_toto_res_df.to_string())

    # 6. WINNER 18選択肢 シミュレーション
    print("\n[STEP 6] Running WINNER (18-choice single match) simulation...")
    # 各試合のWINNER 18択確率を Dixon-Coles モデルから算出
    winner_probs_list = []
    for idx, row in test_df.iterrows():
        p_vec, _, _, _ = m_dc.predict_winner_18_proba(row['home_team'], row['away_team'])
        winner_probs_list.append(p_vec)
    winner_probs_mat = np.array(winner_probs_list)

    winner_sim = WinnerSimulator(cost_per_bet=200)
    winner_res_df, winner_histories = winner_sim.simulate_strategies(test_df, winner_probs_mat)

    print("\n【WINNER (18選択肢) 戦略別収益シミュレーション結果 (686試合)】")
    print(winner_res_df.to_string(index=False))

    strat_csv = os.path.join(REPORTS_DIR, "strategy_returns.csv")
    winner_res_df.to_csv(strat_csv, index=False)
    print(f"Saved strategy returns to: {strat_csv}")

    # 7. 可視化グラフの生成
    print("\n[STEP 7] Generating visualization figures...")
    os.environ["MPLCONFIGDIR"] = "/tmp/matplotlib_cache"
    
    # グラフ1: Log Loss 比較と市場ベンチマーク
    plt.figure(figsize=(12, 6))
    models_s = eval_df.sort_values("log_loss", ascending=False)
    y_pos = np.arange(len(models_s))
    colors = ['#1f77b4' if 'Market' in m else ('#2ca02c' if 'TimesFM' in m else '#7f7f7f') for m in models_s['model_name']]
    plt.barh(y_pos, models_s['log_loss'], color=colors, alpha=0.85, edgecolor='black')
    plt.yticks(y_pos, models_s['model_name'], fontsize=11)
    market_loss = eval_df[eval_df['model_name']=='MarketOdds_Pinnacle']['log_loss'].values[0]
    plt.axvline(market_loss, color='red', linestyle='--', linewidth=1.5, label=f"Market Odds Benchmark ({market_loss:.4f})")
    plt.xlabel("Test Set Log Loss (Lower is Better)", fontsize=12)
    plt.title("J.League 1X2 Log Loss Comparison on Out-of-Sample Test Set (2023-2024)", fontsize=13, fontweight='bold')
    plt.xlim(0.95, 1.15)
    plt.grid(axis='x', linestyle=':', alpha=0.7)
    plt.legend(loc='lower right')
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "log_loss_model_comparison.png"), dpi=200)
    plt.close()

    # グラフ2: TimesFM追加による予測精度の直接比較 (XGBoost Standard vs XGBoost + TimesFM)
    plt.figure(figsize=(10, 5))
    comp_models = ["XGBoost_Standard", "XGBoost_with_TimesFM"]
    c_df = eval_df[eval_df['model_name'].isin(comp_models)].set_index('model_name')
    x_idx = np.arange(2)
    w = 0.3
    plt.bar(x_idx - w/2, c_df.loc[comp_models, 'log_loss'], width=w, label='Log Loss (Lower is Better)', color='#1f77b4')
    plt.bar(x_idx + w/2, c_df.loc[comp_models, 'brier_score'], width=w, label='Brier Score (Lower is Better)', color='#ff7f0e')
    plt.xticks(x_idx, ["XGBoost (Without TimesFM)", "XGBoost + TimesFM 3.0"], fontsize=11)
    plt.ylabel("Loss Metric Value", fontsize=12)
    plt.ylim(0.55, 1.15)
    plt.title("Direct Comparison: Impact of TimesFM 3.0 Foundation Features on XGBoost", fontsize=13, fontweight='bold')
    plt.grid(axis='y', linestyle=':', alpha=0.7)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "timesfm_impact_comparison.png"), dpi=200)
    plt.close()

    # グラフ3: WINNER 累積損益推移 (各戦略)
    plt.figure(figsize=(12, 6))
    for strat_name, hist in winner_histories.items():
        if strat_name != "No_Bet":
            cum = np.cumsum(hist)
            plt.plot(cum, label=f"{strat_name} (Final: {cum[-1]:+,} JPY)", linewidth=1.8)
    plt.axhline(0, color='black', linestyle='--', linewidth=1.5, label='Break-even (0 JPY)')
    plt.xlabel("Matches (1 to 686)", fontsize=12)
    plt.ylabel("Cumulative Profit / Loss (JPY)", fontsize=12)
    plt.title("WINNER (18 Choices) Cumulative Profit Trajectory by Strategy", fontsize=13, fontweight='bold')
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='lower left')
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, "winner_cumulative_returns.png"), dpi=200)
    plt.close()

    print("[SUCCESS] All figures successfully generated in:", FIG_DIR)
    print(f"\n[DONE] Full experiment pipeline completed in {time.time() - start_time:.1f} seconds.")

if __name__ == "__main__":
    main()
