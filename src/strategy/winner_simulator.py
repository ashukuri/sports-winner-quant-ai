#!/usr/bin/env python3
"""
src/strategy/winner_simulator.py
WINNER (サッカー1試合予想 18択) の期待値・収益シミュレーションモジュール
各選択肢のモデル推定確率 P(k) と 払戻倍率 Odds(k) を比較し、複数の購入戦略の収益性・ROI・ドローダウンを検証する。
※ 購入前のリアルタイム倍率が存在しないため、確定倍率に基づく事後的理論検証であることを明記。
"""

import numpy as np
import pandas as pd

WINNER_CATEGORIES = [
    "1-0", "2-0", "2-1", "3-0", "3-1", "3-2", "other_home_win",
    "0-0", "1-1", "2-2", "other_draw",
    "0-1", "0-2", "1-2", "0-3", "1-3", "2-3", "other_away_win"
]

class WinnerSimulator:
    def __init__(self, cost_per_bet=200):
        self.cost_per_bet = cost_per_bet

    def simulate_strategies(self, test_df, model_winner_probs, winner_odds_dict=None):
        """
        複数のベッティング戦略を評価
        test_df: 各試合の実際の結果 'winner_category' を含む DataFrame
        model_winner_probs: (N, 18) の各モデル予測確率
        winner_odds_dict: 各試合ごとの18択確定倍率 (存在しない場合は売上・確率に基づく市場逆算倍率)
        """
        n_matches = len(test_df)
        actual_results = test_df['winner_category'].values

        # 倍率データが外部から与えられない場合、市場確率（またはブックメーカーCS）に基づく理論オッズを生成
        # WINNERの控除率は公式ルールで約50%（払戻率50% = 0.50）
        # Odds(k) = 0.50 / P_market(k)
        if winner_odds_dict is None:
            # リーグ実績頻度に基づく市場倍率モデル (控除率50%反映)
            cat_counts = test_df['winner_category'].value_counts()
            market_p = np.array([max(cat_counts.get(c, 5) / len(test_df), 0.01) for c in WINNER_CATEGORIES])
            market_p = market_p / np.sum(market_p)
            base_odds = 0.50 / market_p # パリミュチュエル倍率
        else:
            base_odds = None

        strategies = {
            "No_Bet": {"cost": 0, "payout": 0, "bets": 0, "hits": 0, "history": []},
            "Random_1Bet": {"cost": 0, "payout": 0, "bets": 0, "hits": 0, "history": []},
            "Most_Probable_Top1": {"cost": 0, "payout": 0, "bets": 0, "hits": 0, "history": []},
            "Positive_EV_Only (EV > 0.0)": {"cost": 0, "payout": 0, "bets": 0, "hits": 0, "history": []},
            "Conservative_Value (EV > 0.15 & P >= 0.08)": {"cost": 0, "payout": 0, "bets": 0, "hits": 0, "history": []}
        }

        np.random.seed(42)

        for i in range(n_matches):
            act_cat = actual_results[i]
            probs = model_winner_probs[i] # (18,)
            
            if winner_odds_dict is not None and i in winner_odds_dict:
                odds = winner_odds_dict[i]
            else:
                odds = base_odds

            expected_values = probs * odds - 1.0 # 期待収益率 (EV)

            # 1. No Bet
            strategies["No_Bet"]["history"].append(0)

            # 2. Random 1 Bet
            rand_idx = np.random.randint(0, 18)
            rand_cat = WINNER_CATEGORIES[rand_idx]
            strategies["Random_1Bet"]["cost"] += self.cost_per_bet
            strategies["Random_1Bet"]["bets"] += 1
            if rand_cat == act_cat:
                pay = self.cost_per_bet * odds[rand_idx]
                strategies["Random_1Bet"]["payout"] += pay
                strategies["Random_1Bet"]["hits"] += 1
                strategies["Random_1Bet"]["history"].append(pay - self.cost_per_bet)
            else:
                strategies["Random_1Bet"]["history"].append(-self.cost_per_bet)

            # 3. Most Probable Top 1
            top1_idx = int(np.argmax(probs))
            top1_cat = WINNER_CATEGORIES[top1_idx]
            strategies["Most_Probable_Top1"]["cost"] += self.cost_per_bet
            strategies["Most_Probable_Top1"]["bets"] += 1
            if top1_cat == act_cat:
                pay = self.cost_per_bet * odds[top1_idx]
                strategies["Most_Probable_Top1"]["payout"] += pay
                strategies["Most_Probable_Top1"]["hits"] += 1
                strategies["Most_Probable_Top1"]["history"].append(pay - self.cost_per_bet)
            else:
                strategies["Most_Probable_Top1"]["history"].append(-self.cost_per_bet)

            # 4. Positive EV Only
            pos_indices = np.where(expected_values > 0.0)[0]
            step_pos_profit = 0
            for p_idx in pos_indices:
                strategies["Positive_EV_Only (EV > 0.0)"]["cost"] += self.cost_per_bet
                strategies["Positive_EV_Only (EV > 0.0)"]["bets"] += 1
                if WINNER_CATEGORIES[p_idx] == act_cat:
                    pay = self.cost_per_bet * odds[p_idx]
                    strategies["Positive_EV_Only (EV > 0.0)"]["payout"] += pay
                    strategies["Positive_EV_Only (EV > 0.0)"]["hits"] += 1
                    step_pos_profit += (pay - self.cost_per_bet)
                else:
                    step_pos_profit -= self.cost_per_bet
            strategies["Positive_EV_Only (EV > 0.0)"]["history"].append(step_pos_profit)

            # 5. Conservative Value
            cons_indices = np.where((expected_values > 0.15) & (probs >= 0.08))[0]
            step_cons_profit = 0
            for c_idx in cons_indices:
                strategies["Conservative_Value (EV > 0.15 & P >= 0.08)"]["cost"] += self.cost_per_bet
                strategies["Conservative_Value (EV > 0.15 & P >= 0.08)"]["bets"] += 1
                if WINNER_CATEGORIES[c_idx] == act_cat:
                    pay = self.cost_per_bet * odds[c_idx]
                    strategies["Conservative_Value (EV > 0.15 & P >= 0.08)"]["payout"] += pay
                    strategies["Conservative_Value (EV > 0.15 & P >= 0.08)"]["hits"] += 1
                    step_cons_profit += (pay - self.cost_per_bet)
                else:
                    step_cons_profit -= self.cost_per_bet
            strategies["Conservative_Value (EV > 0.15 & P >= 0.08)"]["history"].append(step_cons_profit)

        # 指標集計
        summary = []
        for name, data in strategies.items():
            cost = data["cost"]
            payout = data["payout"]
            net = payout - cost
            roi = (net / cost) if cost > 0 else 0.0
            hit_rate = (data["hits"] / data["bets"]) if data["bets"] > 0 else 0.0
            
            # 最大ドローダウン
            cum_profit = np.cumsum(data["history"]) if len(data["history"]) > 0 else np.zeros(1)
            running_max = np.maximum.accumulate(cum_profit)
            drawdown = running_max - cum_profit
            max_dd = float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

            summary.append({
                "Strategy": name,
                "TotalBets": data["bets"],
                "TotalCost (JPY)": int(cost),
                "TotalPayout (JPY)": int(payout),
                "NetProfit (JPY)": int(net),
                "ROI": float(roi),
                "HitRate": float(hit_rate),
                "MaxDrawdown (JPY)": int(max_dd)
            })

        return pd.DataFrame(summary), {k: v["history"] for k, v in strategies.items()}
