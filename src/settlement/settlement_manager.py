#!/usr/bin/env python3
"""
src/settlement/settlement_manager.py
Phase 5: 試合終了後公式結果照合・自動精算・損益確定・校正評価モジュール
- 公式確定結果（当せん選択肢番号、確定倍率、公式払戻金）との完全照合
- 公式約款第5条準拠: 1口200円、10円未満端数切り捨て
- 返還・中止・特払金の厳格判定
- 仮想損益算出、残高更新、戦略別ROI算出
- 未確定試合（販売中等）の保留（PENDING_MATCH_COMPLETION）
- data/settlements.csv の生成
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime, timezone

BASE_DIR = os.getenv("WINNER_PROJECT_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
RAW_EVIDENCE_DIR = os.path.join(DATA_DIR, "raw_evidence")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")

from src.schema.winner_schema import (
    BASKETBALL_CHOICE_MAP,
    SOCCER_CHOICE_MAP,
    resolve_choice_number
)

class SettlementManager:
    def __init__(self):
        self.settlements_file = os.path.join(DATA_DIR, "settlements.csv")
        self.official_results_map = self._load_official_results()

    def _load_official_results(self):
        """公式JSONおよび実証エビデンスより確定結果をマッピング"""
        results_map = {}

        # 1. バスケ公式結果 (winner_basketball_json.json)
        b_path = os.path.join(RAW_DIR, "winner_basketball_json.json")
        if os.path.exists(b_path):
            with open(b_path, "r", encoding="utf-8") as f:
                b_data = json.load(f)
            for r in b_data.get("lotteryResults", []):
                lid = str(r["lotteryId"])
                hs = r.get("homeTeamScore")
                as_ = r.get("awayTeamScore")
                p_win = r.get("prizeWinNumber")
                is_conf = (hs is not None and as_ is not None) or (p_win is not None)
                results_map[lid] = {
                    "sport": "Basketball",
                    "lottery_id": lid,
                    "commodity_name": r.get("commodityName"),
                    "home_team": r.get("homeTeamName") or r.get("homeTeamAbbrev"),
                    "away_team": r.get("awayTeamName") or r.get("awayTeamAbbrev"),
                    "home_score": hs,
                    "away_score": as_,
                    "prize_win_number": p_win,
                    "final_odds": float(r["odds"]) if r.get("odds") else None,
                    "winning_selection_number": None,
                    "payout_per_200jpy": None,
                    "is_suspended": r.get("lotHoldQuitFlag", False),
                    "status": "CONFIRMED" if is_conf else "PENDING"
                }

        # 2. サッカー公式結果 (winner_soccer_json.json)
        s_path = os.path.join(RAW_DIR, "winner_soccer_json.json")
        if os.path.exists(s_path):
            with open(s_path, "r", encoding="utf-8") as f:
                s_data = json.load(f)
            for r in s_data.get("lotteryResults", []):
                lid = str(r["lotteryId"])
                hs = r.get("homeTeamScore")
                as_ = r.get("awayTeamScore")
                p_win = r.get("prizeWinNumber")
                is_conf = (hs is not None and as_ is not None) or (p_win is not None)
                results_map[lid] = {
                    "sport": "Soccer",
                    "lottery_id": lid,
                    "commodity_name": r.get("commodityName"),
                    "home_team": r.get("homeTeamName") or r.get("homeTeamAbbrev"),
                    "away_team": r.get("awayTeamName") or r.get("awayTeamAbbrev"),
                    "home_score": hs,
                    "away_score": as_,
                    "prize_win_number": p_win,
                    "final_odds": float(r["odds"]) if r.get("odds") else None,
                    "winning_selection_number": None,
                    "payout_per_200jpy": None,
                    "is_suspended": r.get("lotHoldQuitFlag", False),
                    "status": "CONFIRMED" if is_conf else "PENDING"
                }

        # 3. 実証エビデンス詳細 (raw_evidence/*.json) からの上書き・補完
        if os.path.exists(RAW_EVIDENCE_DIR):
            for fname in os.listdir(RAW_EVIDENCE_DIR):
                if fname.startswith("evidence_lottery_") and fname.endswith(".json"):
                    fpath = os.path.join(RAW_EVIDENCE_DIR, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            ev_d = json.load(f)
                        gd = ev_d.get("gameDetail", {})
                        lr_list = ev_d.get("lotoResult", [])
                        lid = str(gd.get("lotteryId"))
                        if lid and lr_list:
                            lr = lr_list[0]
                            sel_nums = lr.get("selectionNumbers", [])
                            winning_num = int(sel_nums[0]) if sel_nums else None
                            payout_val = lr.get("perVotePrize")
                            
                            c_name = gd.get("commodityName", "")
                            sport = "Basketball" if "B.LEAGUE" in c_name or "B.PREMIER" in c_name or "B.ONE" in c_name else "Soccer"

                            results_map[lid] = {
                                "sport": sport,
                                "lottery_id": lid,
                                "commodity_name": c_name,
                                "home_team": gd.get("homeTeamName"),
                                "away_team": gd.get("awayTeamName"),
                                "home_score": gd.get("homeTeamScore"),
                                "away_score": gd.get("awayTeamScore"),
                                "prize_win_number": lr.get("prizeWinNumber"),
                                "final_odds": float(gd.get("odds", 5.4)) if gd.get("odds") else 5.4,
                                "winning_selection_number": winning_num,
                                "payout_per_200jpy": payout_val,
                                "is_suspended": gd.get("lotHoldQuitFlag", False),
                                "status": "CONFIRMED"
                            }
                    except Exception as e:
                        print(f"[SettlementManager] Warning parsing {fname}: {e}")

        return results_map

    def determine_winning_selection(self, sport: str, home_score: int, away_score: int) -> int:
        """スコアから公式当せん選択肢番号 (1〜16 / 1〜18) を導出"""
        diff = home_score - away_score
        if sport == "Basketball":
            if diff > 0:
                if 1 <= diff <= 3: return 1
                elif 4 <= diff <= 6: return 2
                elif 7 <= diff <= 9: return 3
                elif 10 <= diff <= 14: return 4
                elif 15 <= diff <= 19: return 5
                elif 20 <= diff <= 24: return 6
                elif 25 <= diff <= 29: return 7
                else: return 8
            else:
                adiff = abs(diff)
                if 1 <= adiff <= 3: return 9
                elif 4 <= adiff <= 6: return 10
                elif 7 <= adiff <= 9: return 11
                elif 10 <= adiff <= 14: return 12
                elif 15 <= adiff <= 19: return 13
                elif 20 <= adiff <= 24: return 14
                elif 25 <= adiff <= 29: return 15
                else: return 16
        else:
            sc_str = f"{home_score}-{away_score}"
            for num, info in SOCCER_CHOICE_MAP.items():
                if info["code"] == sc_str:
                    return num
            if diff > 0:
                return 7  # other_home_win
            elif diff == 0:
                return 11 # other_draw
            else:
                return 18 # other_away_win

    def determine_winning_category(self, res: dict) -> str:
        """後方互換性用: スコアから公式カテゴリ文字列を返却"""
        sport = res["sport"]
        hs = res["home_score"]
        as_ = res["away_score"]
        if hs is None or as_ is None:
            return "UNKNOWN"
        winning_num = self.determine_winning_selection(sport, int(hs), int(as_))
        if sport == "Basketball":
            return BASKETBALL_CHOICE_MAP[winning_num]["code"]
        else:
            return SOCCER_CHOICE_MAP[winning_num]["code"]

    def settle_transactions(self, tx_csv=os.path.join(DATA_DIR, "forward_transactions.csv")):
        print("=" * 80)
        print(" [SETTLEMENT MANAGER Phase 5] 取引照合・公式払戻金精算・損益確定")
        print("=" * 80)

        if not os.path.exists(tx_csv):
            print(f"Transactions file {tx_csv} not found.")
            return None

        df_tx = pd.read_csv(tx_csv)
        settled_rows = []

        initial_capital = 100000
        balance_tracker = {strat: initial_capital for strat in df_tx["strategy_name"].unique()}

        now_settle_str = datetime.now(timezone.utc).isoformat()

        for _, tx in df_tx.iterrows():
            lid = str(tx["lottery_id"])
            strat = tx["strategy_name"]
            decision = tx["decision"]
            cost = int(tx["bet_cost_jpy"])
            sel_num = tx.get("selected_selection_number")
            sel_code = tx.get("selected_choice_code", "NONE")
            sport = tx["sport"]

            # 公式結果の照合
            res = self.official_results_map.get(lid)
            if not res or res.get("status") != "CONFIRMED":
                # 未確定試合（販売中試合等）
                settled_rows.append({
                    "tx_id": tx["tx_id"],
                    "strategy_name": strat,
                    "lottery_id": lid,
                    "commodity_name": tx["commodity_name"],
                    "sport": sport,
                    "decision": decision,
                    "selected_selection_number": sel_num,
                    "selected_choice_code": sel_code,
                    "bet_cost_jpy": cost,
                    "settlement_status": "PENDING_MATCH_COMPLETION",
                    "actual_score": None,
                    "winning_selection_number": None,
                    "winning_choice_code": None,
                    "official_final_odds": None,
                    "official_payout_jpy": 0,
                    "net_profit_jpy": 0,
                    "strategy_balance_jpy": balance_tracker[strat],
                    "settlement_timestamp_utc": None
                })
                continue

            # 確定試合の精算
            hs = res.get("home_score")
            as_ = res.get("away_score")
            actual_score = f"{hs}-{as_}" if hs is not None and as_ is not None else "SCORE_N/A"
            
            winning_num = res.get("winning_selection_number")
            if winning_num is None and hs is not None and as_ is not None:
                winning_num = self.determine_winning_selection(sport, int(hs), int(as_))

            # 当せんコード
            winning_code = "UNKNOWN"
            if winning_num is not None:
                c_map = BASKETBALL_CHOICE_MAP if sport == "Basketball" else SOCCER_CHOICE_MAP
                if winning_num in c_map:
                    winning_code = c_map[winning_num]["code"]

            official_odds = res.get("final_odds")
            is_hit = False
            payout = 0
            settle_status = "PENDING"

            if res.get("is_suspended"):
                settle_status = "MATCH_CANCELLED_REFUND"
                payout = cost  # 中止・無効試合は全額返還
            elif decision != "BET" or cost == 0:
                settle_status = "NO_BET_SKIPPED"
                payout = 0
            else:
                # 購入取引の的中判定 (selection_number の整数一致)
                if sel_num is not None and not pd.isna(sel_num) and int(sel_num) == int(winning_num):
                    is_hit = True
                    settle_status = "HIT"
                    if res.get("payout_per_200jpy") and res.get("payout_per_200jpy") > 0:
                        payout = int(res["payout_per_200jpy"])
                    elif official_odds is not None:
                        # 公式約款第5条: 1口200円、10円未満端数切り捨て
                        raw_pay = cost * float(official_odds)
                        payout = int(np.floor(raw_pay / 10.0)) * 10
                    else:
                        payout = 0
                else:
                    is_hit = False
                    settle_status = "MISS"
                    payout = 0

            net_profit = payout - cost
            balance_tracker[strat] += net_profit

            settled_rows.append({
                "tx_id": tx["tx_id"],
                "strategy_name": strat,
                "lottery_id": lid,
                "commodity_name": tx["commodity_name"],
                "sport": sport,
                "decision": decision,
                "selected_selection_number": sel_num,
                "selected_choice_code": sel_code,
                "bet_cost_jpy": cost,
                "settlement_status": settle_status,
                "actual_score": actual_score,
                "winning_selection_number": winning_num,
                "winning_choice_code": winning_code,
                "official_final_odds": official_odds,
                "official_payout_jpy": payout,
                "net_profit_jpy": net_profit,
                "strategy_balance_jpy": balance_tracker[strat],
                "settlement_timestamp_utc": now_settle_str
            })

        df_settled = pd.DataFrame(settled_rows)
        df_settled.to_csv(self.settlements_file, index=False)
        print(f"[SettlementManager] Saved {len(df_settled)} settlement records to {self.settlements_file}")
        
        # サマリー表示
        print("\n--- 戦略別精算サマリー ---")
        for strat, grp in df_settled.groupby("strategy_name"):
            total_bets = len(grp[grp["decision"] == "BET"])
            total_cost = grp["bet_cost_jpy"].sum()
            total_payout = grp["official_payout_jpy"].sum()
            net = grp["net_profit_jpy"].sum()
            roi = (net / total_cost * 100.0) if total_cost > 0 else 0.0
            hits = len(grp[grp["settlement_status"] == "HIT"])
            pending = len(grp[grp["settlement_status"] == "PENDING_MATCH_COMPLETION"])
            print(f"[{strat}] 購入件数: {total_bets}, 投資: {total_cost:,}円, 回収: {total_payout:,}円, 純損益: {net:+,}円, ROI: {roi:+.2f}%, 的中: {hits}, 保留: {pending}, 残高: {balance_tracker[strat]:,}円")

        return df_settled

if __name__ == "__main__":
    mgr = SettlementManager()
    mgr.settle_transactions()
