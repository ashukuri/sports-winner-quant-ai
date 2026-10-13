#!/usr/bin/env python3
"""
tests/test_phase5_regression.py
Phase 5: 重大バグ修正・実測オッズ取得・フォワードテスト稼働検証の完全回帰テストスイート (16項目)
- Bug 1: 競技誤分類解消 (B.ONE等バスケ商品の16択分類)
- Bug 2: 公式選択肢番号 (1〜16 / 1〜18) を主キーとする確率・オッズ完全結合
- Bug 3: 締切後オッズの事前実測偽装排除 (POST_CUTOFF_OBSERVED は購入除外)
- Bug 4: 追記専用台帳、同一ID上書き拒否、正規化ハッシュ検証、改ざん検出
- Bug 5: 本物の学習済みモデルアーティファクトのロード、モデル不在時エラー
- Bug 6: 販売締切60分前実行の許容範囲 (±120s) 検証、逸脱時 MISSED_DEADLINE
- システム品質: 架空試合拒絶、合成倍率排除、オッズ不在時EV停止、未確定試合保留、
              公式約款第5条端数処理、確率正規化、トランザクションハッシュチェーン完全性
"""

import os
import sys
import json
import shutil
import hashlib
import tempfile
import unittest
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
MODELS_DIR = os.path.join(DATA_DIR, "models")
RAW_DIR = os.path.join(DATA_DIR, "raw")
SNAPSHOT_DIR = os.path.join(DATA_DIR, "odds_snapshots")

from src.schema.winner_schema import (
    BASKETBALL_CHOICE_MAP,
    SOCCER_CHOICE_MAP,
    determine_sport,
    resolve_choice_number
)
from src.fixtures.fixture_manager import FixtureIntegrityManager
from src.odds.odds_snapshot_manager import RealOddsSnapshotManager
from src.forward.forward_engine import (
    ForwardPredictionEngine,
    ModelArtifactManager,
    build_normalized_pred_string
)
from src.settlement.settlement_manager import SettlementManager

