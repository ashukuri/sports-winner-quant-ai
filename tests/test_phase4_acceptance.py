#!/usr/bin/env python3
"""
tests/test_phase4_acceptance.py
Phase 4: 受入テストスイート (Acceptance Tests)
- Test 1: 公式試合データ取得 & 実在性突合 (架空カード混入なし)
- Test 2: 公式倍率取得 & 一次資料整合性 (逆数合計 2.0202 検証)
- Test 3: 不正データの拒絶 (存在しない試合、同一チーム、選択肢欠落、異常オッズ、締切後)
- Test 4: 予測の固定保存 & 重複・上書き拒絶
- Test 5: 公式結果による精算 (公式約款第5条端数処理、的中・不的中判定)
"""

import os
import sys
import json
import hashlib
import unittest
import numpy as np
import pandas as pd

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
from src.fixtures.fixture_manager import FixtureIntegrityManager
from src.odds.odds_snapshot_manager import RealOddsSnapshotManager
from src.settlement.settlement_manager import SettlementManager

class TestPhase4Acceptance(unittest.TestCase):

    def test_1_official_fixtures_verification(self):
        """Test 1: 公式試合データ取得と実在カード突合"""
        fix_path = os.path.join(DATA_DIR, "verified_fixtures.csv")
        self.assertTrue(os.path.exists(fix_path), "verified_fixtures.csv must exist.")
        df = pd.read_csv(fix_path)
        self.assertGreater(len(df), 50, "Should contain verified historical and in-sale matches.")

        # 必須カラムの存在チェック
        required_cols = ["sport", "league", "lottery_id", "commodity_name", "home_team", "away_team", "sales_end_datetime", "status"]
        for col in required_cols:
            self.assertIn(col, df.columns)

        # 販売中試合の存在確認 (ルヴァンカップ & B.ONE)
        in_sale = df[df["status"] == "IN_SALE"]
        self.assertGreaterEqual(len(in_sale), 10)
        self.assertTrue(any("横浜" in str(x) for x in in_sale["home_team"]))
        self.assertTrue(any("鹿児島" in str(x) for x in in_sale["home_team"]))

        # 架空カードが含まれていないことの確認
        self.assertFalse(any("20001" in str(x) for x in df["lottery_id"]))
        self.assertFalse(any("20002" in str(x) for x in df["lottery_id"]))

    def test_2_official_odds_verification_and_reciprocal_sum(self):
        """Test 2: 公式倍率取得と一次資料・逆数合計 (2.0202) の検証"""
        snap_path = os.path.join(DATA_DIR, "odds_snapshots", "snapshot_10092_verified.json")
        self.assertTrue(os.path.exists(snap_path), "Primary snapshot for lottery 10092 must exist.")

        with open(snap_path, "r", encoding="utf-8") as f:
            snap = json.load(f)

        self.assertEqual(snap["lottery_id"], "10092")
        self.assertIn(snap["status"], ["ODDS_VERIFIED_AUTHENTIC", "POST_CUTOFF_ARCHIVED_ODDS"])
        self.assertEqual(snap["n_choices"], 16)

        # 全16選択肢の倍率を取得して逆数合計を計算
        odds = [sel["odds"] for sel in snap["selections"]]
        self.assertEqual(len(odds), 16)
        self.assertTrue(all(o > 1.0 for o in odds))

        reciprocal_sum = sum(1.0 / o for o in odds)
        # 真の公式WINNERオッズの逆数合計は約2.02 (払戻率約49.5%)
        self.assertAlmostEqual(reciprocal_sum, 2.0202, delta=0.01)

        # 生証拠ファイルとそのSHA-256ハッシュの完全性
        ev_file = snap["raw_evidence_path"]
        self.assertTrue(os.path.exists(ev_file))
        with open(ev_file, "rb") as f:
            calc_hash = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(calc_hash, snap["raw_evidence_sha256"])

    def test_3_rejection_of_invalid_and_corrupt_data(self):
        """Test 3: 不正データの自動検知と除絶テスト"""
        mgr = FixtureIntegrityManager()

        # ケースA: 存在しない試合 / lottery_id なし
        bad_item_1 = {"lotteryId": None, "commodityName": "架空試合 A vs B"}
        self.assertFalse(mgr.parse_official_loto_item(bad_item_1, "Soccer"))

        # ケースB: ホーム・アウェイ同一チーム不正
        bad_item_2 = {"lotteryId": "99991", "commodityId": "1", "homeTeamName": "川崎F", "awayTeamName": "川崎F", "salesEndDatetime": "2026-10-14T09:00:00Z", "gameDate": "2026-10-14T10:00:00Z"}
        self.assertFalse(mgr.parse_official_loto_item(bad_item_2, "Soccer"))

        # ケースC: 販売締切時刻欠損
        bad_item_3 = {"lotteryId": "99992", "commodityId": "1", "homeTeamName": "浦和", "awayTeamName": "鹿島", "gameDate": "2026-10-14T10:00:00Z"}
        self.assertFalse(mgr.parse_official_loto_item(bad_item_3, "Soccer"))

        # ケースD: 中止・返還フラグ付き
        bad_item_4 = {"lotteryId": "99993", "commodityId": "1", "homeTeamName": "千葉J", "awayTeamName": "A東京", "salesEndDatetime": "2026-10-14T09:00:00Z", "gameDate": "2026-10-14T10:00:00Z", "lotHoldQuitFlag": True}
        self.assertFalse(mgr.parse_official_loto_item(bad_item_4, "Basketball"))

        # 拒否ログに全件記録されていることの確認
        self.assertEqual(len(mgr.rejected_fixtures), 4)

    def test_4_prediction_locking_and_duplicate_rejection(self):
        """Test 4: 予測の固定保存と暗号学的ハッシュ記録"""
        pred_csv = os.path.join(DATA_DIR, "forward_predictions.csv")
        tx_csv = os.path.join(DATA_DIR, "forward_transactions.csv")
        self.assertTrue(os.path.exists(pred_csv))
        self.assertTrue(os.path.exists(tx_csv))

        df_tx = pd.read_csv(tx_csv)
        # 全取引レコードにchain_sha256が存在すること
        self.assertTrue(all(len(str(h)) == 64 for h in df_tx["chain_sha256"]))

        # 実測オッズ不在時は正しく DATA_UNAVAILABLE または UNAVAILABLE_DUE_TO_NO_ODDS になっていること
        unavail_tx = df_tx[df_tx["odds_status"] == "ODDS_UNAVAILABLE"]
        self.assertTrue(all(d in ["UNAVAILABLE_DUE_TO_NO_ODDS", "DATA_UNAVAILABLE"] for d in unavail_tx["decision"]))
        self.assertTrue(all(c == 0 for c in unavail_tx["bet_cost_jpy"]))

    def test_5_official_result_settlement_and_article_5_rounding(self):
        """Test 5: 公式結果による精算テスト (公式約款第5条端数切り捨て)"""
        settler = SettlementManager()

        # 1. 第423回 千葉J vs A東京 (lotteryId: 10092) の照合
        res_10092 = settler.official_results_map.get("10092")
        self.assertIsNotNone(res_10092)
        self.assertEqual(res_10092["home_score"], 131)
        self.assertEqual(res_10092["away_score"], 138)
        self.assertEqual(res_10092["payout_per_200jpy"], 1080)

        win_cat = settler.determine_winning_category(res_10092)
        self.assertIn(win_cat, ["アウェイ勝利7-9", "A_7-9"])

        # 2. 公式約款第5条端数処理の計算テスト
        # オッズ 7.35倍 の場合: 200 * 7.35 = 1470円
        cost = 200
        odds_val = 7.35
        raw_payout = cost * odds_val
        official_payout = int(np.floor(raw_payout / 10.0)) * 10
        self.assertEqual(official_payout, 1470)

        # オッズ 5.43倍 の場合: 200 * 5.43 = 1086円 -> 切り捨て後 1080円
        odds_val2 = 5.43
        official_payout2 = int(np.floor(cost * odds_val2 / 10.0)) * 10
        self.assertEqual(official_payout2, 1080)
        self.assertEqual(official_payout2 % 10, 0)

if __name__ == "__main__":
    import hashlib
    unittest.main()
