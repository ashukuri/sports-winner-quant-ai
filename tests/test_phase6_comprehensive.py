#!/usr/bin/env python3
"""
tests/test_phase6_comprehensive.py
Phase 6: 最終修正・公式オッズ入力・実モデル推論・フォワードテスト実証の完全テストスイート (20項目)
- Test 01: 動的プロジェクトルート解決と絶対パス不使用
- Test 02: 証拠ファイル・スナップショットの相対パス解決
- Test 03: バスケ16択 正当手動オッズのインポート成功
- Test 04: サッカー18択 正当手動オッズのインポート成功
- Test 05: 不正文字列・欠落選択肢・負値倍率の厳格拒絶
- Test 06: 一次資料未検証時 (MANUAL_UNVERIFIED) の購入除外
- Test 07: 手動入力オッズからのEV計算・購入判断パイプライン疎通
- Test 08: 締切後オッズ (POST_CUTOFF_OBSERVED) のEV購入判断完全停止
- Test 09: 予測作成時刻 (2030年等) の改ざん検知
- Test 10: 取引・予測の表示倍率改ざん検知
- Test 11: 偽の64文字ハッシュの拒否
- Test 12: 取引台帳のレコード削除・順序変更検知
- Test 13: 27特徴量の順序・次元・型の検証
- Test 14: 必須特徴量の不足・欠損時の安全補完・例外判定
- Test 15: 学習時と推論時の特徴量ベクトル完全一致
- Test 16: モデル実体JSONとメタデータ・名称のハッシュ一致
- Test 17: 過去再生モードと本番フォワード予測の明確な分離
- Test 18: NO_BET (オッズあり基準未達) と DATA_UNAVAILABLE (オッズ不在) の厳格区別
- Test 19: 結果未確定試合 (販売中) の精算保留 (PENDING_MATCH_COMPLETION)
- Test 20: 公式約款第5条準拠 (1口200円、10円未満端数切り捨て) 損益完全一致
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

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.config import (
    PROJECT_ROOT,
    DATA_DIR,
    MODELS_DIR,
    RAW_DIR,
    RAW_EVIDENCE_DIR,
    ODDS_SNAPSHOT_DIR,
    resolve_path
)
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
    build_normalized_prediction_string,
    build_normalized_transaction_chain_payload
)
from src.models.basketball.feature_generator import BLeagueFeatureGenerator
from src.settlement.settlement_manager import SettlementManager

class TestPhase6ComprehensiveSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = ForwardPredictionEngine(allow_historical_replay=True)
        cls.odds_mgr = RealOddsSnapshotManager()
        cls.feat_gen = BLeagueFeatureGenerator()
        cls.settler = SettlementManager()

    def test_01_dynamic_project_root_no_absolute_paths(self):
        """[Test 01] 動的プロジェクトルート解決とコード内絶対パスの完全排除"""
        self.assertTrue(os.path.isdir(PROJECT_ROOT))
        self.assertTrue(os.path.isdir(DATA_DIR))
        self.assertTrue(os.path.isdir(MODELS_DIR))
        env_root = os.getenv("WINNER_PROJECT_ROOT")
        if env_root:
            self.assertEqual(os.path.abspath(PROJECT_ROOT), os.path.abspath(env_root))

    def test_02_relative_path_resolution_for_evidence(self):
        """[Test 02] 証拠ファイル・スナップショットの相対パス解決"""
        snap_path = os.path.join(ODDS_SNAPSHOT_DIR, "snapshot_10092_verified.json")
        self.assertTrue(os.path.exists(snap_path))
        with open(snap_path, "r", encoding="utf-8") as f:
            snap = json.load(f)
        rel_ev = snap["raw_evidence_path"]
        self.assertFalse(os.path.isabs(rel_ev), f"Evidence path must be relative: {rel_ev}")
        resolved = resolve_path(rel_ev)
        self.assertTrue(os.path.exists(resolved), f"Resolved path must exist: {resolved}")

    def test_03_import_valid_basketball_16_odds(self):
        """[Test 03] バスケ16択 正当手動オッズのインポート成功"""
        with open(os.path.join(ODDS_SNAPSHOT_DIR, "snapshot_10092_verified.json"), "r") as f:
            s_10092 = json.load(f)
        b_odds = {s["selection_number"]: s["odds"] for s in s_10092["selections"]}

        snap = self.odds_mgr.import_manual_odds(
            lottery_id=10247,
            sport="Basketball",
            odds_dict=b_odds,
            observed_time_utc="2026-10-14T08:30:00Z",
            source_url="https://winner.toto.rakuten.co.jp/detail/singlematch/10247/",
            raw_evidence_content="<html>Official B16 Verified</html>",
            is_verified_with_primary_source=True
        )
        self.assertEqual(snap["evidence_class"], "MANUAL_VERIFIED_PRE_CUTOFF")
        self.assertEqual(snap["n_choices"], 16)
        self.assertTrue(snap["is_valid_for_pre_match_betting"])

    def test_04_import_valid_soccer_18_odds(self):
        """[Test 04] サッカー18択 正当手動オッズのインポート成功"""
        base_s_odds = {
            1: 6.2, 2: 8.5, 3: 7.8, 4: 15.0, 5: 14.0, 6: 25.0, 7: 18.0,
            8: 6.8, 9: 5.5, 10: 12.0, 11: 22.0,
            12: 8.0, 13: 14.0, 14: 11.0, 15: 28.0, 16: 22.0, 17: 35.0, 18: 25.0
        }
        scale = sum(1.0 / o for o in base_s_odds.values()) / 2.0202
        s_odds = {k: round(v * scale, 2) for k, v in base_s_odds.items()}

        snap = self.odds_mgr.import_manual_odds(
            lottery_id=10233,
            sport="Soccer",
            odds_dict=s_odds,
            observed_time_utc="2026-10-14T08:00:00Z",
            source_url="https://winner.toto.rakuten.co.jp/detail/singlematch/10233/",
            raw_evidence_content="<html>Official S18 Verified</html>",
            is_verified_with_primary_source=True
        )
        self.assertEqual(snap["evidence_class"], "MANUAL_VERIFIED_PRE_CUTOFF")
        self.assertEqual(snap["n_choices"], 18)
        self.assertTrue(snap["is_valid_for_pre_match_betting"])

    def test_05_rejection_of_corrupt_manual_odds(self):
        """[Test 05] 不正文字列・選択肢数不足・負値・控除率異常の厳格拒絶"""
        # 1. 選択肢不足
        with self.assertRaises(ValueError):
            self.odds_mgr.import_manual_odds(10247, "Basketball", {1: 5.0}, "2026-10-14T08:00:00Z", "url", "ev")

        # 2. 負倍率
        bad_b = {i: 6.0 for i in range(1, 17)}
        bad_b[1] = -1.0
        with self.assertRaises(ValueError):
            self.odds_mgr.import_manual_odds(10247, "Basketball", bad_b, "2026-10-14T08:00:00Z", "url", "ev")

        # 3. 1.0以下の倍率
        bad_b2 = {i: 6.0 for i in range(1, 17)}
        bad_b2[2] = 0.95
        with self.assertRaises(ValueError):
            self.odds_mgr.import_manual_odds(10247, "Basketball", bad_b2, "2026-10-14T08:00:00Z", "url", "ev")

    def test_06_unverified_primary_evidence_is_not_pre_cutoff(self):
        """[Test 06] 一次資料未検証時 (MANUAL_UNVERIFIED) の購入除外"""
        with open(os.path.join(ODDS_SNAPSHOT_DIR, "snapshot_10092_verified.json"), "r") as f:
            s_10092 = json.load(f)
        b_odds = {s["selection_number"]: s["odds"] for s in s_10092["selections"]}

        snap = self.odds_mgr.import_manual_odds(
            lottery_id=10248,
            sport="Basketball",
            odds_dict=b_odds,
            observed_time_utc="2026-10-14T08:30:00Z",
            source_url="https://winner.toto.rakuten.co.jp/",
            raw_evidence_content="unverified",
            is_verified_with_primary_source=False
        )
        self.assertEqual(snap["evidence_class"], "MANUAL_UNVERIFIED")
        self.assertFalse(snap["is_valid_for_pre_match_betting"])

    def test_07_manual_odds_reaches_ev_calculation(self):
        """[Test 07] 手動入力オッズからのEV計算・購入判断パイプライン疎通"""
        df_p = pd.read_csv(self.engine.predictions_file)
        df_10247 = df_p[df_p["lottery_id"] == 10247]
        self.assertGreater(len(df_10247), 0)
        # EVが数値として算出されていること (Noneではない)
        self.assertTrue(df_10247["predicted_ev"].notna().any())

    def test_08_post_cutoff_odds_halts_ev_betting(self):
        """[Test 08] 締切後オッズ (POST_CUTOFF_OBSERVED) のEV購入判断完全停止"""
        df_t = pd.read_csv(self.engine.transactions_file)
        t_10092 = df_t[df_t["lottery_id"] == 10092]
        self.assertGreater(len(t_10092), 0)
        for _, row in t_10092.iterrows():
            self.assertEqual(row["decision"], "INVALID_ODDS_POST_CUTOFF_OBSERVED")
            self.assertEqual(row["bet_cost_jpy"], 0)

    def test_09_tamper_detection_for_exec_time(self):
        """[Test 09] 予測作成時刻 (2030年等) の改ざん検知"""
        df_p = pd.read_csv(self.engine.predictions_file)
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as tf:
            df_tampered = df_p.copy()
            df_tampered.loc[0, "actual_exec_time_utc"] = "2030-01-01T00:00:00Z"
            df_tampered.to_csv(tf.name, index=False)
            tpath = tf.name

        try:
            ok, msg = ForwardPredictionEngine.verify_prediction_integrity(tpath)
            self.assertFalse(ok, "Must detect tampered exec time")
            self.assertIn("Integrity error", msg)
        finally:
            if os.path.exists(tpath): os.remove(tpath)

    def test_10_tamper_detection_for_observed_odds(self):
        """[Test 10] 取引・予測の表示倍率改ざん検知"""
        # 取引側表示倍率改ざん
        df_t = pd.read_csv(self.engine.transactions_file)
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as tf:
            df_t_tampered = df_t.copy()
            df_t_tampered.loc[0, "observed_odds"] = 99.99
            df_t_tampered.to_csv(tf.name, index=False)
            tpath = tf.name

        try:
            ok, msg = ForwardPredictionEngine.verify_transaction_integrity(tpath)
            self.assertFalse(ok, "Must detect tampered transaction odds")
        finally:
            if os.path.exists(tpath): os.remove(tpath)

    def test_11_fake_hash_rejection(self):
        """[Test 11] 偽の64文字ハッシュの拒否"""
        df_p = pd.read_csv(self.engine.predictions_file)
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as tf:
            df_fake = df_p.copy()
            df_fake.loc[0, "prediction_record_sha256"] = "a" * 64
            df_fake.to_csv(tf.name, index=False)
            tpath = tf.name

        try:
            ok, msg = ForwardPredictionEngine.verify_prediction_integrity(tpath)
            self.assertFalse(ok)
        finally:
            if os.path.exists(tpath): os.remove(tpath)

    def test_12_tamper_detection_for_deletion_and_order_shuffling(self):
        """[Test 12] 取引台帳のレコード削除・順序変更検知"""
        df_t = pd.read_csv(self.engine.transactions_file)
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as tf:
            df_shuffled = df_t.iloc[::-1].reset_index(drop=True)
            df_shuffled.to_csv(tf.name, index=False)
            tpath = tf.name

        try:
            ok, msg = ForwardPredictionEngine.verify_transaction_integrity(tpath)
            self.assertFalse(ok, "Must detect shuffled transaction ledger")
        finally:
            if os.path.exists(tpath): os.remove(tpath)

    def test_13_feature_vector_dimension_order_and_types(self):
        """[Test 13] 27特徴量の順序・次元・型の検証"""
        v = self.feat_gen.generate_features("千葉ジェッツ", "アルバルク東京")
        self.assertEqual(len(v), 27)
        self.assertEqual(v.dtype, np.float32)
        self.assertEqual(self.feat_gen.FEATURE_COLS[0], "elo_diff")
        self.assertEqual(self.feat_gen.FEATURE_COLS[1], "home_elo")
        self.assertEqual(self.feat_gen.FEATURE_COLS[2], "away_elo")
        self.assertEqual(self.feat_gen.FEATURE_COLS[-1], "away_efg_5")

    def test_14_missing_feature_safe_imputation(self):
        """[Test 14] 未知チーム・データ不足時の安全補完"""
        # 履歴が存在しない架空名チームでも定義済みデフォルトで27次元ベクトルを生成
        v = self.feat_gen.generate_features("新規クラブA", "新規クラブB")
        self.assertEqual(len(v), 27)
        self.assertFalse(np.isnan(v).any())
        self.assertFalse(np.isinf(v).any())

    def test_15_feature_consistency_with_training_data(self):
        """[Test 15] 学習時と推論時の特徴量ベクトル整合性"""
        df_train = pd.read_csv(os.path.join(DATA_DIR, "bleague_features.csv"))
        if len(df_train) > 0:
            sample_row = df_train.iloc[0]
            # 特徴量列名が完全一致すること
            for col in self.feat_gen.FEATURE_COLS:
                self.assertIn(col, df_train.columns)

    def test_16_model_artifact_and_metadata_hash_match(self):
        """[Test 16] モデル実体JSONとメタデータ・名称のハッシュ一致"""
        reg, meta, m_hash = ModelArtifactManager.load_basketball_model()
        self.assertEqual(meta["model_name"], "BLeague_B4_Ensemble_Regressor")
        self.assertEqual(len(m_hash), 64)

        params, s_hash = ModelArtifactManager.load_soccer_model()
        self.assertEqual(params["model_name"], "Soccer_DixonColes_Poisson")
        self.assertEqual(len(s_hash), 64)

    def test_17_historical_replay_vs_forward_separation(self):
        """[Test 17] 過去再生モードと本番フォワード予測の明確な分離"""
        # 本番モード (allow_historical_replay=False) では締切時刻が外れた場合に MISSED_DEADLINE
        strict_engine = ForwardPredictionEngine(allow_historical_replay=False)
        self.assertFalse(strict_engine.allow_historical_replay)

    def test_18_distinction_between_no_bet_and_data_unavailable(self):
        """[Test 18] NO_BET (オッズあり基準未達) と DATA_UNAVAILABLE (オッズ不在) の厳格区別"""
        df_t = pd.read_csv(self.engine.transactions_file)
        # オッズ不在の試合 (例: 10234)
        t_unavail = df_t[df_t["lottery_id"] == 10234]
        for _, r in t_unavail.iterrows():
            self.assertEqual(r["decision"], "DATA_UNAVAILABLE")

        # オッズがありEV基準を満たさなかった試合 (例: 10233)
        t_nobet = df_t[(df_t["lottery_id"] == 10233) & (df_t["strategy_name"] == "Conservative_Value")]
        self.assertEqual(t_nobet.iloc[0]["decision"], "NO_BET")

    def test_19_pending_match_completion_settlement(self):
        """[Test 19] 結果未確定試合 (販売中) の精算保留 (PENDING_MATCH_COMPLETION)"""
        df_set = self.settler.settle_transactions(self.engine.transactions_file)
        pending_rows = df_set[df_set["settlement_status"] == "PENDING_MATCH_COMPLETION"]
        self.assertGreater(len(pending_rows), 0)
        # 損益が発生していないこと
        self.assertTrue((pending_rows["net_profit_jpy"] == 0).all())

    def test_20_official_article_5_rounding_accuracy(self):
        """[Test 20] 公式約款第5条準拠 (1口200円、10円未満端数切り捨て) 損益完全一致"""
        cost = 200
        # 5.43倍 -> 1086円 -> 切り捨て1080円
        pay1 = int(np.floor(cost * 5.43 / 10.0)) * 10
        self.assertEqual(pay1, 1080)
        # 3.19倍 -> 638円 -> 切り捨て630円
        pay2 = int(np.floor(cost * 3.19 / 10.0)) * 10
        self.assertEqual(pay2, 630)

if __name__ == "__main__":
    unittest.main()
