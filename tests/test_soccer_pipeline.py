#!/usr/bin/env python3
"""
tests/test_soccer_pipeline.py
サッカー予測・バックテストパイプラインの単体および結合テストスイート
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.append(BASE_DIR)

from src.models.dixon_coles import DixonColesModel, WINNER_CATEGORIES
from src.models.baseline_models import GlobalFrequencyModel, EloProbabilityModel
from src.models.xgboost_model import SoccerXGBoostModel
from src.backtest.evaluator import compute_log_loss_vector, compute_brier_score_vector, calculate_multiclass_ece
from src.strategy.winner_simulator import WinnerSimulator

class TestSoccerPredictionLab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_path = os.path.join(BASE_DIR, "data", "dataset_with_timesfm.csv")
        cls.df = pd.read_csv(cls.data_path)
        cls.train_df = cls.df[cls.df['split'] == 'train'].reset_index(drop=True)
        cls.test_df = cls.df[cls.df['split'] == 'test'].reset_index(drop=True)

    def test_01_dataset_integrity(self):
        """データセット件数、カラム、スプリットの整合性"""
        self.assertEqual(len(self.df), 3208)
        self.assertTrue('market_prob_H' in self.df.columns)
        self.assertTrue('tfm_exp_goal_diff' in self.df.columns)
        self.assertEqual(len(self.test_df), 686)

    def test_02_baseline_models(self):
        """ベースラインモデルの確率特性 (和=1.0)"""
        m_freq = GlobalFrequencyModel()
        m_freq.fit(self.train_df)
        probs_f = m_freq.predict_proba(self.test_df.head(10))
        np.testing.assert_allclose(np.sum(probs_f, axis=1), np.ones(10), atol=1e-5)

        m_elo = EloProbabilityModel()
        m_elo.fit(self.train_df)
        probs_e = m_elo.predict_proba(self.test_df.head(10))
        np.testing.assert_allclose(np.sum(probs_e, axis=1), np.ones(10), atol=1e-5)

    def test_03_dixon_coles(self):
        """Dixon-Coles モデルの 1X2 および WINNER 18択の確率総和 (1.0)"""
        m_dc = DixonColesModel(max_goals=6)
        m_dc.fit(self.train_df.head(300)) # 高速テスト
        p_vec, p_dict, lh, ma = m_dc.predict_winner_18_proba("川崎Ｆ", "横浜FM")
        self.assertEqual(len(p_vec), 18)
        self.assertAlmostEqual(float(np.sum(p_vec)), 1.0, places=5)
        self.assertTrue(lh > 0)
        self.assertTrue(ma > 0)

    def test_04_xgboost_inference(self):
        """XGBoost モデルの推論と確率正規性"""
        m_xgb = SoccerXGBoostModel(use_timesfm=True, n_estimators=20)
        m_xgb.fit(self.train_df.head(300))
        probs = m_xgb.predict_proba(self.test_df.head(10))
        self.assertEqual(probs.shape, (10, 3))
        np.testing.assert_allclose(np.sum(probs, axis=1), np.ones(10), atol=1e-5)

    def test_05_evaluator_metrics(self):
        """評価指標の計算正常性"""
        y_true = np.array(['H', 'D', 'A', 'H'])
        probs = np.array([
            [0.6, 0.2, 0.2],
            [0.2, 0.5, 0.3],
            [0.1, 0.3, 0.6],
            [0.7, 0.2, 0.1]
        ])
        ll = compute_log_loss_vector(y_true, probs)
        self.assertEqual(len(ll), 4)
        bs = compute_brier_score_vector(y_true, probs)
        self.assertEqual(len(bs), 4)
        ece = calculate_multiclass_ece(probs, y_true)
        self.assertTrue(0.0 <= ece <= 1.0)

    def test_06_winner_simulator(self):
        """WINNER 戦略シミュレータの損益計算"""
        sim = WinnerSimulator(cost_per_bet=200)
        dummy_probs = np.full((10, 18), 1.0 / 18.0)
        sub_df = self.test_df.head(10)
        res_df, _ = sim.simulate_strategies(sub_df, dummy_probs)
        self.assertTrue(len(res_df) >= 4)
        self.assertIn("Strategy", res_df.columns)

if __name__ == "__main__":
    unittest.main()
