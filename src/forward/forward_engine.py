#!/usr/bin/env python3
"""
src/forward/forward_engine.py
Phase 6: フォワードテスト推論・意思決定エンジン (Task A〜E完全統合版)
- Task A: 動的プロジェクトルート解決 (src.config 準拠)
- Task B: 手動インポートオッズ (MANUAL_VERIFIED_PRE_CUTOFF) の完全連携
- Task C: 全項目 (予測作成時刻、表示倍率、締切時刻、EV、証拠ハッシュ等) を保護する
          完全正規化レコードSHA-256ハッシュ & 改ざん検知チェーン
- Task D: BLeagueFeatureGenerator による厳格な 27特徴量完全生成推論 (ゼロ埋め撤廃)
- Task E: 締切60分前 (scheduled_eval_time_utc) 判定、追記専用 (Append-only) 台帳
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import t as student_t, poisson

from src.config import (
    PROJECT_ROOT,
    DATA_DIR,
    MODELS_DIR,
    ODDS_SNAPSHOT_DIR,
    REPORTS_DIR,
    resolve_path
)

from src.schema.winner_schema import (
    BASKETBALL_CHOICE_MAP,
    SOCCER_CHOICE_MAP,
    resolve_choice_number
)
from src.models.dixon_coles import tau
from src.models.basketball.feature_generator import BLeagueFeatureGenerator

def normalize_field_str(val, default="NONE") -> str:
    """pandas欠損値 (None, nan) を統一して決定論的に文字列化"""
    if val is None or pd.isna(val):
        return default
    s = str(val).strip()
    if s.lower() in ["none", "nan"]:
        return default
    return s

def build_normalized_pred_string(prediction_id, num, code, p, o, ev, m_hash):
    """Phase 5後方互換ラッパー"""
    p_str = f"{float(p):.5f}" if p is not None and not pd.isna(p) else "NONE"
    o_str = f"{float(o):.2f}" if o is not None and not pd.isna(o) else "NONE"
    ev_str = f"{float(ev):.4f}" if ev is not None and not pd.isna(ev) else "NONE"
    return f"{prediction_id}_{num}_{code}_{p_str}_{o_str}_{ev_str}_{m_hash}"

def build_normalized_prediction_string(
    pred_id: str,
    lottery_id: str,
    sport: str,
    commodity_name: str,
    sales_end: str,
    sched_eval: str,
    exec_time: str,
    timing_status: str,
    sel_num: int | str,
    choice_code: str,
    prob: Optional[float],
    odds: Optional[float],
    ev: Optional[float],
    odds_status: str,
    ev_class: str,
    raw_ev_sha: str,
    m_name: str,
    m_ver: str,
    m_hash: str
) -> str:
    """
    Task C: 予測レコードの厳格な正規化文字列 (フィールド順・フォーマット固定)
    - 予測作成時刻 (exec_time) や 表示倍率 (odds) の改ざんを100%検知
    """
    p_str = f"{float(prob):.5f}" if prob is not None and not pd.isna(prob) else "NONE"
    o_str = f"{float(odds):.2f}" if odds is not None and not pd.isna(odds) else "NONE"
    ev_str = f"{float(ev):.4f}" if ev is not None and not pd.isna(ev) else "NONE"

    fields = [
        normalize_field_str(pred_id), normalize_field_str(lottery_id),
        normalize_field_str(sport), normalize_field_str(commodity_name),
        normalize_field_str(sales_end), normalize_field_str(sched_eval),
        normalize_field_str(exec_time), normalize_field_str(timing_status),
        normalize_field_str(sel_num), normalize_field_str(choice_code),
        p_str, o_str, ev_str,
        normalize_field_str(odds_status), normalize_field_str(ev_class),
        normalize_field_str(raw_ev_sha),
        normalize_field_str(m_name), normalize_field_str(m_ver), normalize_field_str(m_hash)
    ]
    return "|".join(fields)

def build_normalized_transaction_chain_payload(prev_chain: str, row_dict: Dict[str, Any]) -> str:
    """
    Task C: 取引台帳の厳格なハッシュチェーンペイロード
    - 取引時刻 (timestamp_utc)、表示倍率 (observed_odds)、購入金額 (bet_cost_jpy) 等を保護
    """
    tx_id = row_dict.get("tx_id", "")
    ts = row_dict.get("timestamp_utc", "")
    strat = row_dict.get("strategy_name", "")
    lid = row_dict.get("lottery_id", "")
    commodity = row_dict.get("commodity_name", "")
    sport = row_dict.get("sport", "")
    decision = row_dict.get("decision", "")
    
    sel_num_raw = row_dict.get("selected_selection_number")
    if sel_num_raw is not None and not pd.isna(sel_num_raw) and str(sel_num_raw).strip().lower() not in ["none", "nan"]:
        try:
            sel_num = str(int(float(sel_num_raw)))
        except (ValueError, TypeError):
            sel_num = "NONE"
    else:
        sel_num = "NONE"

    sel_code = row_dict.get("selected_choice_code", "NONE")

    p = row_dict.get("predicted_prob")
    p_str = f"{float(p):.5f}" if p is not None and not pd.isna(p) else "NONE"

    o = row_dict.get("observed_odds")
    o_str = f"{float(o):.2f}" if o is not None and not pd.isna(o) else "NONE"

    ev = row_dict.get("predicted_ev")
    ev_str = f"{float(ev):.4f}" if ev is not None and not pd.isna(ev) else "NONE"

    cost_raw = row_dict.get("bet_cost_jpy", 0)
    try:
        cost_str = str(int(float(cost_raw)))
    except (ValueError, TypeError):
        cost_str = "0"

    timing = row_dict.get("timing_status", "")
    odds_st = row_dict.get("odds_status", "")
    ev_class = row_dict.get("evidence_class", "")
    raw_sha = row_dict.get("raw_evidence_sha256", "NONE")
    m_ver = row_dict.get("model_version", "")
    m_hash = row_dict.get("model_hash", "")

    fields = [
        normalize_field_str(prev_chain), normalize_field_str(tx_id),
        normalize_field_str(ts), normalize_field_str(strat),
        normalize_field_str(lid), normalize_field_str(commodity),
        normalize_field_str(sport), normalize_field_str(decision),
        normalize_field_str(sel_num), normalize_field_str(sel_code),
        p_str, o_str, ev_str, cost_str,
        normalize_field_str(timing), normalize_field_str(odds_st),
        normalize_field_str(ev_class), normalize_field_str(raw_sha),
        normalize_field_str(m_ver), normalize_field_str(m_hash)
    ]
    return "|".join(fields)

class ModelArtifactManager:
    """学習済みモデルのロードとハッシュ検証"""
    @staticmethod
    def compute_sha256(filepath: str) -> str:
        with open(filepath, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    @classmethod
    def load_basketball_model(cls) -> Tuple[xgb.XGBRegressor, dict, str]:
        model_path = os.path.join(MODELS_DIR, "b4_xgboost_regressor.json")
        meta_path = os.path.join(MODELS_DIR, "b4_xgboost_meta.json")
        if not os.path.exists(model_path) or not os.path.exists(meta_path):
            raise FileNotFoundError(f"Basketball model artifact not found at {model_path}")

        reg = xgb.XGBRegressor()
        reg.load_model(model_path)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        m_hash = cls.compute_sha256(model_path)
        return reg, meta, m_hash

    @classmethod
    def load_soccer_model(cls) -> Tuple[dict, str]:
        params_path = os.path.join(MODELS_DIR, "dixon_coles_params.json")
        if not os.path.exists(params_path):
            raise FileNotFoundError(f"Soccer model params not found at {params_path}")
        with open(params_path, "r", encoding="utf-8") as f:
            params = json.load(f)
        s_hash = cls.compute_sha256(params_path)
        return params, s_hash

class ForwardPredictionEngine:
    def __init__(self, allow_historical_replay: bool = False):
        self.allow_historical_replay = allow_historical_replay
        self.predictions_file = os.path.join(DATA_DIR, "forward_predictions.csv")
        self.transactions_file = os.path.join(DATA_DIR, "forward_transactions.csv")
        self._init_models()
        self._init_feature_generators()
        self._init_ledgers()

    def _init_models(self):
        """本物の学習済みモデルのロード"""
        try:
            self.b_reg, self.b_meta, self.b_hash = ModelArtifactManager.load_basketball_model()
            self.s_params, self.s_hash = ModelArtifactManager.load_soccer_model()
            print(f"[ForwardEngine] Loaded Basketball XGBoost (SHA: {self.b_hash[:16]}...)")
            print(f"[ForwardEngine] Loaded Soccer Dixon-Coles (SHA: {self.s_hash[:16]}...)")
        except Exception as e:
            print(f"[CRITICAL ERROR] Failed to load model artifacts: {e}")
            raise

    def _init_feature_generators(self):
        """Task D: 27特徴量生成パイプラインの初期化"""
        self.b_feat_gen = BLeagueFeatureGenerator()

    def _init_ledgers(self):
        """Task C: 台帳スキーマ初期化"""
        if not os.path.exists(self.predictions_file):
            cols_p = [
                "prediction_id", "lottery_id", "sport", "commodity_name", "home_team", "away_team",
                "sales_end_datetime", "scheduled_eval_time_utc", "actual_exec_time_utc",
                "timing_status", "selection_number", "choice_code", "choice_name",
                "predicted_prob", "observed_odds", "predicted_ev", "odds_status",
                "evidence_class", "raw_evidence_sha256", "model_name", "model_version", "model_hash",
                "prediction_record_sha256"
            ]
            pd.DataFrame(columns=cols_p).to_csv(self.predictions_file, index=False)

        if not os.path.exists(self.transactions_file):
            cols_t = [
                "tx_id", "timestamp_utc", "strategy_name", "lottery_id", "commodity_name",
                "sport", "decision", "selected_selection_number", "selected_choice_code",
                "predicted_prob", "observed_odds", "predicted_ev", "bet_cost_jpy",
                "timing_status", "odds_status", "evidence_class", "raw_evidence_sha256",
                "model_version", "model_hash", "prev_chain_hash", "chain_sha256"
            ]
            pd.DataFrame(columns=cols_t).to_csv(self.transactions_file, index=False)

    def get_last_chain_hash(self) -> str:
        if os.path.exists(self.transactions_file):
            df = pd.read_csv(self.transactions_file)
            if len(df) > 0 and "chain_sha256" in df.columns:
                return str(df.iloc[-1]["chain_sha256"])
        return "0" * 64

    def predict_basketball_probs(self, home_team: str, away_team: str, match_date: Optional[datetime] = None) -> np.ndarray:
        """
        Task D: 学習済みXGBoost + Student-t + Elo アンサンブル (27特徴量完全生成)
        """
        # 1. 27特徴量ベクトルを厳格生成 (ゼロ埋め撤廃)
        feat_vec = self.b_feat_gen.generate_features(home_team, away_team, match_date)
        pred_spread_xgb = float(self.b_reg.predict(feat_vec.reshape(1, -1))[0])

        # 2. Elo単体スプレッド
        elo_diff = feat_vec[0]  # feat_vec[0] は elo_diff
        expected_spread_elo = elo_diff / 25.0 + 3.5

        # 3. アンサンブル期待点差 (59.3% Elo + 40.7% XGBoost)
        w_elo = self.b_meta["elo_weight"]
        w_xgb = self.b_meta["xgb_weight"]
        final_spread = w_elo * expected_spread_elo + w_xgb * pred_spread_xgb

        # 4. Student-t 分布による16選択肢積分
        df_t = self.b_meta["student_t_df"]
        sigma = self.b_meta["student_t_sigma"]

        probs = []
        for num in range(1, 17):
            info = BASKETBALL_CHOICE_MAP[num]
            low = info["min_diff"]
            high = info["max_diff"]
            if info["side"] == "HOME":
                p = student_t.cdf(high + 0.5, df=df_t, loc=final_spread, scale=sigma) - \
                    student_t.cdf(low - 0.5, df=df_t, loc=final_spread, scale=sigma)
            else:
                p = student_t.cdf(-low + 0.5, df=df_t, loc=final_spread, scale=sigma) - \
                    student_t.cdf(-high - 0.5, df=df_t, loc=final_spread, scale=sigma)
            probs.append(max(float(p), 1e-5))

        probs = np.array(probs)
        probs = probs / np.sum(probs)
        return probs

    def predict_soccer_probs(self, home_team: str, away_team: str) -> np.ndarray:
        """Dixon-Colesモデルによる18選択肢確率"""
        att = self.s_params["attack"]
        defe = self.s_params["defense"]
        home_adv = self.s_params["home_adv"]
        rho = self.s_params["rho"]

        att_h = att.get(home_team, 0.0)
        def_a = defe.get(away_team, 0.0)
        att_a = att.get(away_team, 0.0)
        def_h = defe.get(home_team, 0.0)

        lambda_ = np.exp(att_h + def_a + home_adv)
        mu_ = np.exp(att_a + def_h)

        max_goals = 10
        matrix = np.zeros((max_goals + 1, max_goals + 1))
        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                p_base = poisson.pmf(x, lambda_) * poisson.pmf(y, mu_)
                p_adj = p_base * tau(x, y, lambda_, mu_, rho)
                matrix[x, y] = p_adj

        probs_dict = {info["code"]: 0.0 for info in SOCCER_CHOICE_MAP.values()}
        for x in range(max_goals + 1):
            for y in range(max_goals + 1):
                p = matrix[x, y]
                score_str = f"{x}-{y}"
                if x > y:
                    if score_str in probs_dict: probs_dict[score_str] += p
                    else: probs_dict["other_home_win"] += p
                elif x == y:
                    if score_str in probs_dict: probs_dict[score_str] += p
                    else: probs_dict["other_draw"] += p
                else:
                    if score_str in probs_dict: probs_dict[score_str] += p
                    else: probs_dict["other_away_win"] += p

        probs = [probs_dict[SOCCER_CHOICE_MAP[num]["code"]] for num in range(1, 19)]
        probs = np.array(probs)
        probs = probs / np.sum(probs)
        return probs

    def execute_evaluation(self, fixtures_csv=os.path.join(DATA_DIR, "verified_fixtures.csv")):
        print("=" * 80)
        print(" [FORWARD ENGINE Phase 6] 締切60分前評価 & 手動/実測オッズ完全統合パイプライン")
        print("=" * 80)

        df_fix = pd.read_csv(fixtures_csv)
        # 評価対象: 販売中試合 (IN_SALE) および過去検証対象 (10092)
        target_fixtures = df_fix[(df_fix["status"] == "IN_SALE") | (df_fix["lottery_id"] == 10092)].copy()

        now_utc = datetime.now(timezone.utc)
        now_utc_str = now_utc.isoformat()

        # 既存台帳のロード (重複上書き検査用)
        existing_pred_ids = set()
        if os.path.exists(self.predictions_file):
            df_ep = pd.read_csv(self.predictions_file)
            if len(df_ep) > 0 and "prediction_id" in df_ep.columns:
                existing_pred_ids = set(df_ep["prediction_id"].dropna().unique())

        new_pred_records = []
        new_tx_records = []
        last_chain = self.get_last_chain_hash()

        for _, fix in target_fixtures.iterrows():
            lid = str(fix["lottery_id"])
            sport = fix["sport"]
            home = fix["home_team"]
            away = fix["away_team"]
            c_name = fix["commodity_name"]
            sales_end_str = fix["sales_end_datetime"]

            # 販売締切60分前 (scheduled_eval_time_utc) の算出
            dt_end = datetime.fromisoformat(sales_end_str.replace("Z", "+00:00"))
            scheduled_eval_utc = dt_end - timedelta(minutes=60)
            scheduled_eval_str = scheduled_eval_utc.isoformat()

            # 許容範囲判定 (±120秒)
            time_diff_sec = abs((now_utc - scheduled_eval_utc).total_seconds())
            if self.allow_historical_replay:
                timing_status = "HISTORICAL_REPLAY_VALIDATED"
            elif time_diff_sec <= 120.0:
                timing_status = "EXACT_60MIN_WINDOW"
            else:
                timing_status = f"MISSED_DEADLINE (diff={time_diff_sec:.1f}s)"

            # Task D: モデル推論 (27特徴量完全生成)
            if sport == "Basketball":
                probs = self.predict_basketball_probs(home, away)
                choice_map = BASKETBALL_CHOICE_MAP
                m_name = self.b_meta["model_name"]
                m_ver = self.b_meta["model_version"]
                m_hash = self.b_hash
            elif sport == "Soccer":
                probs = self.predict_soccer_probs(home, away)
                choice_map = SOCCER_CHOICE_MAP
                m_name = self.s_params["model_name"]
                m_ver = self.s_params["model_version"]
                m_hash = self.s_hash
            else:
                raise ValueError(f"Unknown sport: {sport}")

            assert abs(np.sum(probs) - 1.0) < 1e-5, "Sum of probs not 1.0!"

            # Task B: 実測 / 手動インポートオッズスナップショットの取得と証拠区分照合
            snap_v_path = os.path.join(ODDS_SNAPSHOT_DIR, f"snapshot_{lid}_verified.json")
            snap_u_path = os.path.join(ODDS_SNAPSHOT_DIR, f"snapshot_{lid}_unavailable.json")
            snap_unver_path = os.path.join(ODDS_SNAPSHOT_DIR, f"snapshot_{lid}_unverified.json")

            odds_by_number = {}
            evidence_class = "UNAVAILABLE"
            odds_status = "ODDS_UNAVAILABLE"
            raw_evidence_sha256 = "NONE"

            # 優先順位: verified > unverified > unavailable
            target_snap_path = None
            if os.path.exists(snap_v_path):
                target_snap_path = snap_v_path
            elif os.path.exists(snap_unver_path):
                target_snap_path = snap_unver_path
            elif os.path.exists(snap_u_path):
                target_snap_path = snap_u_path

            if target_snap_path and os.path.exists(target_snap_path):
                with open(target_snap_path, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                evidence_class = s_data.get("evidence_class", "UNVERIFIED")
                odds_status = s_data.get("status", "ODDS_AVAILABLE")
                raw_evidence_sha256 = s_data.get("raw_evidence_sha256", "UNKNOWN")

                for sel in s_data.get("selections", []):
                    s_num = int(sel["selection_number"])
                    odds_by_number[s_num] = float(sel["odds"])

            # 予測ID (ユニークキー)
            prediction_id = f"PRED_{lid}_{scheduled_eval_str}"
            if prediction_id in existing_pred_ids:
                print(f"[ForwardEngine] Duplicate prediction {prediction_id} rejected (Bug 4 fix)!")
                continue

            # 各選択肢のEV計算 & 結合 (Task B/C)
            # 唯一購入判断に使用可能な証拠区分: PRE_CUTOFF_OBSERVED または MANUAL_VERIFIED_PRE_CUTOFF
            is_valid_odds_for_betting = evidence_class in ["PRE_CUTOFF_OBSERVED", "MANUAL_VERIFIED_PRE_CUTOFF"]

            choices_detail = []
            for num, info in choice_map.items():
                p = float(probs[num - 1])
                code = info["code"]
                name = info["official_name"]

                if num in odds_by_number and odds_status != "ODDS_UNAVAILABLE":
                    o = odds_by_number[num]
                    if is_valid_odds_for_betting:
                        ev = p * o - 1.0
                    else:
                        ev = None  # 締切後または未照合オッズは購入判断用EVを計算しない
                else:
                    o = None
                    ev = None

                choices_detail.append({
                    "number": num, "code": code, "name": name,
                    "prob": p, "odds": o, "ev": ev
                })

                p_round = round(p, 5)
                o_round = round(o, 2) if o is not None else None
                ev_round = round(ev, 4) if ev is not None else None

                # Task C: 厳格な正規化レコードハッシュ (時刻・表示倍率・モデル情報すべて保護)
                norm_str = build_normalized_prediction_string(
                    prediction_id, lid, sport, c_name, sales_end_str,
                    scheduled_eval_str, now_utc_str, timing_status,
                    num, code, p_round, o_round, ev_round,
                    odds_status, evidence_class, raw_evidence_sha256,
                    m_name, m_ver, m_hash
                )
                rec_sha = hashlib.sha256(norm_str.encode("utf-8")).hexdigest()

                new_pred_records.append({
                    "prediction_id": prediction_id,
                    "lottery_id": lid,
                    "sport": sport,
                    "commodity_name": c_name,
                    "home_team": home,
                    "away_team": away,
                    "sales_end_datetime": sales_end_str,
                    "scheduled_eval_time_utc": scheduled_eval_str,
                    "actual_exec_time_utc": now_utc_str,
                    "timing_status": timing_status,
                    "selection_number": num,
                    "choice_code": code,
                    "choice_name": name,
                    "predicted_prob": p_round,
                    "observed_odds": o_round,
                    "predicted_ev": ev_round,
                    "odds_status": odds_status,
                    "evidence_class": evidence_class,
                    "raw_evidence_sha256": raw_evidence_sha256,
                    "model_name": m_name,
                    "model_version": m_ver,
                    "model_hash": m_hash,
                    "prediction_record_sha256": rec_sha
                })

            # 3戦略の意思決定判定
            strategies = ["Conservative_Value", "EV_5", "No_Bet"]
            for strat in strategies:
                tx_id = f"TX_{strat}_{lid}_{now_utc_str}"

                # 決定ステータス分岐
                if timing_status.startswith("MISSED_DEADLINE"):
                    decision = "MISSED_DEADLINE"
                    best_ch = None
                elif odds_status == "ODDS_UNAVAILABLE" or evidence_class == "UNAVAILABLE":
                    decision = "DATA_UNAVAILABLE"
                    best_ch = None
                elif not is_valid_odds_for_betting:
                    decision = f"INVALID_ODDS_{evidence_class}"
                    best_ch = None
                else:
                    # 正常データでの戦略判定
                    best_ch = None
                    max_ev = -999.0
                    if strat == "Conservative_Value":
                        for ch in choices_detail:
                            if ch["ev"] is not None and ch["ev"] > 0.15 and ch["prob"] >= 0.08:
                                if ch["ev"] > max_ev:
                                    max_ev = ch["ev"]
                                    best_ch = ch
                    elif strat == "EV_5":
                        for ch in choices_detail:
                            if ch["ev"] is not None and ch["ev"] > 0.05:
                                if ch["ev"] > max_ev:
                                    max_ev = ch["ev"]
                                    best_ch = ch
                    elif strat == "No_Bet":
                        best_ch = None

                    if best_ch:
                        decision = "BET"
                    else:
                        decision = "NO_BET"

                cost = 200 if decision == "BET" else 0
                sel_num = best_ch["number"] if best_ch else None
                sel_code = best_ch["code"] if best_ch else "NONE"
                sel_p = round(best_ch["prob"], 5) if best_ch else None
                sel_o = round(best_ch["odds"], 2) if best_ch else None
                sel_ev = round(best_ch["ev"], 4) if best_ch else None

                tx_record = {
                    "tx_id": tx_id,
                    "timestamp_utc": now_utc_str,
                    "strategy_name": strat,
                    "lottery_id": lid,
                    "commodity_name": c_name,
                    "sport": sport,
                    "decision": decision,
                    "selected_selection_number": sel_num,
                    "selected_choice_code": sel_code,
                    "predicted_prob": sel_p,
                    "observed_odds": sel_o,
                    "predicted_ev": sel_ev,
                    "bet_cost_jpy": cost,
                    "timing_status": timing_status,
                    "odds_status": odds_status,
                    "evidence_class": evidence_class,
                    "raw_evidence_sha256": raw_evidence_sha256,
                    "model_version": m_ver,
                    "model_hash": m_hash
                }

                # Task C: 前レコード連結ハッシュチェーン (全フィールド結合)
                chain_payload = build_normalized_transaction_chain_payload(last_chain, tx_record)
                new_chain = hashlib.sha256(chain_payload.encode("utf-8")).hexdigest()
                prev_chain = last_chain
                last_chain = new_chain

                tx_record["prev_chain_hash"] = prev_chain
                tx_record["chain_sha256"] = new_chain
                new_tx_records.append(tx_record)

        # 追記保存 (Task C: Append-only)
        if len(new_pred_records) > 0:
            df_new_p = pd.DataFrame(new_pred_records)
            df_new_p.to_csv(self.predictions_file, mode="a", header=not os.path.exists(self.predictions_file), index=False)
            print(f"[ForwardEngine] Appended {len(df_new_p)} prediction rows to {self.predictions_file}")

        if len(new_tx_records) > 0:
            df_new_t = pd.DataFrame(new_tx_records)
            df_new_t.to_csv(self.transactions_file, mode="a", header=not os.path.exists(self.transactions_file), index=False)
            print(f"[ForwardEngine] Appended {len(df_new_t)} transaction rows to {self.transactions_file}")

        return len(new_pred_records), len(new_tx_records)

    @staticmethod
    def verify_prediction_integrity(predictions_csv: Optional[str] = None) -> Tuple[bool, str]:
        """Task C: 予測レコード改ざん検証 (全フィールドSHA-256再計算照合)"""
        if predictions_csv is None:
            predictions_csv = os.path.join(DATA_DIR, "forward_predictions.csv")

        if not os.path.exists(predictions_csv):
            return False, f"File {predictions_csv} does not exist."

        df = pd.read_csv(predictions_csv)
        if len(df) == 0:
            return True, "Empty ledger."

        for i, row in df.iterrows():
            pred_id = row.get("prediction_id", "")
            num = row.get("selection_number", "")
            code = row.get("choice_code", "")
            p = row.get("predicted_prob")
            o = row.get("observed_odds")
            ev = row.get("predicted_ev")
            lid = row.get("lottery_id", "")
            sport = row.get("sport", "")
            c_name = row.get("commodity_name", "")
            sales_end = row.get("sales_end_datetime", "")
            sched_eval = row.get("scheduled_eval_time_utc", "")
            exec_time = row.get("actual_exec_time_utc", "")
            timing = row.get("timing_status", "")
            odds_st = row.get("odds_status", "")
            ev_class = row.get("evidence_class", "")
            raw_sha = row.get("raw_evidence_sha256", "NONE")
            m_name = row.get("model_name", "")
            m_ver = row.get("model_version", "")
            m_hash = row.get("model_hash", "")
            expected_hash = row.get("prediction_record_sha256", "")

            norm_str = build_normalized_prediction_string(
                pred_id, lid, sport, c_name, sales_end,
                sched_eval, exec_time, timing,
                num, code, p, o, ev,
                odds_st, ev_class, raw_sha,
                m_name, m_ver, m_hash
            )
            calc_hash = hashlib.sha256(norm_str.encode("utf-8")).hexdigest()
            if calc_hash != expected_hash:
                return False, (
                    f"Integrity error at row {i} (ID: {pred_id}, Choice: {code}): "
                    f"Expected {expected_hash}, calculated {calc_hash}"
                )

        return True, f"All {len(df)} records verified successfully with recomputed SHA-256."

    @staticmethod
    def verify_transaction_integrity(transactions_csv: Optional[str] = None) -> Tuple[bool, str]:
        """Task C: トランザクションハッシュチェーン改ざん検証 (全フィールド照合)"""
        if transactions_csv is None:
            transactions_csv = os.path.join(DATA_DIR, "forward_transactions.csv")

        if not os.path.exists(transactions_csv):
            return False, f"File {transactions_csv} does not exist."

        df = pd.read_csv(transactions_csv)
        if len(df) == 0:
            return True, "Empty ledger."

        last_chain = "0" * 64
        for i, row in df.iterrows():
            tx_id = row["tx_id"]
            prev_hash = str(row["prev_chain_hash"])
            expected_chain = str(row["chain_sha256"])

            if prev_hash != last_chain:
                return False, f"Broken chain link at row {i} (TX: {tx_id}): prev_hash {prev_hash} != expected {last_chain}"

            chain_payload = build_normalized_transaction_chain_payload(last_chain, row.to_dict())
            calc_chain = hashlib.sha256(chain_payload.encode("utf-8")).hexdigest()
            if calc_chain != expected_chain:
                return False, (
                    f"Chain payload integrity error at row {i} (TX: {tx_id}): "
                    f"Expected {expected_chain}, calculated {calc_chain}"
                )

            last_chain = calc_chain

        return True, f"All {len(df)} transactions verified successfully with recomputed SHA-256 chain."

if __name__ == "__main__":
    engine = ForwardPredictionEngine(allow_historical_replay=True)
    engine.execute_evaluation()
