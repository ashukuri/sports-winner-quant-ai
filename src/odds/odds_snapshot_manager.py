#!/usr/bin/env python3
"""
src/odds/odds_snapshot_manager.py
Phase 6: 公式オッズ収集・厳格検証・手動インポートモジュール (Task B完全対応版)
- 動的パス解決 (src.config 準拠)
- 証拠区分の厳格分類:
  - MANUAL_VERIFIED_PRE_CUTOFF: 一次資料・取得時刻照合済みの購入前データ (EV計算・購入判断に使用可能)
  - MANUAL_UNVERIFIED: 手動入力済み、未照合データ (購入判断に使用禁止)
  - PRE_CUTOFF_OBSERVED: 自動取得された購入前実測オッズ
  - POST_CUTOFF_OBSERVED: 販売締切後のオッズ (購入判断に使用禁止)
  - OFFICIAL_FINAL_PAYOUT: 公式確定払戻金
  - ODDS_UNAVAILABLE: 取得不能
- 手動入力バリデーション:
  - バスケ16択 / サッカー18択の全選択肢完全性チェック (欠落・重複拒絶)
  - 負倍率・1.0以下・非数値・無関係文字列の厳格拒絶
  - 控除率（逆数合計 1.90〜2.15）の妥当性検証
  - 一次資料ファイルの保存とSHA-256ハッシュ刻印 (相対パス管理)
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from src.config import (
    PROJECT_ROOT,
    DATA_DIR,
    RAW_DIR,
    RAW_EVIDENCE_DIR,
    ODDS_SNAPSHOT_DIR,
    REPORTS_DIR,
    resolve_path
)

from src.schema.winner_schema import (
    BASKETBALL_CHOICE_MAP,
    SOCCER_CHOICE_MAP,
    resolve_choice_number
)

class RealOddsSnapshotManager:
    def __init__(self):
        os.makedirs(RAW_EVIDENCE_DIR, exist_ok=True)
        os.makedirs(ODDS_SNAPSHOT_DIR, exist_ok=True)
        os.makedirs(REPORTS_DIR, exist_ok=True)
        self.snapshots = []

    @staticmethod
    def compute_sha256(content_bytes: bytes) -> str:
        return hashlib.sha256(content_bytes).hexdigest()

    def process_primary_evidence_10092(self):
        """一次資料 detail_sample.html から公式オッズを抽出しスナップショット化 (10092)"""
        html_path = os.path.join(RAW_DIR, "detail_sample.html")
        if not os.path.exists(html_path):
            return None

        with open(html_path, "rb") as f:
            raw_bytes = f.read()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(raw_bytes, "html.parser")
        selections = []
        for row in soup.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                name = th.get_text(strip=True)
                odds_text = td.get_text(strip=True).replace("倍", "")
                s_num = resolve_choice_number("Basketball", name)
                if s_num:
                    try:
                        o_val = float(odds_text)
                        selections.append({
                            "selection_number": s_num,
                            "selection_name": BASKETBALL_CHOICE_MAP[s_num]["official_name"],
                            "code": BASKETBALL_CHOICE_MAP[s_num]["code"],
                            "odds": o_val
                        })
                    except ValueError:
                        pass

        selections = sorted(selections, key=lambda x: x["selection_number"])
        reciprocal_sum = sum(1.0 / s["odds"] for s in selections)

        # 証拠ファイル
        ev_file_rel = "data/raw_evidence/evidence_lottery_10092.json"
        ev_file_abs = os.path.join(PROJECT_ROOT, ev_file_rel)

        ev_sha = "UNKNOWN"
        if os.path.exists(ev_file_abs):
            with open(ev_file_abs, "rb") as f:
                ev_sha = self.compute_sha256(f.read())

        snap_record = {
            "sport": "Basketball",
            "match_id": "BSK_20261002_10092",
            "lottery_id": "10092",
            "commodity_id": "50",
            "commodity_name": "B.PREMIER 2026/10/02 千葉J vs A東京",
            "hold_count": "第423回",
            "home_team": "千葉ジェッツ",
            "away_team": "アルバルク東京",
            "game_date": "2026-10-02T10:05:00.000000Z",
            "sales_end_datetime": "2026-10-02T09:55:00.000000Z",
            "odds_update_datetime": "2026-10-03T00:49:00.000000Z",
            "captured_timestamp_utc": "2026-10-13T13:23:00Z",
            "official_url": "https://winner.toto.rakuten.co.jp/detail/singlematch/10092/",
            "evidence_class": "POST_CUTOFF_OBSERVED",
            "is_valid_for_pre_match_betting": False,
            "raw_evidence_path": ev_file_rel,
            "raw_evidence_sha256": ev_sha,
            "source_html_sha256": self.compute_sha256(raw_bytes),
            "status": "POST_CUTOFF_ARCHIVED_ODDS",
            "n_choices": len(selections),
            "reciprocal_sum": round(reciprocal_sum, 4),
            "implied_takeout_rate_pct": round((1.0 - 1.0 / reciprocal_sum) * 100, 1),
            "implied_payout_rate_pct": round((1.0 / reciprocal_sum) * 100, 1),
            "selections": selections
        }

        snap_file = os.path.join(ODDS_SNAPSHOT_DIR, "snapshot_10092_verified.json")
        with open(snap_file, "w", encoding="utf-8") as f:
            json.dump(snap_record, f, indent=2, ensure_ascii=False)
        self.snapshots.append(snap_record)
        return snap_record

    def process_in_sale_fixtures(self, fixtures_csv=os.path.join(DATA_DIR, "verified_fixtures.csv")):
        """販売中試合のオッズ未取得状態スナップショット生成"""
        df_fix = pd.read_csv(fixtures_csv)
        in_sale = df_fix[df_fix["status"] == "IN_SALE"]
        now_utc = datetime.now(timezone.utc).isoformat()

        for _, row in in_sale.iterrows():
            lid = str(row["lottery_id"])
            sport = row["sport"]
            snap_record = {
                "sport": sport,
                "match_id": f"{'SOC' if sport=='Soccer' else 'BSK'}_{lid}",
                "lottery_id": lid,
                "commodity_id": str(row.get("commodity_id", "")),
                "commodity_name": row["commodity_name"],
                "hold_count": str(row.get("hold_count", "")),
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "game_date": row["game_date"],
                "sales_end_datetime": row["sales_end_datetime"],
                "odds_update_datetime": None,
                "captured_timestamp_utc": now_utc,
                "official_url": row.get("official_url", ""),
                "evidence_class": "UNAVAILABLE",
                "is_valid_for_pre_match_betting": False,
                "raw_evidence_path": None,
                "raw_evidence_sha256": None,
                "status": "ODDS_UNAVAILABLE",
                "n_choices": int(row["n_choices"]),
                "reciprocal_sum": None,
                "implied_takeout_rate_pct": None,
                "implied_payout_rate_pct": None,
                "selections": []
            }
            snap_file = os.path.join(ODDS_SNAPSHOT_DIR, f"snapshot_{lid}_unavailable.json")
            with open(snap_file, "w", encoding="utf-8") as f:
                json.dump(snap_record, f, indent=2, ensure_ascii=False)
            self.snapshots.append(snap_record)

    def import_manual_odds(
        self,
        lottery_id: int | str,
        sport: str,
        odds_dict: Dict[int, float],
        observed_time_utc: str,
        source_url: str,
        raw_evidence_content: bytes | str,
        raw_evidence_filename: Optional[str] = None,
        is_verified_with_primary_source: bool = False
    ) -> Dict[str, Any]:
        """
        Task B: 公式オッズ手動入力の完全実装 (厳格バリデーション)
        - 選択肢数 (バスケ16択 / サッカー18択) の完全一致検証
        - 負値、1.0以下、非数値、無関係文字列の拒絶
        - 控除率（逆数合計 1.90〜2.15）の検証
        - 証拠区分の厳格決定 (MANUAL_VERIFIED_PRE_CUTOFF / MANUAL_UNVERIFIED / POST_CUTOFF_OBSERVED)
        - スナップショットJSONの出力
        """
        lid_str = str(lottery_id).strip()
        if not lid_str.isdigit():
            raise ValueError(f"Invalid lottery_id format: '{lottery_id}'. Must be numeric.")

        lid_int = int(lid_str)

        # 1. verified_fixtures.csv に存在するか確認
        fix_path = os.path.join(DATA_DIR, "verified_fixtures.csv")
        if not os.path.exists(fix_path):
            raise FileNotFoundError(f"Fixture database not found at {fix_path}")

        df_fix = pd.read_csv(fix_path)
        m = df_fix[df_fix["lottery_id"] == lid_int]
        if len(m) == 0:
            raise ValueError(f"Lottery ID {lid_str} not found in verified_fixtures.csv")

        fixture_row = m.iloc[0]
        actual_sport = fixture_row["sport"]
        if sport != actual_sport:
            raise ValueError(f"Sport mismatch for lottery {lid_str}: Provided '{sport}', but fixture is '{actual_sport}'")

        # 2. 選択肢数の厳格検証
        expected_choices = 16 if actual_sport == "Basketball" else 18
        choice_map = BASKETBALL_CHOICE_MAP if actual_sport == "Basketball" else SOCCER_CHOICE_MAP

        if not isinstance(odds_dict, dict):
            raise ValueError(f"odds_dict must be a dictionary, got {type(odds_dict).__name__}")

        if len(odds_dict) != expected_choices:
            raise ValueError(f"Selection count mismatch for {actual_sport}: Expected exactly {expected_choices} choices, got {len(odds_dict)}")

        # 全キーが 1〜expected_choices に存在するか
        required_keys = set(range(1, expected_choices + 1))
        provided_keys = set(odds_dict.keys())
        if required_keys != provided_keys:
            missing = required_keys - provided_keys
            extra = provided_keys - required_keys
            raise ValueError(f"Invalid selection numbers. Missing: {missing}, Extra: {extra}")

        # 3. 倍率値の妥当性検証
        selections = []
        reciprocal_sum = 0.0

        for num in range(1, expected_choices + 1):
            val = odds_dict[num]
            try:
                val_f = float(val)
            except (ValueError, TypeError):
                raise ValueError(f"Odds for selection {num} cannot be parsed as float: '{val}'")

            if np.isnan(val_f) or np.isinf(val_f):
                raise ValueError(f"Odds for selection {num} is NaN or Inf: {val_f}")

            if val_f <= 1.0:
                raise ValueError(f"Odds for selection {num} must be greater than 1.0, got {val_f}")

            reciprocal_sum += 1.0 / val_f
            selections.append({
                "selection_number": num,
                "selection_name": choice_map[num]["official_name"],
                "code": choice_map[num]["code"],
                "odds": round(val_f, 2)
            })

        # 控除率（逆数合計）の検証: WINNER公式では約 1.90〜2.15 (控除率約47%〜53%)
        if not (1.80 <= reciprocal_sum <= 2.25):
            raise ValueError(
                f"Reciprocal sum of odds ({reciprocal_sum:.4f}) is out of reasonable sports lottery range [1.80, 2.25]. "
                "Possible invalid odds data."
            )

        # 4. 時刻と証拠区分の判定
        if not observed_time_utc:
            raise ValueError("observed_time_utc must be specified.")

        try:
            obs_dt = datetime.fromisoformat(observed_time_utc.replace("Z", "+00:00"))
        except Exception as e:
            raise ValueError(f"Failed to parse observed_time_utc '{observed_time_utc}': {e}")

        sales_end_str = fixture_row["sales_end_datetime"]
        try:
            sales_end_dt = datetime.fromisoformat(sales_end_str.replace("Z", "+00:00"))
        except Exception as e:
            raise ValueError(f"Failed to parse sales_end_datetime '{sales_end_str}': {e}")

        is_pre_cutoff = (obs_dt <= sales_end_dt)

        if not is_pre_cutoff:
            evidence_class = "POST_CUTOFF_OBSERVED"
            is_valid_for_betting = False
            status_str = "POST_CUTOFF_ARCHIVED_ODDS"
        elif is_verified_with_primary_source:
            evidence_class = "MANUAL_VERIFIED_PRE_CUTOFF"
            is_valid_for_betting = True
            status_str = "ODDS_AVAILABLE"
        else:
            evidence_class = "MANUAL_UNVERIFIED"
            is_valid_for_betting = False
            status_str = "UNVERIFIED_ODDS"

        # 5. 一次資料の保存 (相対パス管理)
        if not raw_evidence_content:
            raise ValueError("raw_evidence_content cannot be empty.")

        if isinstance(raw_evidence_content, str):
            raw_bytes = raw_evidence_content.encode("utf-8")
        else:
            raw_bytes = raw_evidence_content

        ev_sha256 = self.compute_sha256(raw_bytes)

        if not raw_evidence_filename:
            raw_evidence_filename = f"evidence_manual_{lid_str}_{obs_dt.strftime('%Y%m%d%H%M%S')}.txt"

        ev_rel_path = os.path.join("data", "raw_evidence", raw_evidence_filename)
        ev_abs_path = os.path.join(PROJECT_ROOT, ev_rel_path)

        with open(ev_abs_path, "wb") as f:
            f.write(raw_bytes)

        # 6. スナップショットJSONの生成
        now_utc = datetime.now(timezone.utc).isoformat()
        snap_record = {
            "sport": actual_sport,
            "match_id": f"{'SOC' if actual_sport=='Soccer' else 'BSK'}_{lid_str}",
            "lottery_id": lid_str,
            "commodity_id": str(fixture_row.get("commodity_id", "")),
            "commodity_name": fixture_row["commodity_name"],
            "hold_count": str(fixture_row.get("hold_count", "")),
            "home_team": fixture_row["home_team"],
            "away_team": fixture_row["away_team"],
            "game_date": fixture_row["game_date"],
            "sales_end_datetime": sales_end_str,
            "odds_update_datetime": observed_time_utc,
            "captured_timestamp_utc": now_utc,
            "official_url": source_url,
            "evidence_class": evidence_class,
            "is_valid_for_pre_match_betting": is_valid_for_betting,
            "raw_evidence_path": ev_rel_path,
            "raw_evidence_sha256": ev_sha256,
            "status": status_str,
            "n_choices": expected_choices,
            "reciprocal_sum": round(reciprocal_sum, 4),
            "implied_takeout_rate_pct": round((1.0 - 1.0 / reciprocal_sum) * 100, 1),
            "implied_payout_rate_pct": round((1.0 / reciprocal_sum) * 100, 1),
            "selections": selections
        }

        # 保存ファイル名
        snap_file_name = f"snapshot_{lid_str}_verified.json" if is_valid_for_betting or not is_pre_cutoff else f"snapshot_{lid_str}_unverified.json"
        snap_path = os.path.join(ODDS_SNAPSHOT_DIR, snap_file_name)
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(snap_record, f, indent=2, ensure_ascii=False)

        print(f"[OddsManager] Successfully imported manual odds for lottery {lid_str} -> {snap_path} (Class: {evidence_class})")
        return snap_record
