#!/usr/bin/env python3
"""
tests/test_quant_audit.py
クオンツ監査・Bリーグモデル・フォワードテストの網羅的自動テストスイート
"""

import os
import sys
import unittest
import numpy as np
import pandas as pd

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.data_fetcher_bleague import get_bleague_winner_category, BLEAGUE_WINNER_CATEGORIES
from src.models.basketball.point_spread_models import continuous_diff_to_16_probs
from src.forward.paper_trader import ForwardPaperTrader, STRATEGY_CONFIG, compute_config_hash

class TestQuantAuditAndModels(unittest.TestCase):

    def test_payout_rounding_rule_agreement(self):
        """WINNER公式約款第5条: 1口200円につき10円未満切り捨ての検証"""
        # オッズ 5.63倍 の場合: 200 * 5.63 = 1126.0円 -> 切り捨て後 1120円
        cost = 200
        odds = 5.63
        raw_payout = cost * odds
        official_payout = int(np.floor(raw_payout / 10.0)) * 10
        self.assertEqual(official_payout, 1120)
        self.assertEqual(official_payout % 10, 0)

        # オッズ 14.31倍 の場合: 200 * 14.31 = 2862.0円 -> 切り捨て後 2860円
        odds_high = 14.31
        official_payout_high = int(np.floor(cost * odds_high / 10.0)) * 10
        self.assertEqual(official_payout_high, 2860)
        self.assertEqual(official_payout_high % 10, 0)

    def test_bleague_16_category_mapping(self):
        """BリーグWINNER 16選択肢への正確なマッピングテスト"""
        # ホーム勝利
        self.assertEqual(get_bleague_winner_category(82, 80), "H_1-3")
        self.assertEqual(get_bleague_winner_category(85, 80), "H_4-6")
        self.assertEqual(get_bleague_winner_category(88, 80), "H_7-9")
        self.assertEqual(get_bleague_winner_category(92, 80), "H_10-14")
        self.assertEqual(get_bleague_winner_category(97, 80), "H_15-19")
        self.assertEqual(get_bleague_winner_category(102, 80), "H_20-24")
        self.assertEqual(get_bleague_winner_category(106, 80), "H_25-29")
        self.assertEqual(get_bleague_winner_category(115, 80), "H_30+")

        # アウェイ勝利
        self.assertEqual(get_bleague_winner_category(80, 82), "A_1-3")
        self.assertEqual(get_bleague_winner_category(80, 85), "A_4-6")
        self.assertEqual(get_bleague_winner_category(80, 88), "A_7-9")
        self.assertEqual(get_bleague_winner_category(80, 92), "A_10-14")
        self.assertEqual(get_bleague_winner_category(80, 97), "A_15-19")
        self.assertEqual(get_bleague_winner_category(80, 102), "A_20-24")
        self.assertEqual(get_bleague_winner_category(80, 106), "A_25-29")
        self.assertEqual(get_bleague_winner_category(80, 115), "A_30+")

        # 同点はバスケでは例外
        with self.assertRaises(ValueError):
            get_bleague_winner_category(80, 80)

    def test_continuous_diff_probability_normalization(self):
        """連続分布から離散16選択肢への積分変換と確率の総和が1.0であることの検証"""
        from scipy.stats import norm, t as student_t
        
        # 正規分布 CDF
        norm_fn = lambda x: norm.cdf(x, loc=3.5, scale=12.0)
        p_norm = continuous_diff_to_16_probs(norm_fn)
        self.assertEqual(len(p_norm), 16)
        self.assertAlmostEqual(np.sum(p_norm), 1.0, places=6)
        self.assertTrue(np.all(p_norm > 0))

        # Student-t 分布 CDF
        t_fn = lambda x: student_t.cdf(x, df=5.0, loc=-2.0, scale=12.5)
        p_t = continuous_diff_to_16_probs(t_fn)
        self.assertEqual(len(p_t), 16)
        self.assertAlmostEqual(np.sum(p_t), 1.0, places=6)
        self.assertTrue(np.all(p_t > 0))

    def test_forward_paper_trader_hash_and_settlement(self):
        """フォワードテストのSHA-256署名、改ざん防止、および元帳追記の検証"""
        tmp_dir = "/tmp/test_forward_ledger"
        import shutil
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

        trader = ForwardPaperTrader(forward_dir=tmp_dir)
        init_balance = trader.get_latest_balance()
        self.assertEqual(init_balance, 100000)

        # 試合情報
        match_info = {
            "match_id": "TEST_M_001",
            "kickoff_time": "2026-10-14T19:05:00",
            "home_team": "宇都宮",
            "away_team": "琉球",
            "categories": BLEAGUE_WINNER_CATEGORIES
        }

        # 予測確率 (H_10-14 に高確率 0.20)
        probs = np.ones(16) * 0.05
        probs[3] = 0.20 # H_10-14
        probs /= np.sum(probs)

        # オッズ (H_10-14 に 8.0倍 -> EV = 0.20 * 8.0 - 1 = +0.60 > 0.15)
        odds = np.ones(16) * 5.0
        odds[3] = 8.0

        # 1. 試合前予測ロック
        locked = trader.lock_pre_match_prediction(match_info, probs, odds)
        self.assertIn("locked_sha256", locked)
        self.assertEqual(len(locked["locked_sha256"]), 64)
        self.assertEqual(len(locked["orders"]), 1)
        self.assertEqual(locked["orders"][0]["category"], "H_10-14")

        # 2. 試合終了照合 (的中: 85 - 72 = 13点差 -> H_10-14 的中)
        ledger_df = trader.settle_match_result("TEST_M_001", 85, 72)
        self.assertEqual(len(ledger_df), 1)
        self.assertEqual(ledger_df.iloc[0]['is_hit'], 1)
        # 払戻金: 200 * 8.0 = 1600円
        self.assertEqual(ledger_df.iloc[0]['official_payout'], 1600)
        self.assertEqual(ledger_df.iloc[0]['net_profit'], 1400)
        self.assertEqual(trader.get_latest_balance(), 100000 - 200 + 1600)

        # 3. 改ざん検知テスト
        ok, msg = trader.verify_ledger_integrity()
        self.assertTrue(ok)

    def test_power_analysis_mathematics(self):
        """検出力分析の計算が数理的に妥当であることの検証"""
        res = ForwardPaperTrader.compute_power_analysis(observed_roi=0.20, std_roi=1.20, alpha=0.05, power=0.80)
        self.assertGreater(res['required_sample_size_bets'], 100)
        self.assertLess(res['required_sample_size_bets'], 1000)

if __name__ == "__main__":
    unittest.main()