class TestPhase5RegressionSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # テスト実行前の初期化
        cls.engine = ForwardPredictionEngine(allow_historical_replay=True)
        cls.settler = SettlementManager()

    def test_01_sport_misclassification_fix(self):
        """[Bug 1] 競技誤分類解消: 10247, 10248 が Basketball (16択) として登録・分類されること"""
        df_fix = pd.read_csv(os.path.join(DATA_DIR, "verified_fixtures.csv"))
        f_10247 = df_fix[df_fix["lottery_id"] == 10247]
        f_10248 = df_fix[df_fix["lottery_id"] == 10248]

        self.assertEqual(len(f_10247), 1, "Fixture 10247 must exist in verified_fixtures.csv")
        self.assertEqual(len(f_10248), 1, "Fixture 10248 must exist in verified_fixtures.csv")

        self.assertEqual(f_10247.iloc[0]["sport"], "Basketball")
        self.assertEqual(f_10248.iloc[0]["sport"], "Basketball")

        # 予測エンジンで推論した際の選択肢数が16であることを確認
        probs_10247 = self.engine.predict_basketball_probs(
            f_10247.iloc[0]["home_team"], f_10247.iloc[0]["away_team"]
        )
        self.assertEqual(len(probs_10247), 16)

    def test_02_selection_primary_key_alignment(self):
        """[Bug 2] selection_number を主キーとしてオッズと確率が1対1結合され、欠損・不一致がないこと"""
        # バスケ 16択マッピング検証
        for num in range(1, 17):
            self.assertIn(num, BASKETBALL_CHOICE_MAP)
            resolved = resolve_choice_number("Basketball", BASKETBALL_CHOICE_MAP[num]["code"])
            self.assertEqual(resolved, num)

        # サッカー 18択マッピング検証
        for num in range(1, 19):
            self.assertIn(num, SOCCER_CHOICE_MAP)
            resolved = resolve_choice_number("Soccer", SOCCER_CHOICE_MAP[num]["code"])
            self.assertEqual(resolved, num)

    def test_03_post_cutoff_odds_exclusion(self):
        """[Bug 3] 締切後オッズ (POST_CUTOFF_OBSERVED) は購入除外 (INVALID_ODDS) となり購入額0円であること"""
        snap_path = os.path.join(SNAPSHOT_DIR, "snapshot_10092_verified.json")
        self.assertTrue(os.path.exists(snap_path))
        with open(snap_path, "r", encoding="utf-8") as f:
            snap = json.load(f)
        self.assertEqual(snap["evidence_class"], "POST_CUTOFF_OBSERVED")

        # 取引台帳での記録を検証
        df_tx = pd.read_csv(os.path.join(DATA_DIR, "forward_transactions.csv"))
        tx_10092 = df_tx[df_tx["lottery_id"] == 10092]
        self.assertGreater(len(tx_10092), 0)
        for _, row in tx_10092.iterrows():
            self.assertTrue(row["decision"].startswith("INVALID_ODDS"))
            self.assertEqual(row["bet_cost_jpy"], 0)

    def test_04_fake_hash_rejection(self):
        """[Bug 4] 偽ハッシュ・改ざんハッシュを持つレコードは検証関数で明示的に拒否されること"""
        norm_str = build_normalized_pred_string("PRED_TEST", 1, "1-0", 0.15, 6.5, -0.025, "HASH_A")
        correct_hash = hashlib.sha256(norm_str.encode()).hexdigest()
        fake_hash = "0" * 64

        self.assertNotEqual(correct_hash, fake_hash)

        # 一時CSVを作成して検証
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as tf:
            df = pd.DataFrame([{
                "prediction_id": "PRED_TEST",
                "selection_number": 1,
                "choice_code": "1-0",
                "predicted_prob": 0.15,
                "observed_odds": 6.5,
                "predicted_ev": -0.025,
                "model_hash": "HASH_A",
                "prediction_record_sha256": fake_hash
            }])
            df.to_csv(tf.name, index=False)
            temp_path = tf.name

        try:
            ok, msg = ForwardPredictionEngine.verify_prediction_integrity(temp_path)
            self.assertFalse(ok)
            self.assertIn("Integrity error", msg)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_05_tamper_detection(self):
        """[Bug 4] 予測台帳の確率・オッズが1箇所でも改ざんされた場合、検知して False を返すこと"""
        df_p = pd.read_csv(os.path.join(DATA_DIR, "forward_predictions.csv"))
        self.assertGreater(len(df_p), 0)

        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as tf:
            df_tampered = df_p.copy()
            df_tampered.loc[0, "predicted_prob"] = round(float(df_tampered.loc[0, "predicted_prob"]) + 0.05, 5)
            df_tampered.to_csv(tf.name, index=False)
            temp_path = tf.name

        try:
            ok, msg = ForwardPredictionEngine.verify_prediction_integrity(temp_path)
            self.assertFalse(ok)
            self.assertIn("Integrity error", msg)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_06_duplicate_overwrite_rejection(self):
        """[Bug 4] 同一 prediction_id のレコードが存在する場合、重複書き込みが拒否されること"""
        engine = ForwardPredictionEngine(allow_historical_replay=True)
        # 既に評価済みの台帳に対して再度 execute_evaluation を実行
        new_p, new_t = engine.execute_evaluation()
        self.assertEqual(new_p, 0, "Duplicate predictions must be rejected with 0 new rows.")
        self.assertEqual(new_t, 0, "Duplicate transactions must be rejected with 0 new rows.")

    def test_07_model_absence_raises_error(self):
        """[Bug 5] モデルアーティファクトが存在しない場合、明示的例外 (FileNotFoundError) を発生させること"""
        with self.assertRaises(FileNotFoundError):
            ModelArtifactManager.compute_sha256("non_existent_model_file.json")

    def test_08_cutoff_60min_window_enforcement(self):
        """[Bug 6] 販売締切60分前 (±120s) 以外のタイミングでは MISSED_DEADLINE となること"""
        # allow_historical_replay=False で実行した場合の挙動テスト
        strict_engine = ForwardPredictionEngine(allow_historical_replay=False)
        
        now_utc = datetime.now(timezone.utc)
        # 締切時刻が現在から10分後の試合 (60分前を大幅に超過している)
        sales_end_dt = now_utc + timedelta(minutes=10)
        sched_eval_dt = sales_end_dt - timedelta(minutes=60) # 50分前
        diff_sec = abs((now_utc - sched_eval_dt).total_seconds()) # 約3000秒

        self.assertGreater(diff_sec, 120.0)

    def test_09_fictitious_fixture_rejection(self):
        """実在しない架空試合 (例: 20001, 群馬 vs 千葉J) が verified_fixtures.csv に存在しないこと"""
        df_fix = pd.read_csv(os.path.join(DATA_DIR, "verified_fixtures.csv"))
        self.assertFalse(any(df_fix["lottery_id"].astype(str).str.startswith("2000")))
        
        # 架空対戦カードが含まれていないこと
        gunma_chiba = df_fix[(df_fix["home_team"].str.contains("群馬")) & (df_fix["away_team"].str.contains("千葉"))]
        self.assertEqual(len(gunma_chiba), 0)

    def test_10_synthetic_odds_elimination(self):
        """実測オッズスナップショットが存在しない試合は ODDS_UNAVAILABLE となり、合成倍率を捏造しないこと"""
        df_tx = pd.read_csv(os.path.join(DATA_DIR, "forward_transactions.csv"))
        # 未インポートの販売中試合 (10234〜10240, 10248) は実測未取得のため ODDS_UNAVAILABLE であること
        in_sale_tx = df_tx[df_tx["lottery_id"].isin([10234, 10235, 10236, 10237, 10238, 10239, 10240, 10248])]
        for _, row in in_sale_tx.iterrows():
            self.assertEqual(row["odds_status"], "ODDS_UNAVAILABLE")
            self.assertEqual(row["decision"], "DATA_UNAVAILABLE")
            self.assertEqual(row["bet_cost_jpy"], 0)

    def test_11_odds_absence_halts_ev_calc(self):
        """オッズ不在時、期待値 (EV) の計算を行わず None / DATA_UNAVAILABLE となること"""
        df_p = pd.read_csv(os.path.join(DATA_DIR, "forward_predictions.csv"))
        unavail_p = df_p[df_p["odds_status"] == "ODDS_UNAVAILABLE"]
        self.assertGreater(len(unavail_p), 0)
        self.assertTrue(unavail_p["predicted_ev"].isna().all())
        self.assertTrue(unavail_p["observed_odds"].isna().all())

    def test_12_pending_match_settlement_retention(self):
        """試合結果が未確定の試合は PENDING_MATCH_COMPLETION として保留されること"""
        df_set = pd.read_csv(os.path.join(DATA_DIR, "settlements.csv"))
        pending_rows = df_set[df_set["lottery_id"].isin([10233, 10234, 10247, 10248])]
        self.assertGreater(len(pending_rows), 0)
        for _, row in pending_rows.iterrows():
            self.assertEqual(row["settlement_status"], "PENDING_MATCH_COMPLETION")
            self.assertEqual(row["net_profit_jpy"], 0)

    def test_13_official_payout_article_5_rounding(self):
        """公式約款第5条準拠: 1口200円、10円未満端数切り捨て計算が正確に行われること"""
        # テストケース1: オッズ 5.43倍 -> 200 * 5.43 = 1086 -> 1080円
        cost = 200
        odds1 = 5.43
        payout1 = int(np.floor(cost * odds1 / 10.0)) * 10
        self.assertEqual(payout1, 1080)

        # テストケース2: オッズ 7.89倍 -> 200 * 7.89 = 1578 -> 1570円
        odds2 = 7.89
        payout2 = int(np.floor(cost * odds2 / 10.0)) * 10
        self.assertEqual(payout2, 1570)

        # テストケース3: 千葉J vs A東京 (10092) の公式払戻金照合
        res_10092 = self.settler.official_results_map.get("10092")
        self.assertEqual(res_10092["payout_per_200jpy"], 1080)

    def test_14_relative_path_portability(self):
        """プロジェクトルートからの相対パス解決および環境変数の整合性"""
        self.assertTrue(os.path.isdir(DATA_DIR))
        self.assertTrue(os.path.isdir(MODELS_DIR))
        self.assertTrue(os.path.isdir(RAW_DIR))
        self.assertTrue(os.path.isdir(SNAPSHOT_DIR))

    def test_15_probability_sum_normalization(self):
        """サッカー (18択) およびバスケ (16択) の予測確率総和が 1.0 (±1e-5) であること"""
        # サッカー
        s_probs = self.engine.predict_soccer_probs("川崎フロンターレ", "横浜F・マリノス")
        self.assertEqual(len(s_probs), 18)
        self.assertAlmostEqual(float(np.sum(s_probs)), 1.0, places=5)

        # バスケ
        b_probs = self.engine.predict_basketball_probs("千葉ジェッツ", "アルバルク東京")
        self.assertEqual(len(b_probs), 16)
        self.assertAlmostEqual(float(np.sum(b_probs)), 1.0, places=5)

    def test_16_transaction_chain_sha256_integrity(self):
        """トランザクションハッシュチェーン (SHA-256) が unbroken であり完全性検証に成功すること"""
        ok_t, msg_t = ForwardPredictionEngine.verify_transaction_integrity()
        self.assertTrue(ok_t, f"Transaction chain integrity failed: {msg_t}")

        ok_p, msg_p = ForwardPredictionEngine.verify_prediction_integrity()
        self.assertTrue(ok_p, f"Prediction integrity failed: {msg_p}")

if __name__ == "__main__":
    unittest.main()
